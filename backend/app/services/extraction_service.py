import logging
import os
import time
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


# ============================================================
# Pydantic structured-output models
# ============================================================

class DocumentMetadata(BaseModel):
    """
    General metadata that may appear in any supported document.
    """

    title: Optional[str] = Field(
        default=None,
        description="Document title if explicitly visible.",
    )

    document_number: Optional[str] = Field(
        default=None,
        description=(
            "Invoice number, statement number, or other "
            "document identifier."
        ),
    )

    document_date: Optional[str] = Field(
        default=None,
        description="Document date if explicitly visible.",
    )

    currency: Optional[str] = Field(
        default=None,
        description="Currency explicitly visible in the document.",
    )

    company: Optional[str] = Field(
        default=None,
        description=(
            "Company or organization name explicitly visible."
        ),
    )

    period: Optional[str] = Field(
        default=None,
        description=(
            "Reporting period explicitly visible in the document."
        ),
    )


class ExtractedField(BaseModel):
    """
    A general extracted field with evidence.
    """

    name: str = Field(
        description="Name of the extracted field.",
    )

    value: Optional[str] = Field(
        default=None,
        description=(
            "Value exactly as represented in the document. "
            "Use null when the value is missing or unreadable."
        ),
    )

    page_number: Optional[int] = Field(
        default=None,
        description=(
            "Page number where the field was found."
        ),
    )

    evidence: Optional[str] = Field(
        default=None,
        description=(
            "Exact or near-exact source text supporting "
            "the extracted value."
        ),
    )


class ExtractedLineItem(BaseModel):
    """
    Financial statement or invoice line item.
    """

    name: str = Field(
        description="Name of the financial line item.",
    )

    value: Optional[str] = Field(
        default=None,
        description=(
            "Value as shown in the document. "
            "Keep the original numeric representation as text."
        ),
    )

    period: Optional[str] = Field(
        default=None,
        description=(
            "Period associated with this line item, "
            "if explicitly visible."
        ),
    )

    page_number: Optional[int] = Field(
        default=None,
        description=(
            "Page number where the line item was found."
        ),
    )

    evidence: Optional[str] = Field(
        default=None,
        description=(
            "Exact or near-exact source text supporting "
            "the line item."
        ),
    )


class ExtractedTable(BaseModel):
    """
    Extracted document table.
    """

    title: Optional[str] = Field(
        default=None,
        description="Table title if explicitly visible.",
    )

    columns: List[str] = Field(
        default_factory=list,
        description="Column names in the table.",
    )

    rows: List[List[Optional[str]]] = Field(
        default_factory=list,
        description=(
            "Table rows. Preserve values as strings and use "
            "null when a cell is missing or unreadable."
        ),
    )

    page_number: Optional[int] = Field(
        default=None,
        description=(
            "Page number where the table appears."
        ),
    )


class ExtractionResult(BaseModel):
    """
    Complete structured extraction result.
    """

    document_metadata: DocumentMetadata = Field(
        description="General document metadata.",
    )

    fields: List[ExtractedField] = Field(
        default_factory=list,
        description=(
            "Meaningful extracted document fields."
        ),
    )

    line_items: List[ExtractedLineItem] = Field(
        default_factory=list,
        description=(
            "Financial or invoice line items."
        ),
    )

    tables: List[ExtractedTable] = Field(
        default_factory=list,
        description=(
            "Extracted tables and their rows."
        ),
    )


# ============================================================
# Extraction service
# ============================================================

class ExtractionService:
    """
    Uses Gemini to extract structured financial information
    from OCR/native document text.

    Supported document types:
        - invoice
        - balance_sheet
        - profit_and_loss
        - cash_flow_statement
    """

    SUPPORTED_DOCUMENT_TYPES = {
        "invoice",
        "balance_sheet",
        "profit_and_loss",
        "cash_flow_statement",
    }

    # Retry temporary Gemini availability errors.
    MAX_RETRIES = 3

    RETRY_DELAYS = [
        2,
        4,
        8,
    ]

    # Gemini HTTP timeout in milliseconds.
    #
    # This gives the Gemini request enough time to complete
    # while remaining below the Gunicorn timeout configured
    # on the deployed service.
    GEMINI_TIMEOUT_MS = 150000

    def __init__(self):
        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        # ----------------------------------------------------
        # Explicit Gemini HTTP timeout
        # ----------------------------------------------------
        #
        # The Google GenAI SDK supports HttpOptions(timeout=...)
        # for controlling request timeout.
        #
        # 150000 milliseconds = 150 seconds.
        #
        # This prevents the Gemini SDK from using an unsuitable
        # default timeout for a document extraction request.
        # ----------------------------------------------------

        http_options = types.HttpOptions(
            timeout=self.GEMINI_TIMEOUT_MS
        )

        self.client = genai.Client(
            api_key=api_key,
            http_options=http_options,
        )

        logger.info(
            "Gemini ExtractionService initialized "
            "(model=%s, timeout_ms=%s)",
            self.model,
            self.GEMINI_TIMEOUT_MS,
        )

    # ========================================================
    # Main extraction method
    # ========================================================

    def extract(
        self,
        document_type: str,
        pages: list,
    ):
        """
        Extract structured information from page-level
        OCR/native text.
        """

        start_time = time.perf_counter()

        if document_type not in self.SUPPORTED_DOCUMENT_TYPES:
            raise ValueError(
                f"Unsupported document type: {document_type}"
            )

        if not pages:
            raise ValueError(
                "No extracted document text was provided."
            )

        source_text = self._build_source_text(
            pages
        )

        logger.info(
            "Preparing Gemini extraction "
            "(document_type=%s, pages=%s, source_chars=%s)",
            document_type,
            len(pages),
            len(source_text),
        )

        prompt = self._build_prompt(
            document_type=document_type,
            source_text=source_text,
        )

        logger.info(
            "Gemini prompt prepared "
            "(prompt_chars=%s)",
            len(prompt),
        )

        response = self._generate_content_with_retry(
            prompt
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Gemini extraction completed in %.2f seconds.",
            elapsed,
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty extraction response."
            )

        try:
            result = ExtractionResult.model_validate_json(
                response.text
            )

        except Exception as exc:
            logger.exception(
                "Gemini returned invalid structured extraction."
            )

            raise ValueError(
                "AI extraction returned an invalid structured result."
            ) from exc

        logger.info(
            "Structured extraction validated successfully "
            "(fields=%s, line_items=%s, tables=%s).",
            len(result.fields),
            len(result.line_items),
            len(result.tables),
        )

        return result.model_dump()

    # ========================================================
    # Gemini request with retry handling
    # ========================================================

    def _generate_content_with_retry(
        self,
        prompt: str,
    ):
        """
        Call Gemini with retry handling for temporary
        service-unavailable errors such as HTTP 503.

        Non-503 errors are raised immediately.
        """

        last_exception = None

        total_attempts = self.MAX_RETRIES + 1

        for attempt in range(total_attempts):

            attempt_start = time.perf_counter()

            try:
                logger.info(
                    "Sending extraction request to Gemini "
                    "(attempt %s/%s, model=%s)",
                    attempt + 1,
                    total_attempts,
                    self.model,
                )

                response = (
                    self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config={
                            "temperature": 0,
                            "response_mime_type": (
                                "application/json"
                            ),
                            "response_schema": ExtractionResult,
                        },
                    )
                )

                attempt_elapsed = (
                    time.perf_counter()
                    - attempt_start
                )

                logger.info(
                    "Gemini extraction request succeeded "
                    "in %.2f seconds.",
                    attempt_elapsed,
                )

                return response

            except Exception as exc:

                last_exception = exc

                attempt_elapsed = (
                    time.perf_counter()
                    - attempt_start
                )

                status_code = getattr(
                    exc,
                    "status_code",
                    None,
                )

                # Some Google API exceptions expose HTTP
                # information through a response object.
                if status_code is None:

                    response_object = getattr(
                        exc,
                        "response",
                        None,
                    )

                    status_code = getattr(
                        response_object,
                        "status_code",
                        None,
                    )

                error_text = str(exc)

                is_503 = (
                    status_code == 503
                    or (
                        "503" in error_text
                        and
                        "UNAVAILABLE"
                        in error_text.upper()
                    )
                )

                logger.error(
                    "Gemini request failed "
                    "(attempt=%s/%s, elapsed=%.2fs, "
                    "status_code=%s, is_503=%s, error=%s)",
                    attempt + 1,
                    total_attempts,
                    attempt_elapsed,
                    status_code,
                    is_503,
                    error_text,
                )

                # ------------------------------------------------
                # Non-503 errors
                # ------------------------------------------------

                if not is_503:

                    logger.exception(
                        "Gemini extraction failed with "
                        "a non-retryable error."
                    )

                    raise

                # ------------------------------------------------
                # Retry exhausted
                # ------------------------------------------------

                if attempt >= self.MAX_RETRIES:

                    logger.exception(
                        "Gemini remained unavailable after "
                        "%s retries.",
                        self.MAX_RETRIES,
                    )

                    raise RuntimeError(
                        "Gemini extraction service is temporarily "
                        "unavailable after multiple retry attempts. "
                        "Please try processing the document again."
                    ) from exc

                # ------------------------------------------------
                # Retry
                # ------------------------------------------------

                delay = self.RETRY_DELAYS[
                    attempt
                ]

                logger.warning(
                    "Gemini returned HTTP 503 UNAVAILABLE. "
                    "Retrying in %s seconds "
                    "(attempt %s/%s).",
                    delay,
                    attempt + 1,
                    total_attempts,
                )

                time.sleep(delay)

        # Defensive fallback.
        raise RuntimeError(
            "Gemini extraction failed unexpectedly."
        ) from last_exception

    # ========================================================
    # Build source text
    # ========================================================

    @staticmethod
    def _build_source_text(
        pages,
    ):
        """
        Preserve page boundaries so evidence can reference
        the correct page.
        """

        page_sections = []

        for page in pages:

            page_number = page.get(
                "page_number"
            )

            text = page.get(
                "text",
                "",
            ).strip()

            page_sections.append(
                f"--- PAGE {page_number} ---\n{text}"
            )

        return "\n\n".join(
            page_sections
        )

    # ========================================================
    # Prompt
    # ========================================================

    @staticmethod
    def _build_prompt(
        document_type: str,
        source_text: str,
    ):
        """
        Build the extraction prompt.
        """

        return f"""
You are a financial document extraction system.

DOCUMENT TYPE:
{document_type}

SOURCE DOCUMENT TEXT:
{source_text}

TASK:

Extract ALL meaningful information explicitly visible in the
document.

IMPORTANT RULES:

1. Extract only information explicitly present in the source.
2. Never invent, estimate, guess, or infer a value.
3. If a required or visible value is missing or unreadable,
   return null.
4. Preserve the original meaning of the document.
5. Extract headers and document metadata.
6. Extract dates.
7. Extract document numbers or identifiers.
8. Extract company names and parties.
9. Extract currencies when explicitly visible.
10. Extract totals and subtotals.
11. Extract financial statement line items.
12. Extract comparative-period values when visible.
13. Extract invoice or financial statement tables.
14. Extract every meaningful table row and value.
15. Do not silently omit meaningful visible information.
16. Preserve page numbers.
17. Provide evidence/source text for extracted information
    whenever possible.
18. Evidence must come from the supplied source text.
19. Do not use outside knowledge.
20. Do not calculate financial values.
21. Do not perform accounting validation.
22. Financial validation will be performed separately by the
    application.
23. Numeric values should be returned as strings so that their
    original document representation is preserved.
24. If a value cannot be reliably read, use null.

The output must follow the provided structured schema.
"""