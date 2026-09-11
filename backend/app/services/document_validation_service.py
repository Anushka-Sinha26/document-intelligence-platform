import os
import tempfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


class DocumentValidationService:
    """
    Validates uploaded financial documents before OCR or AI extraction.

    Supported formats:
        - PDF
        - JPG
        - JPEG
        - PNG

    Validation includes:
        - File presence
        - File name
        - Empty file detection
        - Supported extension
        - Actual file signature
        - Extension/signature match
        - PDF readability
        - PDF encryption check
        - PDF page count
        - Maximum 3-page limit
        - Image readability
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
    }

    MAX_PAGES = 3

    # ---------------------------------------------------------
    # Existing test-compatible validation method
    # ---------------------------------------------------------

    def validate(self, uploaded_file):
        """
        Validate a Flask/Werkzeug uploaded file.

        This method is retained for compatibility with the
        existing automated validation tests.
        """

        if uploaded_file is None:
            return self._failure(
                error_code="FILE_REQUIRED",
                error_message="A document file is required.",
            )

        temporary_path = self.create_temporary_file(
            uploaded_file
        )

        try:
            return self.validate_document(
                temporary_path,
                uploaded_file.filename,
            )

        finally:
            self.remove_temporary_file(
                temporary_path
            )

    # ---------------------------------------------------------
    # Main validation method
    # ---------------------------------------------------------

    @classmethod
    def validate_document(
        cls,
        file_path: str,
        original_filename: str | None = None,
    ):
        """
        Validate a document before OCR or AI extraction.
        """

        # -----------------------------------------------------
        # 1. File path
        # -----------------------------------------------------

        if not file_path:
            return cls._failure(
                error_code="FILE_REQUIRED",
                error_message="A document file is required.",
            )

        path = Path(file_path)

        if not path.exists():
            return cls._failure(
                error_code="FILE_NOT_FOUND",
                error_message=(
                    "The uploaded document could not be found."
                ),
            )

        # -----------------------------------------------------
        # 2. File name
        # -----------------------------------------------------

        filename = original_filename or path.name

        if not filename:
            return cls._failure(
                error_code="INVALID_FILE_NAME",
                error_message=(
                    "The uploaded document must have a valid "
                    "file name."
                ),
            )

        # -----------------------------------------------------
        # 3. Empty file
        # -----------------------------------------------------

        try:
            file_size = path.stat().st_size

        except OSError:
            return cls._failure(
                error_code="FILE_ACCESS_ERROR",
                error_message=(
                    "The uploaded document could not be accessed."
                ),
            )

        if file_size == 0:
            return cls._failure(
                error_code="EMPTY_FILE",
                error_message=(
                    "The uploaded document is empty."
                ),
            )

        # -----------------------------------------------------
        # 4. File extension
        # -----------------------------------------------------

        extension = path.suffix.lower()

        if extension not in cls.SUPPORTED_EXTENSIONS:
            return cls._failure(
                error_code="UNSUPPORTED_FILE_TYPE",
                error_message=(
                    "Unsupported file type. Only PDF, JPG, JPEG, "
                    "and PNG files are supported."
                ),
            )

        # -----------------------------------------------------
        # 5. Detect actual file type
        # -----------------------------------------------------

        try:
            actual_file_type = cls._detect_file_type(path)

        except OSError:
            return cls._failure(
                error_code="FILE_READ_ERROR",
                error_message=(
                    "The uploaded document could not be read."
                ),
            )

        if actual_file_type is None:
            return cls._failure(
                error_code="CORRUPTED_FILE",
                error_message=(
                    "The uploaded document is corrupted or does "
                    "not have a valid PDF, JPG, JPEG, or PNG "
                    "file signature."
                ),
            )

        # -----------------------------------------------------
        # 6. Extension/signature consistency
        # -----------------------------------------------------

        expected_file_type = cls._extension_to_file_type(
            extension
        )

        if actual_file_type != expected_file_type:
            return cls._failure(
                error_code="FILE_TYPE_MISMATCH",
                error_message=(
                    "The file extension does not match the actual "
                    "file format."
                ),
            )

        # -----------------------------------------------------
        # 7. PDF validation
        # -----------------------------------------------------

        if actual_file_type == "application/pdf":
            return cls._validate_pdf(path)

        # -----------------------------------------------------
        # 8. Image validation
        # -----------------------------------------------------

        if actual_file_type in {
            "image/jpeg",
            "image/png",
        }:
            return cls._validate_image(
                path,
                actual_file_type,
            )

        # -----------------------------------------------------
        # 9. Fallback
        # -----------------------------------------------------

        return cls._failure(
            error_code="CORRUPTED_FILE",
            error_message=(
                "The uploaded document could not be validated."
            ),
        )

    # ---------------------------------------------------------
    # PDF validation
    # ---------------------------------------------------------

    @classmethod
    def _validate_pdf(cls, path: Path):
        """
        Validate PDF readability, encryption and page count.
        """

        try:
            reader = PdfReader(str(path))

            # -------------------------------------------------
            # Encrypted PDF
            # -------------------------------------------------

            if reader.is_encrypted:
                return cls._failure(
                    error_code="ENCRYPTED_PDF",
                    error_message=(
                        "The PDF is encrypted or password protected "
                        "and cannot be processed."
                    ),
                    file_type="application/pdf",
                )

            # -------------------------------------------------
            # Page count
            # -------------------------------------------------

            page_count = len(reader.pages)

            if page_count == 0:
                return cls._failure(
                    error_code="EMPTY_PDF",
                    error_message=(
                        "The PDF does not contain any pages."
                    ),
                    file_type="application/pdf",
                    page_count=0,
                )

            if page_count > cls.MAX_PAGES:
                return cls._failure(
                    error_code="PAGE_LIMIT_EXCEEDED",
                    error_message=(
                        f"The document contains {page_count} pages. "
                        f"The maximum allowed is "
                        f"{cls.MAX_PAGES} pages."
                    ),
                    file_type="application/pdf",
                    page_count=page_count,
                )

            # -------------------------------------------------
            # Basic readability check
            # -------------------------------------------------

            for page in reader.pages:
                _ = page.mediabox

            return {
                "file_type": "application/pdf",
                "is_supported": True,
                "is_readable": True,
                "page_count": page_count,
                "status": "PASS",
            }

        except Exception:
            return cls._failure(
                error_code="CORRUPTED_FILE",
                error_message=(
                    "The PDF is corrupted, malformed, or could "
                    "not be read."
                ),
                file_type="application/pdf",
            )

    # ---------------------------------------------------------
    # Image validation
    # ---------------------------------------------------------

    @classmethod
    def _validate_image(
        cls,
        path: Path,
        file_type: str,
    ):
        """
        Validate JPG/JPEG/PNG image readability.
        """

        try:
            # First verify the image.
            with Image.open(path) as image:
                image.verify()

            # Re-open because verify() invalidates the image.
            with Image.open(path) as image:
                width, height = image.size

                if width <= 0 or height <= 0:
                    return cls._failure(
                        error_code="INVALID_IMAGE_DIMENSIONS",
                        error_message=(
                            "The image has invalid dimensions."
                        ),
                        file_type=file_type,
                    )

            return {
                "file_type": file_type,
                "is_supported": True,
                "is_readable": True,
                "page_count": 1,
                "status": "PASS",
            }

        except Exception:
            return cls._failure(
                error_code="CORRUPTED_FILE",
                error_message=(
                    "The uploaded image is corrupted or could "
                    "not be read."
                ),
                file_type=file_type,
            )

    # ---------------------------------------------------------
    # File signature detection
    # ---------------------------------------------------------

    @staticmethod
    def _detect_file_type(path: Path):
        """
        Detect actual file type using binary file signatures.
        """

        with open(path, "rb") as file:
            header = file.read(16)

        # PDF signature
        if header.startswith(b"%PDF-"):
            return "application/pdf"

        # JPEG signature
        if header.startswith(b"\xFF\xD8\xFF"):
            return "image/jpeg"

        # PNG signature
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"

        return None

    # ---------------------------------------------------------
    # Extension mapping
    # ---------------------------------------------------------

    @staticmethod
    def _extension_to_file_type(extension: str):
        """
        Convert a file extension to its expected MIME type.
        """

        mapping = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }

        return mapping.get(extension)

    # ---------------------------------------------------------
    # Temporary file creation
    # ---------------------------------------------------------

    @staticmethod
    def create_temporary_file(uploaded_file):
        """
        Save an uploaded Flask file to a temporary location.
        """

        suffix = ""

        if uploaded_file.filename:
            _, extension = os.path.splitext(
                uploaded_file.filename
            )

            suffix = extension.lower()

        temporary_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        )

        try:
            uploaded_file.save(
                temporary_file.name
            )

            return temporary_file.name

        finally:
            temporary_file.close()

    # ---------------------------------------------------------
    # Temporary file cleanup
    # ---------------------------------------------------------

    @staticmethod
    def remove_temporary_file(file_path):
        """
        Delete a temporary uploaded document.
        """

        if not file_path:
            return

        try:
            if os.path.exists(file_path):
                os.remove(file_path)

        except OSError:
            # Cleanup failure must not crash processing.
            pass

    # ---------------------------------------------------------
    # Standardized failure response
    # ---------------------------------------------------------

    @staticmethod
    def _failure(
        error_code: str,
        error_message: str,
        file_type: str | None = None,
        page_count: int | None = None,
    ):
        """
        Create a standardized validation failure response.

        The nested 'error' structure is retained because the
        existing automated tests expect result["error"]["code"].
        """

        return {
            "status": "FAILED",
            "file_type": file_type,
            "is_supported": False,
            "is_readable": False,
            "page_count": page_count,
            "error": {
                "code": error_code,
                "message": error_message,
            },
        }