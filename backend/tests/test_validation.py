import io

from PIL import Image
from pypdf import PdfWriter
from werkzeug.datastructures import FileStorage

from app.services.document_validation_service import (
    DocumentValidationService,
)


validation_service = DocumentValidationService()


def create_pdf(page_count: int) -> bytes:
    """Create a small in-memory PDF for testing."""

    writer = PdfWriter()

    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)

    output = io.BytesIO()
    writer.write(output)

    return output.getvalue()


def create_png() -> bytes:
    """Create a small valid PNG for testing."""

    image = Image.new("RGB", (100, 100), "white")

    output = io.BytesIO()
    image.save(output, format="PNG")

    return output.getvalue()


def make_file(
    filename: str,
    content: bytes,
) -> FileStorage:
    """Create a Werkzeug FileStorage object for testing."""

    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
    )


def test_valid_pdf_passes():
    file = make_file("sample.pdf", create_pdf(1))

    result = validation_service.validate(file)

    assert result["status"] == "PASS"
    assert result["is_supported"] is True
    assert result["is_readable"] is True
    assert result["page_count"] == 1


def test_pdf_with_three_pages_passes():
    file = make_file("sample.pdf", create_pdf(3))

    result = validation_service.validate(file)

    assert result["status"] == "PASS"
    assert result["page_count"] == 3


def test_pdf_with_more_than_three_pages_fails():
    file = make_file("sample.pdf", create_pdf(4))

    result = validation_service.validate(file)

    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "PAGE_LIMIT_EXCEEDED"
    assert result["page_count"] == 4


def test_valid_png_passes():
    file = make_file("sample.png", create_png())

    result = validation_service.validate(file)

    assert result["status"] == "PASS"
    assert result["file_type"] == "image/png"
    assert result["page_count"] == 1


def test_empty_file_fails():
    file = make_file("empty.pdf", b"")

    result = validation_service.validate(file)

    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "EMPTY_FILE"


def test_unsupported_extension_fails():
    file = make_file("sample.txt", b"some text")

    result = validation_service.validate(file)

    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_corrupted_pdf_fails():
    file = make_file(
        "corrupted.pdf",
        b"%PDF-this-is-not-a-valid-pdf",
    )

    result = validation_service.validate(file)

    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "CORRUPTED_FILE"


def test_file_extension_mismatch_fails():
    file = make_file("sample.pdf", create_png())

    result = validation_service.validate(file)

    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "FILE_TYPE_MISMATCH"