import json
import logging
import os
from typing import List, Optional

from google import genai
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
        description="Invoice number, statement number, or other document identifier.",
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
        description="Company or organization name explicitly visible.",
    )

    period: Optional[str] = Field(
        default=None,
        description="Reporting period explicitly visible in the document.",
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
        description="Page number where the field was found.",
    )

    evidence: Optional[str] = Field(
        default=None,
        description=(
            "Exact or near-exact source text supporting the extracted value."
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
        description="Page number where the line item was found.",
    )

    evidence: Optional[str] = Field(
        default=None,
        description=(
            "Exact or near-exact source text supporting the line item."
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
            "Table rows. Preserve values as strings and use null "
            "when a cell is missing or unreadable."
        ),
    )

    page_number: Optional[int] = Field(
        default=None,
        description="Page number where the table appears.",
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
        description="Meaningful extracted document fields.",
    )

    line_items: List[ExtractedLineItem] = Field(
        default_factory=list,
        description="Financial or invoice line items.",
    )

    tables: List[ExtractedTable] = Field(
        default_factory=list,
        description="Extracted tables and their rows.",
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

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash",
        )

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=api_key
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

        prompt = self._build_prompt(
            document_type=document_type,
            source_text=source_text,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
                "response_schema": ExtractionResult,
            },
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

        return result.model_dump()

    # ========================================================
    # Build source text
    # ========================================================

    @staticmethod
    def _build_source_text(pages):
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
