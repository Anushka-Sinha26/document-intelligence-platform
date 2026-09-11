from decimal import Decimal, InvalidOperation
import logging
import re


logger = logging.getLogger(__name__)


class FinancialValidationService:
    """
    Performs deterministic financial calculations and validations
    on AI-extracted document data.

    Supported document types:
    - invoice
    - balance_sheet
    - profit_and_loss
    - cash_flow_statement
    """

    DEFAULT_TOLERANCE = Decimal("0.01")

    def validate(self, document_type, extracted_data):
        """
        Validate financial consistency based on document type.
        """

        document_type = (document_type or "").strip().lower()

        if document_type == "invoice":
            return self._validate_invoice(extracted_data)

        if document_type == "balance_sheet":
            return self._validate_balance_sheet(extracted_data)

        if document_type == "profit_and_loss":
            return self._validate_profit_and_loss(extracted_data)

        if document_type == "cash_flow_statement":
            return self._validate_cash_flow_statement(extracted_data)

        return {
            "status": "NOT_APPLICABLE",
            "checks": []
        }

    # ------------------------------------------------------------------
    # GENERAL HELPERS
    # ------------------------------------------------------------------

    def _to_decimal(self, value):
        """
        Convert extracted numeric text into Decimal.

        Handles:
        - 126.27
        - 126,27
        - 1,234.56
        - 1.234,56
        - $ 126,27
        - ₹ 6,862.00
        - INR 1,046.72
        """

        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        text = str(value).strip()

        if not text:
            return None

        # Remove currency symbols and non-numeric characters except
        # decimal separators, minus sign, and parentheses.
        text = text.replace("₹", "")
        text = text.replace("$", "")
        text = text.replace("€", "")
        text = text.replace("£", "")
        text = re.sub(r"[A-Za-z]", "", text)
        text = text.strip()

        if not text:
            return None

        # Handle negative values represented as parentheses.
        negative = False

        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1].strip()

        # Keep only digits, commas, periods, and minus sign.
        text = re.sub(r"[^0-9,.\-]", "", text)

        if not text:
            return None

        # Handle both comma and period.
        if "," in text and "." in text:
            last_comma = text.rfind(",")
            last_period = text.rfind(".")

            # European format: 1.234,56
            if last_comma > last_period:
                text = text.replace(".", "")
                text = text.replace(",", ".")

            # US format: 1,234.56
            else:
                text = text.replace(",", "")

        elif "," in text:
            parts = text.split(",")

            # Example: 126,27 -> 126.27
            if len(parts) == 2 and len(parts[1]) == 2:
                text = parts[0] + "." + parts[1]

            # Example: 1,234 -> 1234
            else:
                text = text.replace(",", "")

        elif text.count(".") > 1:
            # Example: 1.234.567, if comma was already removed.
            parts = text.split(".")
            text = "".join(parts[:-1]) + "." + parts[-1]

        try:
            number = Decimal(text)

            if negative:
                number = -number

            return number

        except (InvalidOperation, ValueError):
            return None

    def _format_decimal(self, value):
        """
        Return Decimal as a clean string with two decimal places.
        """

        if value is None:
            return None

        return f"{value:.2f}"

    def _normalize_label(self, label):
        """
        Normalize labels for reliable matching.
        """

        if label is None:
            return ""

        text = str(label).lower().strip()

        text = text.replace("&", " and ")
        text = text.replace("/", " ")
        text = text.replace("-", " ")

        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def _label_matches(self, actual_label, aliases):
        """
        Check whether an extracted label matches one of the aliases.
        """

        actual = self._normalize_label(actual_label)

        if not actual:
            return False

        normalized_aliases = [
            self._normalize_label(alias)
            for alias in aliases
            if alias
        ]

        # Exact match first.
        if actual in normalized_aliases:
            return True

        # Then allow a controlled containment match.
        for alias in normalized_aliases:
            if not alias:
                continue

            if alias in actual or actual in alias:
                return True

        return False

    # ------------------------------------------------------------------
    # EXTRACTED VALUE COLLECTION
    # ------------------------------------------------------------------

    def _all_values(self, extracted_data):
        """
        Collect values from:
        - extracted fields
        - line items
        - table cells

        Each entry retains its label so that financial validation
        can select the correct value.
        """

        values = []

        if not extracted_data:
            return values

        # --------------------------------------------------------------
        # Fields
        # --------------------------------------------------------------

        for field in extracted_data.get("fields", []) or []:
            if not isinstance(field, dict):
                continue

            name = field.get("name")
            value = field.get("value")

            if name is not None and value is not None:
                values.append(
                    {
                        "label": str(name),
                        "value": value,
                        "source": "field"
                    }
                )

        # --------------------------------------------------------------
        # Line items
        # --------------------------------------------------------------

        for item in extracted_data.get("line_items", []) or []:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            value = item.get("value")

            if name is not None and value is not None:
                values.append(
                    {
                        "label": str(name),
                        "value": value,
                        "source": "line_item"
                    }
                )

        # --------------------------------------------------------------
        # Tables
        # --------------------------------------------------------------

        for table in extracted_data.get("tables", []) or []:
            if not isinstance(table, dict):
                continue

            columns = table.get("columns", []) or []
            rows = table.get("rows", []) or []

            for row in rows:
                if not isinstance(row, list):
                    continue

                for index, cell in enumerate(row):
                    if cell is None:
                        continue

                    if index < len(columns):
                        label = columns[index]
                    else:
                        label = f"column_{index + 1}"

                    values.append(
                        {
                            "label": str(label),
                            "value": cell,
                            "source": "table"
                        }
                    )

        return values

    def _find_value(self, values, aliases, preferred_sources=None):
        """
        Find the first matching numeric value.

        Exact matches are preferred before fuzzy matches.

        preferred_sources can be used when a financial value should
        preferentially come from explicit extracted fields or summary
        tables rather than line items.
        """

        if not values:
            return None

        normalized_aliases = [
            self._normalize_label(alias)
            for alias in aliases
            if alias
        ]

        # --------------------------------------------------------------
        # Pass 1: exact label matches
        # --------------------------------------------------------------

        for item in values:
            label = self._normalize_label(item.get("label"))

            if label in normalized_aliases:
                number = self._to_decimal(item.get("value"))

                if number is not None:
                    return number

        # --------------------------------------------------------------
        # Pass 2: exact matches from preferred sources
        # --------------------------------------------------------------

        if preferred_sources:
            for source in preferred_sources:
                for item in values:
                    if item.get("source") != source:
                        continue

                    label = self._normalize_label(item.get("label"))

                    if label in normalized_aliases:
                        number = self._to_decimal(item.get("value"))

                        if number is not None:
                            return number

        # --------------------------------------------------------------
        # Pass 3: controlled fuzzy matching
        # --------------------------------------------------------------

        for item in values:
            label = self._normalize_label(item.get("label"))

            if not label:
                continue

            for alias in normalized_aliases:
                if not alias:
                    continue

                # Avoid broad aliases matching unrelated line items.
                if len(alias.split()) == 1 and len(alias) <= 5:
                    if label == alias:
                        number = self._to_decimal(item.get("value"))

                        if number is not None:
                            return number
                    continue

                if alias in label:
                    number = self._to_decimal(item.get("value"))

                    if number is not None:
                        return number

        return None

    # ------------------------------------------------------------------
    # CHECK BUILDER
    # ------------------------------------------------------------------

    def _build_check(
        self,
        formula,
        input_values,
        calculated_value,
        reported_value
    ):
        """
        Build a standardized financial validation check.
        """

        if calculated_value is None or reported_value is None:
            return {
                "formula": formula,
                "input_values": input_values,
                "calculated_value": (
                    self._format_decimal(calculated_value)
                    if calculated_value is not None
                    else None
                ),
                "reported_value": (
                    self._format_decimal(reported_value)
                    if reported_value is not None
                    else None
                ),
                "variance": None,
                "status": "NOT_APPLICABLE"
            }

        variance = abs(calculated_value - reported_value)

        status = (
            "PASS"
            if variance <= self.DEFAULT_TOLERANCE
            else "FAIL"
        )

        return {
            "formula": formula,
            "input_values": input_values,
            "calculated_value": self._format_decimal(calculated_value),
            "reported_value": self._format_decimal(reported_value),
            "variance": self._format_decimal(variance),
            "status": status
        }

    def _final_status(self, checks):
        """
        Determine overall validation status.

        - FAIL if any check fails
        - PASS if all applicable checks pass
        - NOT_APPLICABLE if no check could be performed
        """

        if not checks:
            return "NOT_APPLICABLE"

        if any(check["status"] == "FAIL" for check in checks):
            return "FAIL"

        applicable_checks = [
            check
            for check in checks
            if check["status"] in {"PASS", "FAIL"}
        ]

        if not applicable_checks:
            return "NOT_APPLICABLE"

        return "PASS"

    # ------------------------------------------------------------------
    # INVOICE VALIDATION
    # ------------------------------------------------------------------

    def _validate_invoice(self, extracted_data):
        """
        Validate invoice totals.

        Supported calculation:

        Subtotal + Tax + Shipping/Handling ≈ Total

        If shipping/handling is not present:

        Subtotal + Tax ≈ Total
        """

        values = self._all_values(extracted_data)

        # --------------------------------------------------------------
        # Subtotal
        # --------------------------------------------------------------

        subtotal = self._find_value(
            values,
            [
                "subtotal",
                "sub total",
                "total net worth",
                "net worth",
                "net amount",
                "taxable amount",
                "amount before tax",
            ],
            preferred_sources=["field", "table"]
        )

        # --------------------------------------------------------------
        # Tax
        # --------------------------------------------------------------

        tax = self._find_value(
            values,
            [
                "sales tax",
                "tax",
                "total vat",
                "vat",
                "gst",
                "gst payable",
                "tax payable",
                "tax amount",
            ],
            preferred_sources=["field", "table"]
        )

        # --------------------------------------------------------------
        # IMPORTANT SHIPPING FIX
        #
        # Only use explicit shipping/handling summary labels.
        #
        # DO NOT include "freight" here because a product/line item
        # can legitimately contain the word Freight.
        # --------------------------------------------------------------

        shipping = self._find_value(
            values,
            [
                "s&h",
                "s & h",
                "shipping and handling",
                "shipping handling",
                "shipping/handling",
                "handling charge",
                "shipping charge",
                "shipping cost",
                "handling cost",
            ],
            preferred_sources=["field", "table"]
        )

        # --------------------------------------------------------------
        # Total
        # --------------------------------------------------------------

        total = self._find_value(
            values,
            [
                "total due",
                "amount due",
                "grand total",
                "invoice total",
                "total amount",
                "amount payable",
                "total payable",
                "total gross worth",
                "gross worth",
                "total",
            ],
            preferred_sources=["field", "table"]
        )

        checks = []

        # --------------------------------------------------------------
        # Calculate invoice total
        # --------------------------------------------------------------

        if subtotal is None or tax is None or total is None:
            check = self._build_check(
                formula=(
                    "Subtotal + Tax + Shipping/Handling ≈ Total"
                    if shipping is not None
                    else "Subtotal + Tax ≈ Total"
                ),
                input_values={
                    "subtotal": (
                        self._format_decimal(subtotal)
                        if subtotal is not None
                        else None
                    ),
                    "tax": (
                        self._format_decimal(tax)
                        if tax is not None
                        else None
                    ),
                    "shipping": (
                        self._format_decimal(shipping)
                        if shipping is not None
                        else None
                    )
                },
                calculated_value=None,
                reported_value=total
            )

            checks.append(check)

            return {
                "status": self._final_status(checks),
                "checks": checks
            }

        if shipping is not None:
            calculated = subtotal + tax + shipping

            formula = "Subtotal + Tax + Shipping/Handling ≈ Total"

        else:
            calculated = subtotal + tax

            formula = "Subtotal + Tax ≈ Total"

        check = self._build_check(
            formula=formula,
            input_values={
                "subtotal": self._format_decimal(subtotal),
                "tax": self._format_decimal(tax),
                "shipping": (
                    self._format_decimal(shipping)
                    if shipping is not None
                    else None
                )
            },
            calculated_value=calculated,
            reported_value=total
        )

        checks.append(check)

        return {
            "status": self._final_status(checks),
            "checks": checks
        }

    # ------------------------------------------------------------------
    # BALANCE SHEET VALIDATION
    # ------------------------------------------------------------------

    def _validate_balance_sheet(self, extracted_data):
        """
        Validate:

        Total Assets ≈ Total Capital and Liabilities
        """

        values = self._all_values(extracted_data)

        total_assets = self._find_value(
            values,
            [
                "total assets",
                "total asset",
            ],
            preferred_sources=["field", "table"]
        )

        total_capital_liabilities = self._find_value(
            values,
            [
                "total capital and liabilities",
                "total capital liabilities",
                "total liabilities and capital",
                "total liabilities and shareholders equity",
                "total liabilities and equity",
            ],
            preferred_sources=["field", "table"]
        )

        checks = []

        if (
            total_assets is None
            or total_capital_liabilities is None
        ):
            check = self._build_check(
                formula="Total Assets ≈ Total Capital and Liabilities",
                input_values={
                    "total_assets": (
                        self._format_decimal(total_assets)
                        if total_assets is not None
                        else None
                    ),
                    "total_capital_and_liabilities": (
                        self._format_decimal(total_capital_liabilities)
                        if total_capital_liabilities is not None
                        else None
                    )
                },
                calculated_value=total_assets,
                reported_value=total_capital_liabilities
            )

            checks.append(check)

            return {
                "status": self._final_status(checks),
                "checks": checks
            }

        check = self._build_check(
            formula="Total Assets ≈ Total Capital and Liabilities",
            input_values={
                "total_assets": self._format_decimal(total_assets),
                "total_capital_and_liabilities": self._format_decimal(
                    total_capital_liabilities
                )
            },
            calculated_value=total_assets,
            reported_value=total_capital_liabilities
        )

        checks.append(check)

        return {
            "status": self._final_status(checks),
            "checks": checks
        }

    # ------------------------------------------------------------------
    # PROFIT & LOSS VALIDATION
    # ------------------------------------------------------------------

    def _validate_profit_and_loss(self, extracted_data):
        """
        Validate P&L relationships.

        1. Interest Earned + Other Income ≈ Total Income

        2. Interest Expended + Operating Expenses +
           Provisions ≈ Total Expenditure

        3. Total Income - Total Expenditure ≈
           Consolidated Net Profit Before Minority Interest

        4. Profit Before Minority Interest - Minority Interest ≈
           Attributable Group Profit
        """

        values = self._all_values(extracted_data)

        interest_earned = self._find_value(
            values,
            [
                "interest earned",
                "interest income",
            ],
            preferred_sources=["field", "table"]
        )

        other_income = self._find_value(
            values,
            [
                "other income",
            ],
            preferred_sources=["field", "table"]
        )

        total_income = self._find_value(
            values,
            [
                "total income",
            ],
            preferred_sources=["field", "table"]
        )

        interest_expended = self._find_value(
            values,
            [
                "interest expended",
                "interest expense",
            ],
            preferred_sources=["field", "table"]
        )

        operating_expenses = self._find_value(
            values,
            [
                "operating expenses",
                "operating expense",
            ],
            preferred_sources=["field", "table"]
        )

        provisions = self._find_value(
            values,
            [
                "provisions and contingencies",
                "provisions contingencies",
                "provisions",
                "provision for contingencies",
            ],
            preferred_sources=["field", "table"]
        )

        total_expenditure = self._find_value(
            values,
            [
                "total expenditure",
                "total expenditures",
            ],
            preferred_sources=["field", "table"]
        )

        profit_before_minority = self._find_value(
            values,
            [
                "consolidated net profit for the year before minority interest",
                "net profit for the year before minority interest",
                "consolidated net profit before minority interest",
                "net profit before minority interest",
            ],
            preferred_sources=["field", "table"]
        )

        minority_interest = self._find_value(
            values,
            [
                "minority interest",
                "less minority interest",
            ],
            preferred_sources=["field", "table"]
        )

        attributable_group_profit = self._find_value(
            values,
            [
                "consolidated net profit for the year attributable to the group",
                "net profit for the year attributable to the group",
                "consolidated net profit attributable to the group",
                "net profit attributable to the group",
            ],
            preferred_sources=["field", "table"]
        )

        checks = []

        # --------------------------------------------------------------
        # Check 1
        # --------------------------------------------------------------

        if (
            interest_earned is not None
            and other_income is not None
            and total_income is not None
        ):
            calculated = interest_earned + other_income

            checks.append(
                self._build_check(
                    formula="Interest Earned + Other Income ≈ Total Income",
                    input_values={
                        "interest_earned": self._format_decimal(
                            interest_earned
                        ),
                        "other_income": self._format_decimal(
                            other_income
                        )
                    },
                    calculated_value=calculated,
                    reported_value=total_income
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula="Interest Earned + Other Income ≈ Total Income",
                    input_values={
                        "interest_earned": (
                            self._format_decimal(interest_earned)
                            if interest_earned is not None
                            else None
                        ),
                        "other_income": (
                            self._format_decimal(other_income)
                            if other_income is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=total_income
                )
            )

        # --------------------------------------------------------------
        # Check 2
        # --------------------------------------------------------------

        if (
            interest_expended is not None
            and operating_expenses is not None
            and provisions is not None
            and total_expenditure is not None
        ):
            calculated = (
                interest_expended
                + operating_expenses
                + provisions
            )

            checks.append(
                self._build_check(
                    formula=(
                        "Interest Expended + Operating Expenses + "
                        "Provisions ≈ Total Expenditure"
                    ),
                    input_values={
                        "interest_expended": self._format_decimal(
                            interest_expended
                        ),
                        "operating_expenses": self._format_decimal(
                            operating_expenses
                        ),
                        "provisions": self._format_decimal(
                            provisions
                        )
                    },
                    calculated_value=calculated,
                    reported_value=total_expenditure
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula=(
                        "Interest Expended + Operating Expenses + "
                        "Provisions ≈ Total Expenditure"
                    ),
                    input_values={
                        "interest_expended": (
                            self._format_decimal(interest_expended)
                            if interest_expended is not None
                            else None
                        ),
                        "operating_expenses": (
                            self._format_decimal(operating_expenses)
                            if operating_expenses is not None
                            else None
                        ),
                        "provisions": (
                            self._format_decimal(provisions)
                            if provisions is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=total_expenditure
                )
            )

        # --------------------------------------------------------------
        # Check 3
        # --------------------------------------------------------------

        if (
            total_income is not None
            and total_expenditure is not None
            and profit_before_minority is not None
        ):
            calculated = total_income - total_expenditure

            checks.append(
                self._build_check(
                    formula=(
                        "Total Income - Total Expenditure ≈ "
                        "Consolidated Net Profit Before Minority Interest"
                    ),
                    input_values={
                        "total_income": self._format_decimal(
                            total_income
                        ),
                        "total_expenditure": self._format_decimal(
                            total_expenditure
                        )
                    },
                    calculated_value=calculated,
                    reported_value=profit_before_minority
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula=(
                        "Total Income - Total Expenditure ≈ "
                        "Consolidated Net Profit Before Minority Interest"
                    ),
                    input_values={
                        "total_income": (
                            self._format_decimal(total_income)
                            if total_income is not None
                            else None
                        ),
                        "total_expenditure": (
                            self._format_decimal(total_expenditure)
                            if total_expenditure is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=profit_before_minority
                )
            )

        # --------------------------------------------------------------
        # Check 4
        # --------------------------------------------------------------

        if (
            profit_before_minority is not None
            and minority_interest is not None
            and attributable_group_profit is not None
        ):
            calculated = (
                profit_before_minority
                - minority_interest
            )

            checks.append(
                self._build_check(
                    formula=(
                        "Profit Before Minority Interest - Minority Interest "
                        "≈ Attributable Group Profit"
                    ),
                    input_values={
                        "profit_before_minority_interest": (
                            self._format_decimal(
                                profit_before_minority
                            )
                        ),
                        "minority_interest": self._format_decimal(
                            minority_interest
                        )
                    },
                    calculated_value=calculated,
                    reported_value=attributable_group_profit
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula=(
                        "Profit Before Minority Interest - Minority Interest "
                        "≈ Attributable Group Profit"
                    ),
                    input_values={
                        "profit_before_minority_interest": (
                            self._format_decimal(
                                profit_before_minority
                            )
                            if profit_before_minority is not None
                            else None
                        ),
                        "minority_interest": (
                            self._format_decimal(
                                minority_interest
                            )
                            if minority_interest is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=attributable_group_profit
                )
            )

        return {
            "status": self._final_status(checks),
            "checks": checks
        }

    # ------------------------------------------------------------------
    # CASH FLOW VALIDATION
    # ------------------------------------------------------------------

    def _validate_cash_flow_statement(self, extracted_data):
        """
        Validate cash flow relationships.

        1. Operating + Investing + Financing + FX
           ≈ Net Increase in Cash

        2. Opening Cash + Net Increase in Cash
           ≈ Closing Cash
        """

        values = self._all_values(extracted_data)

        operating = self._find_value(
            values,
            [
                "net cash from operating activities",
                "cash from operating activities",
                "operating activities",
                "operating",
                "net cash generated from operating activities",
            ],
            preferred_sources=["field", "table"]
        )

        investing = self._find_value(
            values,
            [
                "net cash from investing activities",
                "cash from investing activities",
                "investing activities",
                "investing",
                "net cash used in investing activities",
            ],
            preferred_sources=["field", "table"]
        )

        financing = self._find_value(
            values,
            [
                "net cash from financing activities",
                "cash from financing activities",
                "financing activities",
                "financing",
                "net cash used in financing activities",
            ],
            preferred_sources=["field", "table"]
        )

        fx = self._find_value(
            values,
            [
                "effect of exchange rate changes",
                "effect of exchange rate",
                "foreign exchange effect",
                "exchange rate changes",
                "fx effect",
                "fx",
            ],
            preferred_sources=["field", "table"]
        )

        net_increase = self._find_value(
            values,
            [
                "net increase in cash",
                "net increase in cash and cash equivalents",
                "increase in cash",
                "net change in cash",
                "net increase",
            ],
            preferred_sources=["field", "table"]
        )

        opening_cash = self._find_value(
            values,
            [
                "cash and cash equivalents at beginning of year",
                "cash and cash equivalents at beginning",
                "opening cash",
                "cash at beginning of year",
                "opening balance of cash",
                "cash and cash equivalents opening",
            ],
            preferred_sources=["field", "table"]
        )

        closing_cash = self._find_value(
            values,
            [
                "cash and cash equivalents at end of year",
                "cash and cash equivalents at end",
                "closing cash",
                "cash at end of year",
                "closing balance of cash",
                "cash and cash equivalents closing",
            ],
            preferred_sources=["field", "table"]
        )

        checks = []

        # --------------------------------------------------------------
        # Check 1
        # --------------------------------------------------------------

        if (
            operating is not None
            and investing is not None
            and financing is not None
            and net_increase is not None
        ):
            # FX is optional. If present, include it.
            calculated = (
                operating
                + investing
                + financing
            )

            if fx is not None:
                calculated += fx

            checks.append(
                self._build_check(
                    formula=(
                        "Operating + Investing + Financing + FX "
                        "≈ Net Increase in Cash"
                    ),
                    input_values={
                        "operating": self._format_decimal(operating),
                        "investing": self._format_decimal(investing),
                        "financing": self._format_decimal(financing),
                        "fx": (
                            self._format_decimal(fx)
                            if fx is not None
                            else None
                        )
                    },
                    calculated_value=calculated,
                    reported_value=net_increase
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula=(
                        "Operating + Investing + Financing + FX "
                        "≈ Net Increase in Cash"
                    ),
                    input_values={
                        "operating": (
                            self._format_decimal(operating)
                            if operating is not None
                            else None
                        ),
                        "investing": (
                            self._format_decimal(investing)
                            if investing is not None
                            else None
                        ),
                        "financing": (
                            self._format_decimal(financing)
                            if financing is not None
                            else None
                        ),
                        "fx": (
                            self._format_decimal(fx)
                            if fx is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=net_increase
                )
            )

        # --------------------------------------------------------------
        # Check 2
        # --------------------------------------------------------------

        if (
            opening_cash is not None
            and net_increase is not None
            and closing_cash is not None
        ):
            calculated = opening_cash + net_increase

            checks.append(
                self._build_check(
                    formula=(
                        "Opening Cash + Net Increase in Cash "
                        "≈ Closing Cash"
                    ),
                    input_values={
                        "opening_cash": self._format_decimal(
                            opening_cash
                        ),
                        "net_increase": self._format_decimal(
                            net_increase
                        )
                    },
                    calculated_value=calculated,
                    reported_value=closing_cash
                )
            )

        else:
            checks.append(
                self._build_check(
                    formula=(
                        "Opening Cash + Net Increase in Cash "
                        "≈ Closing Cash"
                    ),
                    input_values={
                        "opening_cash": (
                            self._format_decimal(opening_cash)
                            if opening_cash is not None
                            else None
                        ),
                        "net_increase": (
                            self._format_decimal(net_increase)
                            if net_increase is not None
                            else None
                        )
                    },
                    calculated_value=None,
                    reported_value=closing_cash
                )
            )

        return {
            "status": self._final_status(checks),
            "checks": checks
        }