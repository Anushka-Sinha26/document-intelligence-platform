from app.services.financial_validation_service import FinancialValidationService


def test_invoice_validation_pass():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {"name": "Subtotal", "value": "10000.00"},
            {"name": "Tax", "value": "1800.00"},
            {"name": "Total", "value": "11800.00"},
        ]
    }

    result = service.validate("invoice", extracted_data)

    assert result["status"] == "PASS"
    assert len(result["checks"]) == 1

    check = result["checks"][0]

    assert check["calculated_value"] == "11800.00"
    assert check["reported_value"] == "11800.00"
    assert check["variance"] == "0.00"
    assert check["status"] == "PASS"


def test_invoice_validation_failure():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {"name": "Subtotal", "value": "804.00"},
            {"name": "Sales Tax", "value": "63.47"},
            {"name": "S&H", "value": "50.00"},
            {"name": "Total Due", "value": "916.47"},
        ]
    }

    result = service.validate("invoice", extracted_data)

    assert result["status"] == "FAIL"
    assert len(result["checks"]) == 1

    check = result["checks"][0]

    assert check["calculated_value"] == "917.47"
    assert check["reported_value"] == "916.47"
    assert check["variance"] == "1.00"
    assert check["status"] == "FAIL"


def test_balance_sheet_validation_pass():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Total Assets",
                "value": "4908040.84",
            },
            {
                "name": "Total Capital and Liabilities",
                "value": "4908040.84",
            },
        ]
    }

    result = service.validate("balance_sheet", extracted_data)

    assert result["status"] == "PASS"
    assert len(result["checks"]) == 1

    check = result["checks"][0]

    assert check["calculated_value"] == "4908040.84"
    assert check["reported_value"] == "4908040.84"
    assert check["variance"] == "0.00"
    assert check["status"] == "PASS"


def test_balance_sheet_validation_failure():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Total Assets",
                "value": "1000.00",
            },
            {
                "name": "Total Capital and Liabilities",
                "value": "900.00",
            },
        ]
    }

    result = service.validate("balance_sheet", extracted_data)

    assert result["status"] == "FAIL"
    assert len(result["checks"]) == 1

    check = result["checks"][0]

    assert check["calculated_value"] == "1000.00"
    assert check["reported_value"] == "900.00"
    assert check["variance"] == "100.00"
    assert check["status"] == "FAIL"


def test_profit_and_loss_validation_pass():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Interest Earned",
                "value": "348615.15",
            },
            {
                "name": "Other Income",
                "value": "146847.66",
            },
            {
                "name": "Total Income",
                "value": "495462.81",
            },
            {
                "name": "Interest Expended",
                "value": "185491.23",
            },
            {
                "name": "Operating Expenses",
                "value": "181173.91",
            },
            {
                "name": "Provisions",
                "value": "49578.21",
            },
            {
                "name": "Total Expenditure",
                "value": "416243.35",
            },
            {
                "name": "Consolidated Net Profit for the Year Before Minority Interest",
                "value": "79219.46",
            },
            {
                "name": "Minority Interest",
                "value": "3193.49",
            },
            {
                "name": "Consolidated Net Profit for the Year Attributable to the Group",
                "value": "76025.97",
            },
        ]
    }

    result = service.validate("profit_and_loss", extracted_data)

    assert result["status"] == "PASS"
    assert len(result["checks"]) == 4

    for check in result["checks"]:
        assert check["status"] == "PASS"


def test_profit_and_loss_validation_missing_field():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Interest Earned",
                "value": "100.00",
            },
            {
                "name": "Other Income",
                "value": "50.00",
            },
            {
                "name": "Total Income",
                "value": "150.00",
            },
        ]
    }

    result = service.validate("profit_and_loss", extracted_data)

    assert result["status"] == "PASS"

    assert result["checks"][0]["status"] == "PASS"

    for check in result["checks"][1:]:
        assert check["status"] == "NOT_APPLICABLE"


def test_cash_flow_validation_pass():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Net Cash Flow from Operating Activities",
                "value": "113506.38",
            },
            {
                "name": "Net Cash Flow from Investing Activities",
                "value": "6362.72",
            },
            {
                "name": "Net Cash Flow from Financing Activities",
                "value": "-59004.85",
            },
            {
                "name": "Effect of Foreign Exchange Rate Changes",
                "value": "1113.90",
            },
            {
                "name": "Net Increase in Cash and Cash Equivalents",
                "value": "61978.15",
            },
            {
                "name": "Cash and Cash Equivalents at Beginning of the Year",
                "value": "249947.90",
            },
            {
                "name": "Cash and Cash Equivalents at End of the Year",
                "value": "311926.05",
            },
        ]
    }

    result = service.validate("cash_flow_statement", extracted_data)

    assert result["status"] == "PASS"
    assert len(result["checks"]) == 2

    for check in result["checks"]:
        assert check["status"] == "PASS"


def test_cash_flow_validation_failure():
    service = FinancialValidationService()

    extracted_data = {
        "fields": [
            {
                "name": "Net Cash Flow from Operating Activities",
                "value": "100.00",
            },
            {
                "name": "Net Cash Flow from Investing Activities",
                "value": "-20.00",
            },
            {
                "name": "Net Cash Flow from Financing Activities",
                "value": "10.00",
            },
            {
                "name": "Effect of Foreign Exchange Rate Changes",
                "value": "5.00",
            },
            {
                "name": "Net Increase in Cash and Cash Equivalents",
                "value": "200.00",
            },
            {
                "name": "Cash and Cash Equivalents at Beginning of the Year",
                "value": "500.00",
            },
            {
                "name": "Cash and Cash Equivalents at End of the Year",
                "value": "700.00",
            },
        ]
    }

    result = service.validate("cash_flow_statement", extracted_data)

    assert result["status"] == "FAIL"

    assert any(
        check["status"] == "FAIL"
        for check in result["checks"]
    )