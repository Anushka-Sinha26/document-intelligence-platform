import logging
import os
import tempfile
from pathlib import Path

from flask import request
from flask_smorest import Blueprint

from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.document_validation_service import DocumentValidationService
from app.services.ocr_service import OCRService
from app.services.extraction_service import ExtractionService
from app.services.financial_validation_service import FinancialValidationService


logger = logging.getLogger(__name__)


# ============================================================
# Blueprint
# ============================================================

documents_bp = Blueprint(
    "documents",
    __name__,
    url_prefix="/api/v1/documents",
    description="Document processing and retrieval APIs",
)


# ============================================================
# Services
# ============================================================

validation_service = DocumentValidationService()
ocr_service = OCRService()
financial_validation_service = FinancialValidationService()

# Repository is an instance-based class.
document_repository = DocumentRepository()

# Gemini extraction service is intentionally initialized lazily.
# This prevents pytest collection from requiring GEMINI_API_KEY.
extraction_service = None


def _get_extraction_service():
    """
    Create the Gemini extraction service only when
    an actual document-processing request requires it.
    """

    global extraction_service

    if extraction_service is None:
        extraction_service = ExtractionService()

    return extraction_service


# ============================================================
# Supported document types
# ============================================================

SUPPORTED_DOCUMENT_TYPES = {
    "invoice",
    "balance_sheet",
    "profit_and_loss",
    "cash_flow_statement",
}


# ============================================================
# Helper functions
# ============================================================

def _determine_processing_status(
    file_validation,
    extracted_data,
    validation_result,
):
    """
    Determine the final processing status.

    PASS:
        File validation passed, extraction succeeded,
        and applicable financial validations passed.

    FAILED:
        File validation failed, extraction failed,
        or an applicable financial validation failed.

    NOT_APPLICABLE:
        No financial validation could be performed because
        the required validation fields were unavailable.
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
    Create a consistent error response.
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


# ============================================================
# POST /api/v1/documents/process
# ============================================================

@documents_bp.route("/process", methods=["POST"])
def process_document():
    """
    Process a financial document.

    Processing flow:

        Upload
          ↓
        Document validation
          ↓
        OCR / native text extraction
          ↓
        Gemini structured extraction
          ↓
        Financial validation
          ↓
        Database persistence
          ↓
        Structured JSON response
    """

    uploaded_file = request.files.get("file")
    document_type = request.form.get("document_type")

    # --------------------------------------------------------
    # Basic request validation
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Temporary uploaded file
    # --------------------------------------------------------

    temporary_path = None

    try:
        file_suffix = Path(original_filename).suffix.lower()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_suffix,
        ) as temp_file:
            uploaded_file.save(temp_file)
            temporary_path = temp_file.name

        logger.info(
            "Processing document: name=%s type=%s",
            original_filename,
            document_type,
        )

        # ----------------------------------------------------
        # STEP 1 — Document validation
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # STEP 2 — OCR / native text extraction
        # ----------------------------------------------------

        ocr_result = ocr_service.extract_text(
            temporary_path,
            file_validation.get("file_type"),
        )

        logger.info(
            "OCR/text extraction completed for %s",
            original_filename,
        )

        pages = ocr_result.get("pages", [])

        if not pages:
            logger.error(
                "No pages/text extracted from %s",
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
                    "ocr_used": ocr_result.get(
                        "ocr_used",
                        False,
                    ),
                },
            }, 422

        # ----------------------------------------------------
        # STEP 3 — Gemini structured extraction
        # ----------------------------------------------------

        logger.info(
            "Starting AI extraction for %s",
            original_filename,
        )

        current_extraction_service = _get_extraction_service()

        extracted_data = current_extraction_service.extract(
            document_type=document_type,
            pages=pages,
        )

        logger.info(
            "AI extraction completed for %s",
            original_filename,
        )

        # ----------------------------------------------------
        # STEP 4 — Financial validation
        # ----------------------------------------------------

        validation_result = financial_validation_service.validate(
            document_type=document_type,
            extracted_data=extracted_data,
        )

        logger.info(
            "Financial validation completed for %s: %s",
            original_filename,
            validation_result,
        )

        # ----------------------------------------------------
        # STEP 5 — Determine final processing status
        # ----------------------------------------------------

        processing_status = _determine_processing_status(
            file_validation=file_validation,
            extracted_data=extracted_data,
            validation_result=validation_result,
        )

        # ----------------------------------------------------
        # STEP 6 — Processing metadata
        # ----------------------------------------------------

        processing_metadata = {
            "ocr_used": ocr_result.get(
                "ocr_used",
                False,
            ),
            "page_count": file_validation.get(
                "page_count"
            ),
            "file_type": file_validation.get(
                "file_type"
            ),
            "model": os.getenv(
                "GEMINI_MODEL",
                "gemini-2.5-flash",
            ),
        }

        # ----------------------------------------------------
        # STEP 7 — Store processing result
        # ----------------------------------------------------

        document = document_repository.create(
            document_name=original_filename,
            document_type=document_type,
            processing_status=processing_status,
            file_type=file_validation.get(
                "file_type"
            ),
            page_count=file_validation.get(
                "page_count"
            ),
            extracted_data=extracted_data,
            validation_result=validation_result,
            processing_metadata=processing_metadata,
        )

        logger.info(
            "Document stored successfully: id=%s name=%s",
            document.id,
            original_filename,
        )

        # ----------------------------------------------------
        # STEP 8 — Final structured response
        # ----------------------------------------------------

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": processing_status,
            "file_validation": file_validation,
            "extracted_data": extracted_data,
            "validation": validation_result,
            "processing_metadata": processing_metadata,
        }, 200

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
                "message": str(exc),
            },
        }, 500

    except Exception:
        logger.exception(
            "Unexpected error while processing document: %s",
            original_filename,
        )

        return {
            "document_name": original_filename,
            "document_type": document_type,
            "processing_status": "FAILED",
            "error": {
                "code": "PROCESSING_ERROR",
                "message": (
                    "An unexpected error occurred while "
                    "processing the document."
                ),
            },
        }, 500

    finally:
        # ----------------------------------------------------
        # Always remove temporary uploaded file
        # ----------------------------------------------------

        if temporary_path:
            try:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)

            except Exception:
                logger.exception(
                    "Failed to remove temporary file: %s",
                    temporary_path,
                )


# ============================================================
# GET /api/v1/documents
# ============================================================

@documents_bp.route("", methods=["GET"])
def get_documents():
    """
    Return all processed documents.
    """

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
                    "processing_status": (
                        document.processing_status
                    ),
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

    except Exception:
        logger.exception(
            "Failed to retrieve processed documents."
        )

        return {
            "status": "error",
            "message": (
                "Failed to retrieve processed documents."
            ),
        }, 500


# ============================================================
# GET /api/v1/documents/{document_name}
# ============================================================

@documents_bp.route(
    "/<path:document_name>",
    methods=["GET"],
)
def get_document(document_name):
    """
    Return the latest stored processing result
    for a document name.
    """

    try:
        document = document_repository.get_latest_by_name(
            document_name
        )

        if document is None:
            return {
                "status": "error",
                "message": (
                    f"Document '{document_name}' was not found."
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

    except Exception:
        logger.exception(
            "Failed to retrieve document: %s",
            document_name,
        )

        return {
            "status": "error",
            "message": "Failed to retrieve document.",
        }, 500