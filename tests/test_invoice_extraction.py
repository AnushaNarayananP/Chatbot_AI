from tools.invoice_tools import extract_invoice_data, validate_invoice_extraction


def _gst_invoice_text():
    return "\n".join(
        [
            "GUJARAT FREIGHT TOOLS",
            "Invoice No. GST-3425-26",
            "Invoice Date 23-Jul-2025",
            "Sr. No. Name of Product / Service HSN / SAC Qty Rate Taxable Value",
            "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
            "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
            "IGST (18.00 %) 684.90",
            "Total 2 NOS Rs. 4,490.00",
        ]
    )


def test_extract_invoice_data_returns_validated_common_shape_with_confidence():
    result = extract_invoice_data(
        {
            "extracted_text": _gst_invoice_text(),
            "raw_text": _gst_invoice_text(),
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        }
    )

    assert result["type"] == "invoice"
    assert result["vendor"] == "Gujarat Freight Tools"
    assert result["invoice_number"] == "GST-3425-26"
    assert result["date"] == "23-Jul-2025"
    assert result["currency"] == "INR"
    assert result["amount"] == 4490.0
    assert result["gst"] == {
        "igst": 684.9,
        "cgst": 0.0,
        "sgst": 0.0,
        "total": 684.9,
    }
    assert [item["name"] for item in result["items"]] == [
        "Bosch All-in-One Metal Hand Tool Kit",
        "Taparia Universal Tool Kit",
    ]
    assert result["validation"] == {"valid": True, "reason": "", "missing_fields": []}
    assert result["confidence"] >= 0.85
    assert result["field_confidence"]["vendor"] >= 0.9
    assert result["field_confidence"]["items"] >= 0.9


def test_validate_invoice_extraction_reports_missing_required_fields():
    result = validate_invoice_extraction(
        {
            "vendor": "Acme Tools",
            "invoice_number": "",
            "date": "",
            "items": [],
            "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 0.0},
        }
    )

    assert result["valid"] is False
    assert result["missing_fields"] == ["invoice_number", "date", "items", "amount"]
    assert result["reason"] == "missing invoice_number, date, items, amount"


def test_extract_invoice_data_handles_hindi_gst_labels():
    result = extract_invoice_data(
        "\n".join(
            [
                "विक्रेता नाम: Bharat Stores",
                "बिल संख्या: BS-101",
                "दिनांक: 21/05/2026",
                "वस्तु विवरण मात्रा दर कुल",
                "1 Notebook 2 50.00 100.00",
                "सीजीएसटी 9.00",
                "एसजीएसटी 9.00",
                "कुल राशि 118.00",
            ]
        )
    )

    assert result["vendor"] == "Bharat Stores"
    assert result["invoice_number"] == "BS-101"
    assert result["date"] == "21/05/2026"
    assert result["gst"]["cgst"] == 9.0
    assert result["gst"]["sgst"] == 9.0
    assert result["gst"]["total"] == 18.0
    assert result["validation"]["valid"] is True
