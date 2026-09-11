import logging
import os
import tempfile
from pathlib import Path

from flask import request
from flask_smorest import Blueprint

from app.repositories.document_repository import DocumentRepository
from app.services.document_validation_service import DocumentValidationService
from app.services.ocr_service import OCRService
from app.services.extraction_service import ExtractionService
from app.services.financial_validation_service import FinancialValidationService

logger = logging.getLogger(__name__)

documents_bp = Blueprint(
    "documents",
    __name__,
    url_prefix="/api/v1/documents",
    description="Document processing and retrieval APIs",
)

validation_service = DocumentValidationService()
ocr_service = OCRService()
financial_validation_service = FinancialValidationService()
document_repository = DocumentRepository()

# Lazy initialization so the Gemini client is created only when required.
extraction_service = None


def _get_extraction_service():
    global extraction_service

    if extraction_service is None:
        extraction_service = ExtractionService()

    return extraction_service


SUPPORTED_DOCUMENT_TYPES = {
    "invoice",
    "balance_sheet",
    "profit_and_loss",
    "cash_flow_statement",
}


def _determine_processing_status(
    file_validation,
    extracted_data,
    validation_result,
):
    """
    Determine the final processing status according to the
    document-processing requirements.
    """

    if not file_validation:
        return "FAILED"

    if file_validation.get("status") != "PASS":
        return "FAILED"

    if not extracted_data:
        return "FAILED"

    if not validation_result:
        return "FAILED"

    validation_status = validation_result.get("status")

    if validation_status == "PASS":
        return "PASS"

    if validation_status == "FAIL":
        return "FAILED"

    if validation_status == "NOT_APPLICABLE":
        return "NOT_APPLICABLE"

    return "FAILED"


def _error_response(
    document_name,
    document_type,
    code,
    message,
    status_code=422,
):
    """
    Standard error response for request/input-level errors.
    """

    return {
        "document_name": document_name,
        "document_type": document_type,
        "processing_status": "FAILED",
        "error": {
            "code": code,
            "message": message,
        },
    }, status_code


@documents_bp.route(
    "/process",
    methods=["POST"],
)
@documents_bp.doc(
    summary="Process a financial document.",
    description=(
        "Upload a financial document for validation, OCR/native text "
        "extraction, Gemini structured extraction, financial validation, "
        "database persistence, and structured JSON response."
    ),
    requestBody={
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": [
                        "file",
                        "document_type",
                    ],
                    "properties": {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": (
                                "PDF, JPG, JPEG, or PNG document. "
                                "Maximum 3 pages."
                            ),
                        },
                        "document_type": {
                            "type": "string",
                            "enum": [
                                "invoice",
                                "balance_sheet",
                                "profit_and_loss",
                                "cash_flow_statement",
                            ],
                            "description": "Financial document type.",
                        },
                    },
                },
            },
        },
    },
)
def process_document():
    """
    Main document-processing pipeline:

    1. Receive file and document type
    2. Validate request
    3. Validate document before extraction
    4. Extract native text/OCR
    5. Extract structured fields/tables using Gemini
    6. Run financial validation
    7. Determine final processing status
    8. Persist result
    9. Return structured JSON
    """

    uploaded_file = request.files.get("file")
    document_type = request.form.get("document_type")

    # ---------------------------------------------------------
    # REQUEST VALIDATION
    # ---------------------------------------------------------

    if uploaded_file is None:
        return _error_response(
            document_name="",
            document_type=document_type,
            code="FILE_REQUIRED",
            message="A document file is required.",
        )

    if not document_type:
        return _error_response(
            document_name=uploaded_file.filename or "",
            document_type="",
            code="DOCUMENT_TYPE_REQUIRED",
            message="document_type is required.",
        )

    document_type = document_type.strip().lower()

    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        return _error_response(
            document_name=uploaded_file.filename or "",
            document_type=document_type,
            code="UNSUPPORTED_DOCUMENT_TYPE",
            message=(
                "Unsupported document type. "
                "Supported types are: invoice, balance_sheet, "
                "profit_and_loss, cash_flow_statement."
            ),
        )

    original_filename = uploaded_file.filename

    if not original_filename:
        return _error_response(
            document_name="",
            document_type=document_type,
            code="INVALID_FILENAME",
            message="The uploaded file does not have a valid filename.",
        )

    temporary_path = None

    try:
        # -----------------------------------------------------
        # SAVE TEMPORARY FILE
        # -----------------------------------------------------

        file_suffix = Path(original_filename).suffix.lower()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_suffix,
        ) as temp_file:
            uploaded_file.save(temp_file)
            temporary_path = temp_file.name

        logger.info(
            "Processing document: name=%s type=%s temp_path=%s",
            original_filename,
            document_type,
            temporary_path,
        )

        # -----------------------------------------------------
        # STEP 1: DOCUMENT VALIDATION
        # -----------------------------------------------------

        logger.info(
            "Starting document validation: %s",
            original_filename,
        )

        file_validation = validation_service.validate_document(
            file_path=temporary_path,
            original_filename=original_filename,
        )

        logger.info(
            "File validation result for %s: %s",
            original_filename,
            file_validation,
        )

        if file_validation.get("status") != "PASS":
            logger.warning(
                "Document validation failed: %s",
                original_filename,
            )

            return {
                "document_name": original_filename,
                "document_type": document_type,
                "processing_status": "FAILED",
                "file_validation": file_validation,
                "extracted_data": None,
                "validation": None,
                "processing_metadata": {
                    "stage": "document_validation",
                },
            }, 422

        # -----------------------------------------------------
        # STEP 2: OCR / NATIVE TEXT EXTRACTION
        # -----------------------------------------------------

        logger.info(
            "Starting OCR/text extraction: %s",
            original_filename,
        )

        ocr_result = ocr_service.extract_text(
            temporary_path,
            file_validation.get("file_type"),
        )

        logger.info(
            "OCR/text extraction completed: name=%s pages=%s ocr_used=%s",
            original_filename,
            len(ocr_result.get("pages", [])),
            ocr_result.get("ocr_used", False),
        )

        pages = ocr_result.get("pages", [])

        if not pages:
            logger.error(
                "No pages/text extracted from document: %s",
                original_filename,
            )

            return {
                "document_name": original_filename,
                "document_type": document_type,
                "processing_status": "FAILED",
                "file_validation": file_validation,
                "extracted_data": None,
                "validation": None,
                "processing_metadata": {
                    "stage": "ocr",
                    "ocr_used": ocr_result.get("ocr_used", False),
                },
            }, 422

        # -----------------------------------------------------
        # STEP 3: AI EXTRACTION
        # -----------------------------------------------------

        logger.info(
            "Starting AI extraction: name=%s type=%s",
            original_filename,
            document_type,
        )

        current_extraction_service = _get_extraction_service()

        extracted_data = current_extraction_service.extract(
            document_type=document_type,
            pages=pages,
        )

        logger.info(
            "AI extraction completed successfully: %s",
            original_filename,
        )

        if not extracted_data:
            logger.error(
                "AI extraction returned empty result: %s",
                original_filename,
            )

            return {
                "document_name": original_filename,
                "document_type": document_type,
                "processing_status": "FAILED",
                "file_validation": file_validation,
                "extracted_data": None,
                "validation": None,
                "processing_metadata": {
                    "stage": "ai_extraction",
                    "ocr_used": ocr_result.get("ocr_used", False),
                },
            }, 422

        # -----------------------------------------------------
        # STEP 4: FINANCIAL VALIDATION
        # -----------------------------------------------------

        logger.info(
            "Starting financial validation: %s",
            original_filename,
        )

        validation_result = financial_validation_service.validate(
            document_type=document_type,
            extracted_data=extracted_data,
        )

        logger.info(
            "Financial validation completed: name=%s result=%s",
            original_filename,
            validation_result,
        )

        # -----------------------------------------------------
        # STEP 5: FINAL PROCESSING STATUS
        # -----------------------------------------------------

        processing_status = _determine_processing_status(
            file_validation=file_validation,
            extracted_data=extracted_data,
            validation_result=validation_result,
        )

        logger.info(
            "Final processing status: name=%s status=%s",
            original_filename,
            processing_status,
        )

        # -----------------------------------------------------
        # STEP 6: PROCESSING METADATA
        # -----------------------------------------------------

        processing_metadata = {
            "ocr_used": ocr_result.get("ocr_used", False),
            "page_count": file_validation.get("page_count"),
            "file_type": file_validation.get("file_type"),
            "model": os.getenv(
                "GEMINI_MODEL",
                "gemini-3.5-flash",
            ),
        }

        # -----------------------------------------------------
        # STEP 7: DATABASE PERSISTENCE
        # -----------------------------------------------------

        logger.info(
            "Saving processing result to database: %s",
            original_filename,
        )

        document = document_repository.create(
            document_name=original_filename,
            document_type=document_type,
            processing_status=processing_status,
            file_type=file_validation.get("file_type"),
            page_count=file_validation.get("page_count"),
            extracted_data=extracted_data,
            validation_result=validation_result,
            processing_metadata=processing_metadata,
        )

        logger.info(
            "Document stored successfully: id=%s name=%s",
            document.id,
            original_filename,
        )

        # -----------------------------------------------------
        # STEP 8: FINAL RESPONSE
        # -----------------------------------------------------

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": processing_status,
            "file_validation": file_validation,
            "extracted_data": extracted_data,
            "validation": validation_result,
            "processing_metadata": processing_metadata,
        }, 200

    # ---------------------------------------------------------
    # GEMINI / EXTERNAL SERVICE FAILURE
    # ---------------------------------------------------------

    except RuntimeError as exc:
        logger.exception(
            "External AI/service failure while processing %s",
            original_filename,
        )

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": "FAILED",
            "error": {
                "code": "AI_SERVICE_UNAVAILABLE",
                "message": str(exc),
            },
        }, 503

    # ---------------------------------------------------------
    # VALUE / CONFIGURATION ERROR
    # ---------------------------------------------------------

    except ValueError as exc:
        logger.exception(
            "Validation/configuration error while processing %s",
            original_filename,
        )

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": "FAILED",
            "error": {
                "code": "PROCESSING_ERROR",
                "message": f"{type(exc).__name__}: {str(exc)}",
            },
        }, 500

    # ---------------------------------------------------------
    # UNEXPECTED ERROR
    # ---------------------------------------------------------

    except Exception as exc:
        logger.exception(
            "Unexpected error while processing document: %s",
            original_filename,
        )

        # IMPORTANT:
        # Return the actual exception temporarily so we can identify
        # the remaining local processing problem instead of hiding it
        # behind a generic 500 response.

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": "FAILED",
            "error": {
                "code": "PROCESSING_ERROR",
                "message": f"{type(exc).__name__}: {str(exc)}",
            },
        }, 500

    # ---------------------------------------------------------
    # TEMPORARY FILE CLEANUP
    # ---------------------------------------------------------

    finally:
        if temporary_path:
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)

                    logger.info(
                        "Temporary file removed: %s",
                        temporary_path,
                    )

            except Exception:
                logger.exception(
                    "Failed to remove temporary file: %s",
                    temporary_path,
                )


# =============================================================
# GET ALL PROCESSED DOCUMENTS
# =============================================================

@documents_bp.route(
    "",
    methods=["GET"],
)
def get_documents():
    try:
        documents = document_repository.get_all()

        return {
            "status": "success",
            "count": len(documents),
            "documents": [
                {
                    "id": document.id,
                    "document_name": document.document_name,
                    "document_type": document.document_type,
                    "processing_status": document.processing_status,
                    "file_type": document.file_type,
                    "page_count": document.page_count,
                    "created_at": (
                        document.created_at.isoformat()
                        if document.created_at
                        else None
                    ),
                    "updated_at": (
                        document.updated_at.isoformat()
                        if document.updated_at
                        else None
                    ),
                }
                for document in documents
            ],
        }, 200

    except Exception as exc:
        logger.exception(
            "Failed to retrieve processed documents."
        )

        return {
            "status": "error",
            "message": f"{type(exc).__name__}: {str(exc)}",
        }, 500


# =============================================================
# GET LATEST DOCUMENT BY NAME
# =============================================================

@documents_bp.route(
    "/<path:document_name>",
    methods=["GET"],
)
def get_document(document_name):
    try:
        document = document_repository.get_latest_by_name(
            document_name
        )

        if document is None:
            return {
                "status": "error",
                "message": (
                    f"Document '{document_name}' "
                    "was not found."
                ),
            }, 404

        return {
            "document_name": document.document_name,
            "document_type": document.document_type,
            "processing_status": document.processing_status,
            "file_validation": {
                "status": "PASS",
                "file_type": document.file_type,
                "page_count": document.page_count,
            },
            "extracted_data": document.extracted_data,
            "validation": document.validation_result,
            "processing_metadata": document.processing_metadata,
            "created_at": (
                document.created_at.isoformat()
                if document.created_at
                else None
            ),
            "updated_at": (
                document.updated_at.isoformat()
                if document.updated_at
                else None
            ),
        }, 200

    except Exception as exc:
        logger.exception(
            "Failed to retrieve document: %s",
            document_name,
        )

        return {
            "status": "error",
            "message": f"{type(exc).__name__}: {str(exc)}",
        }, 500