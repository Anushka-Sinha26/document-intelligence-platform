import io

from app.main import create_app


def create_test_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health_endpoint():
    client = create_test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["service"] == "document-intelligence-platform"


def test_list_documents_endpoint():
    client = create_test_client()

    response = client.get("/api/v1/documents")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, dict)
    assert "documents" in data
    assert "count" in data
    assert isinstance(data["documents"], list)
    assert isinstance(data["count"], int)


def test_get_nonexistent_document():
    client = create_test_client()

    response = client.get(
        "/api/v1/documents/this-document-does-not-exist.pdf"
    )

    assert response.status_code == 404


def test_process_unsupported_file():
    client = create_test_client()

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(b"This is not a supported document."),
                "unsupported.txt",
            ),
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422

    data = response.get_json()

    assert data["processing_status"] == "FAILED"
    assert data["file_validation"]["is_supported"] is False
    assert data["file_validation"]["is_readable"] is False

    assert data["file_validation"]["error"]["code"] == (
        "UNSUPPORTED_FILE_TYPE"
    )


def test_process_request_without_file():
    client = create_test_client()

    response = client.post(
        "/api/v1/documents/process",
        data={
            "document_type": "invoice",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_process_request_without_document_type():
    client = create_test_client()

    response = client.post(
        "/api/v1/documents/process",
        data={
            "file": (
                io.BytesIO(b"test document"),
                "test.txt",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_invalid_document_type():
    client = create_test_client()

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

    assert response.status_code == 400