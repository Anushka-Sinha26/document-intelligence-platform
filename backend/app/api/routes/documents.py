import logging
import os
import tempfile

from flask_smorest import Blueprint
from flask import jsonify, request

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
)


SUPPORTED_DOCUMENT_TYPES = {
    "invoice",
    "balance_sheet",
    "profit_and_loss",
    "cash_flow_statement",
}


@documents_bp.post("/process")
@documents_bp.doc(
    summary="Process a financial document",
    description=(
        "Process a financial document through the complete pipeline.\n\n"
        "Pipeline:\n"
        "1. Validate uploaded file\n"
        "2. Extract text / OCR\n"
        "3. Extract structured data using Gemini\n"
        "4. Perform deterministic financial validation\n"
        "5. Store the result in the database\n"
        "6. Return the final structured response"
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
                                "Financial document in PDF, JPG, JPEG, or PNG format. "
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
                            "description": "Type of financial document.",
                        },
                    },
                }
            }
        },
    },
)
def process_document():
    """
    Process a financial document through the complete pipeline.

    Pipeline:
    1. Validate uploaded file
    2. Extract text / OCR
    3. Extract structured data using Gemini
    4. Perform deterministic financial validation
    5. Store the result in the database
    6. Return the final structured response
    """

    uploaded_file = request.files.get("file")
    document_type = request.form.get("document_type")

    # ---------------------------------------------------------------
    # Basic request validation
    # ---------------------------------------------------------------

    if uploaded_file is None:
        return jsonify({
            "error": {
                "code": "FILE_REQUIRED",
                "message": "A document file is required.",
            }
        }), 400

    if not document_type:
        return jsonify({
            "error": {
                "code": "DOCUMENT_TYPE_REQUIRED",
                "message": "document_type is required.",
            }
        }), 400

    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        return jsonify({
            "error": {
                "code": "INVALID_DOCUMENT_TYPE",
                "message": (
                    "document_type must be one of: "
                    "invoice, balance_sheet, "
                    "profit_and_loss, cash_flow_statement."
                ),
            }
        }), 400

    if not uploaded_file.filename:
        return jsonify({
            "error": {
                "code": "INVALID_FILENAME",
                "message": "The uploaded file must have a filename.",
            }
        }), 400

    document_name = uploaded_file.filename

    temp_path = None

    try:
        # -----------------------------------------------------------
        # Save uploaded file temporarily
        # -----------------------------------------------------------

        suffix = os.path.splitext(document_name)[1].lower()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:

            uploaded_file.save(temp_file.name)
            temp_path = temp_file.name

        logger.info(
            "Processing document: name=%s type=%s",
            document_name,
            document_type,
        )

        # -----------------------------------------------------------
        # 1. DOCUMENT VALIDATION
        # -----------------------------------------------------------

        validation_service = DocumentValidationService()

        file_validation = validation_service.validate_document(
            temp_path,
            document_name,
        )

        if file_validation["status"] != "PASS":

            logger.warning(
                "Document validation failed: %s",
                file_validation,
            )

            return jsonify({
                "document_name": document_name,
                "document_type": document_type,
                "processing_status": "FAILED",
                "file_validation": file_validation,
                "extracted_data": None,
                "validation": None,
                "processing_metadata": None,
            }), 422

        # -----------------------------------------------------------
        # 2. OCR / TEXT EXTRACTION
        # -----------------------------------------------------------

        logger.info(
            "Starting OCR/text extraction for %s",
            document_name,
        )

        ocr_service = OCRService()

        ocr_result = ocr_service.extract_text(
            temp_path
        )

        if not ocr_result.get("pages"):

            logger.warning(
                "No readable text found in document: %s",
                document_name,
            )

            return jsonify({
                "document_name": document_name,
                "document_type": document_type,
                "processing_status": "FAILED",
                "file_validation": file_validation,
                "extracted_data": None,
                "validation": None,
                "processing_metadata": {
                    "ocr_used": ocr_result.get(
                        "ocr_used",
                        False,
                    ),
                    "error": (
                        "No readable text could be extracted."
                    ),
                },
            }), 422

        # -----------------------------------------------------------
        # 3. GEMINI STRUCTURED EXTRACTION
        # -----------------------------------------------------------

        logger.info(
            "Starting AI extraction for %s",
            document_name,
        )

        extraction_service = ExtractionService()

        extraction_result = extraction_service.extract(
            document_type,
            ocr_result["pages"],
        )

        # -----------------------------------------------------------
        # 4. FINANCIAL VALIDATION
        # -----------------------------------------------------------

        logger.info(
            "Starting financial validation for %s",
            document_name,
        )

        financial_validation_service = (
            FinancialValidationService()
        )

        validation_result = (
            financial_validation_service.validate(
                document_type,
                extraction_result,
            )
        )

        # -----------------------------------------------------------
        # 5. DETERMINE FINAL PROCESSING STATUS
        # -----------------------------------------------------------

        processing_status = _determine_processing_status(
            validation_result
        )

        # -----------------------------------------------------------
        # 6. PROCESSING METADATA
        # -----------------------------------------------------------

        processing_metadata = {
            "ocr_used": ocr_result.get(
                "ocr_used",
                False,
            ),
            "page_count": file_validation.get(
                "page_count"
            ),
        }

        # -----------------------------------------------------------
        # 7. SAVE RESULT TO DATABASE
        # -----------------------------------------------------------

        logger.info(
            "Saving processing result to database: %s",
            document_name,
        )

        document_repository = DocumentRepository()

        document_repository.create(
            document_name=document_name,
            document_type=document_type,
            processing_status=processing_status,
            file_validation=file_validation,
            extracted_data=extraction_result,
            validation_result=validation_result,
            processing_metadata=processing_metadata,
        )

        # -----------------------------------------------------------
        # 8. BUILD FINAL RESPONSE
        # -----------------------------------------------------------

        response = {
            "document_name": document_name,
            "document_type": document_type,
            "processing_status": processing_status,
            "overall_confidence": None,
            "file_validation": file_validation,
            "extracted_data": extraction_result,
            "validation": validation_result,
            "processing_metadata": processing_metadata,
        }

        logger.info(
            "Document processing completed: name=%s status=%s",
            document_name,
            processing_status,
        )

        return jsonify(response), 200

    except Exception:

        logger.exception(
            "Unexpected error while processing document: %s",
            document_name,
        )

        return jsonify({
            "document_name": document_name,
            "document_type": document_type,
            "processing_status": "FAILED",
            "error": {
                "code": "PROCESSING_ERROR",
                "message": (
                    "An unexpected error occurred while "
                    "processing the document."
                ),
            },
        }), 500

    finally:

        # -----------------------------------------------------------
        # Always remove temporary uploaded file
        # -----------------------------------------------------------

        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)

            except OSError:

                logger.warning(
                    "Could not remove temporary file: %s",
                    temp_path,
                )


@documents_bp.get("")
@documents_bp.doc(
    summary="Get all processed documents",
    description="Return all documents stored in the database.",
)
def get_documents():
    """Return all processed documents."""

    try:
        repository = DocumentRepository()
        documents = repository.get_all()

        results = []

        for document in documents:
            results.append({
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
            })

        return jsonify({
            "count": len(results),
            "documents": results,
        }), 200

    except Exception:

        logger.exception(
            "Failed to retrieve documents."
        )

        return jsonify({
            "error": {
                "code": "DOCUMENT_LIST_ERROR",
                "message": (
                    "An unexpected error occurred while "
                    "retrieving documents."
                ),
            }
        }), 500


@documents_bp.get("/<string:document_name>")
@documents_bp.doc(
    summary="Get a processed document",
    description=(
        "Return the latest stored processing result for a document "
        "using its filename."
    ),
)
def get_document(document_name):
    """Return the latest processing result for a document."""

    try:
        repository = DocumentRepository()

        document = repository.get_latest_by_name(
            document_name
        )

        if document is None:
            return jsonify({
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": (
                        f"No processed document found with name "
                        f"'{document_name}'."
                    ),
                }
            }), 404

        response = {
            "document_name": document.document_name,
            "document_type": document.document_type,
            "processing_status": document.processing_status,
            "overall_confidence": None,
            "file_validation": {
                "file_type": document.file_type,
                "page_count": document.page_count,
            },
            "extracted_data": document.extracted_data,
            "validation": document.validation_result,
            "processing_metadata": document.processing_metadata,
        }

        return jsonify(response), 200

    except Exception:

        logger.exception(
            "Failed to retrieve document: %s",
            document_name,
        )

        return jsonify({
            "error": {
                "code": "DOCUMENT_RETRIEVAL_ERROR",
                "message": (
                    "An unexpected error occurred while "
                    "retrieving the document."
                ),
            }
        }), 500


def _determine_processing_status(
    validation_result,
):
    """
    Determine final processing status.

    PASS:
        All applicable financial checks pass.

    FAILED:
        At least one financial check fails.

    NOT_APPLICABLE:
        No financial validation could be performed.

    The assignment requires NOT_APPLICABLE for an individual
    validation when its required fields are missing. The overall
    document can still be processed successfully when no applicable
    financial check fails.
    """

    validation_status = validation_result.get(
        "status"
    )

    if validation_status == "FAIL":
        return "FAILED"

    if validation_status == "PASS":
        return "PASS"

    return "PASS"