import io

import pytest

from app.main import create_app
from app.core.database import db


# ============================================================
# Test application setup
# ============================================================

@pytest.fixture()
def app():
    """
    Create a Flask application for API tests.
    """

    app = create_app()

    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """
    Flask test client.
    """

    return app.test_client()


# ============================================================
# Health endpoint
# ============================================================

def test_health_endpoint(client):
    """
    Health endpoint should return HTTP 200.
    """

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data is not None
    assert data["status"] == "success"
    assert data["service"] == "document-intelligence-platform"
    assert data["message"] == "API is running"


# ============================================================
# List documents
# ============================================================

def test_list_documents_endpoint(client):
    """
    GET /api/v1/documents should return a document list.
    """

    response = client.get("/api/v1/documents")

    assert response.status_code == 200

    data = response.get_json()

    assert data is not None
    assert "documents" in data
    assert "count" in data

    assert isinstance(data["documents"], list)
    assert data["count"] == 0


# ============================================================
# Get non-existent document
# ============================================================

def test_get_nonexistent_document(client):
    """
    Requesting a document that does not exist should
    return HTTP 404.
    """

    response = client.get(
        "/api/v1/documents/"
        "this-document-does-not-exist.pdf"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data is not None


# ============================================================
# Process request without file
# ============================================================

def test_process_request_without_file(client):
    """
    Processing without a file should return HTTP 422.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


# ============================================================
# Process request without document type
# ============================================================

def test_process_request_without_document_type(client):
    """
    Processing without document_type should return HTTP 422.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(b"test document"),
                "test.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


# ============================================================
# Invalid document type
# ============================================================

def test_invalid_document_type(client):
    """
    An unsupported document_type should return HTTP 422.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(b"test document"),
                "test.txt",
            ),
            "document_type": "invalid_type",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


# ============================================================
# Unsupported file type
# ============================================================

def test_unsupported_file_type(client):
    """
    Unsupported file extensions should be rejected.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(
                    b"This is a text file."
                ),
                "test.txt",
            ),
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422

    data = response.get_json()

    assert data is not None
    assert data.get("processing_status") == "FAILED"


# ============================================================
# Empty filename
# ============================================================

def test_process_request_empty_filename(client):
    """
    An uploaded file without a filename should be rejected.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(b"test document"),
                "",
            ),
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


# ============================================================
# Invalid PDF file
# ============================================================

def test_invalid_pdf_file(client):
    """
    A file named as PDF but containing invalid PDF data
    should fail document validation.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(
                    b"This is not a real PDF file."
                ),
                "invalid.pdf",
            ),
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422

    data = response.get_json()

    assert data is not None
    assert data.get("processing_status") == "FAILED"

    file_validation = data.get("file_validation")

    assert file_validation is not None
    assert file_validation.get("status") == "FAILED"


# ============================================================
# File type mismatch
# ============================================================

def test_file_type_mismatch(client):
    """
    A file whose extension does not match its actual content
    should be rejected.
    """

    fake_png = (
        b"\x89PNG\r\n\x1a\n"
        b"invalid-content"
    )

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(fake_png),
                "mismatch.pdf",
            ),
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422

    data = response.get_json()

    assert data is not None
    assert data.get("processing_status") == "FAILED"

    file_validation = data.get("file_validation")

    assert file_validation is not None
    assert file_validation.get("status") == "FAILED"


# ============================================================
# OpenAPI endpoint
# ============================================================

def test_openapi_endpoint(client):
    """
    OpenAPI specification should be available.
    """

    response = client.get("/openapi.json")

    assert response.status_code == 200

    data = response.get_json()

    assert data is not None
    assert "openapi" in data
    assert "paths" in data


# ============================================================
# Swagger UI
# ============================================================

def test_swagger_ui_endpoint(client):
    """
    Swagger UI should be available.
    """

    response = client.get("/swagger-ui")

    assert response.status_code == 200


# ============================================================
# Process endpoint exists
# ============================================================

def test_process_endpoint_exists(client):
    """
    The document processing endpoint should exist.
    """

    response = client.post(
        "/api/v1/documents/process",
        content_type="multipart/form-data",
    )

    assert response.status_code == 422


# ============================================================
# Supported document types
# ============================================================

@pytest.mark.parametrize(
    "document_type",
    [
        "invoice",
        "balance_sheet",
        "profit_and_loss",
        "cash_flow_statement",
    ],
)
def test_supported_document_type_values(
    client,
    document_type,
):
    """
    The four document types required by the assignment
    should be accepted as valid document type metadata.

    The uploaded content is intentionally invalid, so this
    test checks that the request does not fail because of
    an unsupported document type.
    """

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(
                    b"not a valid financial document"
                ),
                "test.pdf",
            ),
            "document_type": document_type,
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422

    data = response.get_json()

    assert data is not None

    # The request should reach file/document validation.
    # It must not report an invalid document type.
    error = data.get("error")

    if isinstance(error, dict):
        assert error.get("code") != "INVALID_DOCUMENT_TYPE"


# ============================================================
# Invalid request content type
# ============================================================

def test_process_request_with_invalid_content_type(client):
    """
    A non-multipart request should not be accepted as a
    valid document-processing request.
    """

    response = client.post(
        "/api/v1/documents/process",
        json={
            "document_type": "invoice",
        },
    )

    assert response.status_code in (
        400,
        415,
        422,
    )