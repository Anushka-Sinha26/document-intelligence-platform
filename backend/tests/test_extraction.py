import json

import pytest

from app.services.extraction_service import (
    ExtractionResult,
    ExtractionService,
)


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.last_model = None
        self.last_contents = None
        self.last_config = None

    def generate_content(self, model, contents, config):
        self.last_model = model
        self.last_contents = contents
        self.last_config = config

        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def create_service(monkeypatch, response_text):
    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "test-api-key",
    )

    response = FakeResponse(response_text)

    service = ExtractionService()

    service.client = FakeClient(response)

    return service


def test_build_source_text_preserves_page_numbers():
    pages = [
        {
            "page_number": 1,
            "text": "Invoice Number: INV-1001",
        },
        {
            "page_number": 2,
            "text": "Total: 11800.00",
        },
    ]

    source_text = ExtractionService._build_source_text(pages)

    assert "--- PAGE 1 ---" in source_text
    assert "Invoice Number: INV-1001" in source_text

    assert "--- PAGE 2 ---" in source_text
    assert "Total: 11800.00" in source_text


def test_build_source_text_handles_empty_text():
    pages = [
        {
            "page_number": 1,
            "text": "",
        }
    ]

    source_text = ExtractionService._build_source_text(pages)

    assert "--- PAGE 1 ---" in source_text


def test_build_prompt_contains_document_type_and_source_text():
    source_text = (
        "--- PAGE 1 ---\n"
        "Invoice Number: INV-1001\n"
        "Total: 11800.00"
    )

    prompt = ExtractionService._build_prompt(
        document_type="invoice",
        source_text=source_text,
    )

    assert "invoice" in prompt
    assert "Invoice Number: INV-1001" in prompt
    assert "Total: 11800.00" in prompt

    assert "Extract ALL meaningful information" in prompt
    assert "Never invent, estimate, guess, or infer a value" in prompt
    assert "Do not calculate financial values" in prompt
    assert "Do not perform accounting validation" in prompt


def test_extraction_service_requires_api_key(monkeypatch):
    monkeypatch.delenv(
        "GEMINI_API_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="GEMINI_API_KEY is not configured",
    ):
        ExtractionService()


def test_extraction_rejects_unsupported_document_type(
    monkeypatch,
):
    response_text = ExtractionResult(
        document_metadata={
            "title": None,
            "document_number": None,
            "document_date": None,
            "currency": None,
            "company": None,
            "period": None,
        },
        fields=[],
        line_items=[],
        tables=[],
    ).model_dump_json()

    service = create_service(
        monkeypatch,
        response_text,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported document type",
    ):
        service.extract(
            document_type="unsupported_type",
            pages=[
                {
                    "page_number": 1,
                    "text": "Test document",
                }
            ],
        )


def test_extraction_rejects_empty_pages(
    monkeypatch,
):
    response_text = ExtractionResult(
        document_metadata={
            "title": None,
            "document_number": None,
            "document_date": None,
            "currency": None,
            "company": None,
            "period": None,
        },
        fields=[],
        line_items=[],
        tables=[],
    ).model_dump_json()

    service = create_service(
        monkeypatch,
        response_text,
    )

    with pytest.raises(
        ValueError,
        match="No extracted document text was provided",
    ):
        service.extract(
            document_type="invoice",
            pages=[],
        )


def test_extraction_returns_structured_result(
    monkeypatch,
):
    expected_result = ExtractionResult(
        document_metadata={
            "title": "Invoice",
            "document_number": "INV-1001",
            "document_date": "10-09-2026",
            "currency": "$",
            "company": "ABC Technologies",
            "period": None,
        },
        fields=[
            {
                "name": "Seller",
                "value": "ABC Technologies",
                "page_number": 1,
                "evidence": "Seller: ABC Technologies",
            },
            {
                "name": "Buyer",
                "value": "XYZ Company",
                "page_number": 1,
                "evidence": "Buyer: XYZ Company",
            },
        ],
        line_items=[
            {
                "name": "Subtotal",
                "value": "10000.00",
                "period": None,
                "page_number": 1,
                "evidence": "Subtotal: 10000.00",
            },
            {
                "name": "Tax",
                "value": "1800.00",
                "period": None,
                "page_number": 1,
                "evidence": "Tax: 1800.00",
            },
            {
                "name": "Total",
                "value": "11800.00",
                "period": None,
                "page_number": 1,
                "evidence": "Total: 11800.00",
            },
        ],
        tables=[],
    )

    service = create_service(
        monkeypatch,
        expected_result.model_dump_json(),
    )

    pages = [
        {
            "page_number": 1,
            "text": (
                "INVOICE\n"
                "Invoice Number: INV-1001\n"
                "Seller: ABC Technologies\n"
                "Buyer: XYZ Company\n"
                "Subtotal: 10000.00\n"
                "Tax: 1800.00\n"
                "Total: 11800.00"
            ),
        }
    ]

    result = service.extract(
        document_type="invoice",
        pages=pages,
    )

    assert result["document_metadata"]["document_number"] == (
        "INV-1001"
    )

    assert result["document_metadata"]["company"] == (
        "ABC Technologies"
    )

    assert len(result["fields"]) == 2
    assert len(result["line_items"]) == 3

    assert result["line_items"][0]["name"] == "Subtotal"
    assert result["line_items"][0]["value"] == "10000.00"

    assert result["line_items"][2]["name"] == "Total"
    assert result["line_items"][2]["value"] == "11800.00"


def test_extraction_sends_page_text_to_gemini(
    monkeypatch,
):
    expected_result = ExtractionResult(
        document_metadata={},
        fields=[],
        line_items=[],
        tables=[],
    )

    service = create_service(
        monkeypatch,
        expected_result.model_dump_json(),
    )

    pages = [
        {
            "page_number": 1,
            "text": "Balance Sheet",
        },
        {
            "page_number": 2,
            "text": "Total Assets: 5000",
        },
    ]

    service.extract(
        document_type="balance_sheet",
        pages=pages,
    )

    fake_client = service.client

    assert fake_client.models.last_model == service.model

    assert "--- PAGE 1 ---" in (
        fake_client.models.last_contents
    )

    assert "Balance Sheet" in (
        fake_client.models.last_contents
    )

    assert "--- PAGE 2 ---" in (
        fake_client.models.last_contents
    )

    assert "Total Assets: 5000" in (
        fake_client.models.last_contents
    )

    assert fake_client.models.last_config[
        "response_mime_type"
    ] == "application/json"

    assert fake_client.models.last_config[
        "response_schema"
    ] is ExtractionResult


def test_extraction_rejects_empty_gemini_response(
    monkeypatch,
):
    service = create_service(
        monkeypatch,
        "",
    )

    with pytest.raises(
        ValueError,
        match="Gemini returned an empty extraction response",
    ):
        service.extract(
            document_type="invoice",
            pages=[
                {
                    "page_number": 1,
                    "text": "Invoice",
                }
            ],
        )


def test_extraction_rejects_invalid_structured_response(
    monkeypatch,
):
    service = create_service(
        monkeypatch,
        '{"invalid": "structured response"}',
    )

    with pytest.raises(
        ValueError,
        match="AI extraction returned an invalid structured result",
    ):
        service.extract(
            document_type="invoice",
            pages=[
                {
                    "page_number": 1,
                    "text": "Invoice",
                }
            ],
        )