import json
import logging
import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError


logger = logging.getLogger(__name__)


# ============================================================
# EXTRACTION SCHEMAS
# ============================================================

class DocumentMetadata(BaseModel):
    document_title: str | None = None
    document_date: str | None = None
    period: str | None = None
    company_name: str | None = None
    currency: str | None = None


class ExtractedField(BaseModel):
    field_name: str
    value: str | None = None
    source_text: str | None = None
    page_number: int | None = None
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )


class ExtractedLineItem(BaseModel):
    description: str | None = None
    quantity: str | None = None
    unit_price: str | None = None
    amount: str | None = None
    source_text: str | None = None
    page_number: int | None = None
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )


class ExtractedTable(BaseModel):
    table_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str | None]] = Field(default_factory=list)
    source_text: str | None = None
    page_number: int | None = None
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )


class ExtractionResult(BaseModel):
    metadata: DocumentMetadata
    fields: list[ExtractedField] = Field(default_factory=list)
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)


# ============================================================
# EXTRACTION SERVICE
# ============================================================

class ExtractionService:

    SUPPORTED_DOCUMENT_TYPES = {
        "invoice",
        "balance_sheet",
        "profit_and_loss",
        "cash_flow_statement",
    }

    MAX_RETRIES = 3

    RETRY_DELAYS = [
        2,
        4,
        8,
    ]

    # IMPORTANT:
    # Never fall back to the retired Gemini 2.5 Flash model.
    DEFAULT_MODEL = "gemini-3.5-flash"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        # Read the configured model.
        #
        # The default is deliberately Gemini 3.5 Flash so that
        # the application cannot accidentally use the retired
        # Gemini 2.5 Flash model.
        configured_model = os.getenv(
            "GEMINI_MODEL",
            self.DEFAULT_MODEL,
        )

        configured_model = configured_model.strip()

        if not configured_model:
            configured_model = self.DEFAULT_MODEL

        # Remove "models/" if someone placed it in .env.
        # The SDK accepts the model ID itself.
        if configured_model.startswith("models/"):
            configured_model = configured_model.replace(
                "models/",
                "",
                1,
            )

        # Protect against the exact retired model that caused
        # the current 500 error.
        if configured_model == "gemini-2.5-flash":
            logger.warning(
                "GEMINI_MODEL was set to retired "
                "gemini-2.5-flash. Using gemini-3.5-flash instead."
            )

            configured_model = self.DEFAULT_MODEL

        self.model = configured_model

        logger.info(
            "Initializing Gemini ExtractionService with model=%s",
            self.model,
        )

        self.client = genai.Client(
            api_key=self.api_key,
        )

    # ========================================================
    # PUBLIC EXTRACTION METHOD
    # ========================================================

    def extract(
        self,
        document_type,
        pages,
    ):
        """
        Extract structured information from OCR/native text.

        The source text is preserved page-by-page so that the model
        can provide page numbers and source evidence.
        """

        if document_type not in self.SUPPORTED_DOCUMENT_TYPES:
            raise ValueError(
                f"Unsupported document type: {document_type}"
            )

        if not pages:
            raise ValueError(
                "No document pages were provided for extraction."
            )

        source_text = self._build_source_text(pages)

        prompt = self._build_prompt(
            document_type=document_type,
            source_text=source_text,
        )

        logger.info(
            "Sending document to Gemini: type=%s model=%s pages=%s",
            document_type,
            self.model,
            len(pages),
        )

        response = self._generate_content_with_retry(
            prompt=prompt,
        )

        if response is None:
            raise RuntimeError(
                "Gemini returned no response."
            )

        extracted_data = self._parse_response(
            response,
        )

        logger.info(
            "Gemini structured extraction successful: "
            "type=%s fields=%s tables=%s line_items=%s",
            document_type,
            len(extracted_data.get("fields", [])),
            len(extracted_data.get("tables", [])),
            len(extracted_data.get("line_items", [])),
        )

        return extracted_data

    # ========================================================
    # BUILD PAGE-PRESERVING SOURCE TEXT
    # ========================================================

    def _build_source_text(self, pages):
        page_blocks = []

        for page in pages:
            page_number = page.get(
                "page_number",
                len(page_blocks) + 1,
            )

            text = page.get(
                "text",
                "",
            )

            if text is None:
                text = ""

            text = str(text).strip()

            page_blocks.append(
                f"--- PAGE {page_number} ---\n"
                f"{text}"
            )

        return "\n\n".join(page_blocks)

    # ========================================================
    # PROMPT
    # ========================================================

    def _build_prompt(
        self,
        document_type,
        source_text,
    ):
        return f"""
You are a document intelligence extraction system.

The document type is:
{document_type}

Extract ALL meaningful information that is visibly present
in the supplied document text.

IMPORTANT RULES:

1. Extract only information explicitly present in the source.
2. Do NOT invent values.
3. Do NOT infer missing values.
4. If a field is not present, use null.
5. Preserve the original meaning of the document.
6. Extract headers and document metadata.
7. Extract dates.
8. Extract company/party names.
9. Extract currency information.
10. Extract totals.
11. Extract all meaningful financial statement line items.
12. Extract comparative periods/years when present.
13. Extract invoice or financial statement tables.
14. Extract every meaningful visible table row and value.
15. Preserve negative values.
16. Preserve zero values.
17. Preserve the source wording where practical.
18. Provide source_text/evidence for extracted values when possible.
19. Provide the page_number whenever it can be determined.
20. Confidence may be provided when appropriate.
21. Do NOT perform financial calculations.
22. Do NOT modify or correct numbers from the document.
23. Do NOT assume a value merely because a financial statement
    normally contains such a value.
24. Missing or unreadable information must remain null.

For numeric values, return them as strings so that the original
document value can be preserved accurately.

Document type-specific guidance:

INVOICE:
- invoice number
- invoice date
- due date
- seller/bill-from
- buyer/bill-to
- currency
- subtotal
- tax
- shipping/handling
- total
- all invoice line items
- product/service descriptions
- quantities
- unit prices
- amounts
- invoice tables

BALANCE SHEET:
- reporting date
- company
- currency
- all asset line items
- all liability line items
- capital/equity line items
- total assets
- total liabilities/capital
- comparative periods
- all visible tables

PROFIT AND LOSS:
- reporting period
- company
- currency
- income items
- interest earned
- other income
- total income
- expenditure items
- interest expended
- operating expenses
- provisions
- total expenditure
- profit before minority interest
- minority interest
- attributable group profit
- comparative periods
- all visible tables

CASH FLOW STATEMENT:
- reporting period
- company
- currency
- operating cash flow
- investing cash flow
- financing cash flow
- foreign exchange effect
- net increase/decrease in cash
- opening cash
- closing cash
- comparative periods
- all visible tables

Return ONLY valid JSON matching the required structured schema.

SOURCE DOCUMENT TEXT:

{source_text}
"""

    # ========================================================
    # GEMINI REQUEST WITH RETRIES
    # ========================================================

    def _generate_content_with_retry(
        self,
        prompt,
    ):
        last_exception = None

        for attempt in range(
            self.MAX_RETRIES
        ):
            try:
                logger.info(
                    "Gemini request attempt %s/%s using model=%s",
                    attempt + 1,
                    self.MAX_RETRIES,
                    self.model,
                )

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ExtractionResult,
                    ),
                )

                return response

            except Exception as exc:
                last_exception = exc

                error_text = str(exc)

                logger.exception(
                    "Gemini request failed on attempt %s/%s: %s",
                    attempt + 1,
                    self.MAX_RETRIES,
                    error_text,
                )

                # A model-not-found / invalid-model error should
                # NOT be retried because retrying the same retired
                # model will never fix the problem.
                if (
                    "404" in error_text
                    or "NOT_FOUND" in error_text
                    or "not found" in error_text.lower()
                    or "no longer available" in error_text.lower()
                ):
                    raise RuntimeError(
                        f"Gemini model '{self.model}' is unavailable. "
                        f"Please use a supported model. "
                        f"Original error: {error_text}"
                    ) from exc

                # Retry transient service errors.
                is_transient = any(
                    code in error_text
                    for code in [
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL",
                    ]
                )

                if not is_transient:
                    raise RuntimeError(
                        f"Gemini extraction failed: {error_text}"
                    ) from exc

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[
                        min(
                            attempt,
                            len(self.RETRY_DELAYS) - 1,
                        )
                    ]

                    logger.warning(
                        "Transient Gemini error. "
                        "Retrying in %s seconds.",
                        delay,
                    )

                    time.sleep(delay)

        raise RuntimeError(
            "Gemini extraction failed after "
            f"{self.MAX_RETRIES} attempts: "
            f"{last_exception}"
        ) from last_exception

    # ========================================================
    # RESPONSE PARSING
    # ========================================================

    def _parse_response(
        self,
        response,
    ):
        response_text = getattr(
            response,
            "text",
            None,
        )

        if not response_text:
            raise RuntimeError(
                "Gemini response did not contain text."
            )

        response_text = response_text.strip()

        try:
            parsed = json.loads(
                response_text
            )

            validated = ExtractionResult.model_validate(
                parsed
            )

            return validated.model_dump()

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            logger.exception(
                "Failed to parse Gemini structured response."
            )

            raise RuntimeError(
                "Gemini returned an invalid structured response: "
                f"{exc}"
            ) from exc