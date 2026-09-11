from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from gemini_client import GeminiError
from tools.vision_tools import extract_structured_data, extract_text_from_image


def _uploaded_image(name="invoice.png", content=b"fake-image-bytes"):
    return SimpleNamespace(name=name, getvalue=lambda: content)


def _uploaded_png(name="invoice.png"):
    buffer = BytesIO()
    Image.new("RGB", (1200, 1600), "white").save(buffer, format="PNG")
    return _uploaded_image(name=name, content=buffer.getvalue())


def test_extract_text_from_image_uses_openrouter_qianfan_ocr_by_default(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("USE_GEMINI_VISION", raising=False)
    monkeypatch.delenv("OPENROUTER_VISION_MODEL", raising=False)

    captured = {"gemini_called": False}

    def unexpected_gemini_call(*args, **kwargs):
        captured["gemini_called"] = True
        raise AssertionError("Gemini vision should not run unless USE_GEMINI_VISION is enabled.")

    def fake_run_vision_action(*args, **kwargs):
        captured["kwargs"] = kwargs
        return {
            "ok": True,
            "task": "ocr",
            "raw_text": "Invoice ACME\nTotal 120.00",
            "structured": {
                "summary": "Merchant: ACME | Total: 120.00",
                "extracted_text": "Invoice ACME\nTotal 120.00",
                "answer": "Merchant: ACME | Total: 120.00",
            },
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        }

    monkeypatch.setattr("tools.vision_tools.post_generate_content", unexpected_gemini_call, raising=False)
    monkeypatch.setattr("tools.vision_tools.run_vision_action", fake_run_vision_action)

    result = extract_text_from_image(
        prompt="Extract structured data from this invoice",
        uploaded_image=_uploaded_image(),
        detected_language="english",
    )

    assert result["extracted_text"] == "Invoice ACME\nTotal 120.00"
    assert result["provider"] == "openrouter"
    assert result["model"] == "baidu/qianfan-ocr-fast:free"
    assert captured["kwargs"]["image_data_url"].startswith("data:image/png;base64,")
    assert captured["gemini_called"] is False


def test_extract_text_from_image_can_opt_into_gemini_for_uploaded_images(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("USE_GEMINI_VISION", "true")

    captured = {}

    def fake_post_generate_content(model, payload, timeout=None):
        captured["model"] = model
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "candidates": [
                {"content": {"parts": [{"text": "Invoice ACME\nTotal 120.00"}]}}
            ]
        }

    def unexpected_openrouter_fallback(**kwargs):
        raise AssertionError("OpenRouter vision fallback should not run when Gemini succeeds.")

    monkeypatch.setattr("tools.vision_tools.post_generate_content", fake_post_generate_content, raising=False)
    monkeypatch.setattr("tools.vision_tools.run_vision_action", unexpected_openrouter_fallback)

    result = extract_text_from_image(
        prompt="Extract structured data from this invoice",
        uploaded_image=_uploaded_image(),
        detected_language="english",
    )

    assert result["extracted_text"] == "Invoice ACME\nTotal 120.00"
    assert result["provider"] == "gemini"
    assert captured["model"] == "gemini-2.5-flash"
    assert captured["payload"]["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"


def test_extract_text_from_image_falls_back_to_openrouter_for_transient_gemini_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_VISION_FALLBACK_MODEL", "gemini-2.5-flash-lite")
    monkeypatch.setenv("USE_GEMINI_VISION", "true")

    calls = []

    def fake_post_generate_content(model, payload, timeout=None):
        calls.append(("gemini", model))
        raise GeminiError(
            'Gemini returned HTTP 503. Details: { "error": { "code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE" } }'
        )

    def fake_run_vision_action(*args, **kwargs):
        calls.append(("openrouter", kwargs.get("image_data_url")))
        return {
            "ok": True,
            "task": "ocr",
            "raw_text": "Invoice ACME\nTotal 120.00",
            "structured": {
                "summary": "Merchant: ACME | Total: 120.00",
                "extracted_text": "Invoice ACME\nTotal 120.00",
                "answer": "Merchant: ACME | Total: 120.00",
            },
        }

    monkeypatch.setattr("tools.vision_tools.post_generate_content", fake_post_generate_content, raising=False)
    monkeypatch.setattr("tools.vision_tools.run_vision_action", fake_run_vision_action)

    result = extract_text_from_image(
        prompt="Extract structured data from this invoice",
        uploaded_image=_uploaded_image(),
        detected_language="english",
    )

    assert result["summary"] == "Merchant: ACME | Total: 120.00"
    assert calls[0] == ("gemini", "gemini-2.5-flash")
    assert calls[1] == ("gemini", "gemini-2.5-flash-lite")
    assert calls[2][0] == "openrouter"


def test_extract_text_from_image_adds_gujarat_template_invoice_number(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    calls = []

    def fake_run_vision_action(*args, **kwargs):
        calls.append(("full", kwargs.get("image_data_url")))
        return {
            "ok": True,
            "task": "ocr",
            "raw_text": (
                '```json\n{"vendor":"GUJARAT FREIGHT TOOLS",'
                '"invoice_number":"33","date":"23-Jul-2025","items":[]}\n```'
            ),
            "structured": {
                "summary": "Gujarat invoice",
                "extracted_text": (
                    '```json\n{"vendor":"GUJARAT FREIGHT TOOLS",'
                    '"invoice_number":"33","date":"23-Jul-2025","items":[]}\n```'
                ),
                "answer": "",
            },
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        }

    def fake_call_openrouter_vision(prompt, image_data_url=None, image_url=None):
        calls.append(("template", prompt, image_data_url))
        return {
            "ok": True,
            "response": {
                "choices": [
                    {"message": {"content": "Invoice No. GST-3425-26"}}
                ]
            },
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        }

    monkeypatch.setattr("tools.vision_tools.run_vision_action", fake_run_vision_action)
    monkeypatch.setattr("tools.vision_tools.call_openrouter_vision", fake_call_openrouter_vision)

    result = extract_text_from_image(
        prompt="store data",
        uploaded_image=_uploaded_png(),
        detected_language="english",
    )

    assert "Vendor template invoice number evidence: Invoice No. GST-3425-26" in result["extracted_text"]
    assert "Vendor template invoice number evidence: Invoice No. GST-3425-26" in result["raw_text"]
    assert result["template_invoice_number"] == "GST-3425-26"
    assert result["template_provider"] == "openrouter"
    assert result["template_model"] == "baidu/qianfan-ocr-fast:free"
    assert calls[0][0] == "full"
    assert calls[1][0] == "template"
    assert calls[1][2].startswith("data:image/png;base64,")
    assert calls[1][1].startswith("Read only the cropped top-right invoice metadata area")


def test_extract_structured_data_returns_common_invoice_format():
    result = extract_structured_data(
        "\n".join(
            [
                "Gujarat Freight Tools",
                "Invoice Number: GST-3425-26",
                "Date: 23-07-2025",
                "Currency: INR",
                "Bosch All-in-One Metal Hand Tool Kit 1 2535.00 2535.00",
                "Subtotal 3805.00",
                "Tax 684.90",
                "Grand Total 4490.00",
            ]
        )
    )

    assert result["type"] == "invoice"
    assert result["vendor"] == "Gujarat Freight Tools"
    assert result["invoice_number"] == "GST-3425-26"
    assert result["date"] == "23-07-2025"
    assert result["currency"] == "INR"
    assert result["items"][0]["sr_no"] == 1
    assert result["items"][0]["name"] == "Bosch All-in-One Metal Hand Tool Kit"
    assert result["items"][0]["quantity"] == 1
    assert result["summary"]["subtotal"] == 3805.0
    assert result["summary"]["tax"] == 684.9
    assert result["summary"]["total_amount"] == 4490.0
    assert result["invoice"] == {
        "vendor": "Gujarat Freight Tools",
        "invoice_number": "GST-3425-26",
        "date": "23-07-2025",
        "currency": "INR",
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert result["purchases"][0] == {
        "sr_no": 1,
        "name": "Bosch All-in-One Metal Hand Tool Kit",
        "quantity": 1,
        "rate": 2535.0,
        "total": 2535.0,
    }


def test_extract_structured_data_parses_markdown_invoice_summary():
    result = extract_structured_data(
        "\n".join(
            [
                "The invoice contains the following data:",
                "*   **Invoice Number:** GST-3425-26",
                "*   **Invoice Date:** 23-Jul-2025",
                "*   **Supplier Name:** GUJARAT FREIGHT TOOLS",
                "*   Bosch All-in-One Metal Hand Tool Kit (Rate: 2,535.00, Taxable Value: 2,535.00)",
                "*   Taparia Universal Tool Kit (Rate: 1,270.00, Taxable Value: 1,270.00)",
                "*   **Total Taxable Value:** 3,805.00",
                "*   **IGST Amount:** 684.90",
                "*   **Total Amount:** 4,490.00",
            ]
        )
    )

    assert result["vendor"] == "GUJARAT FREIGHT TOOLS"
    assert result["invoice_number"] == "GST-3425-26"
    assert result["date"] == "23-Jul-2025"
    assert result["currency"] == "INR"
    assert result["items"] == [
        {
            "sr_no": 1,
            "name": "Bosch All-in-One Metal Hand Tool Kit",
            "quantity": 1,
            "rate": 2535.0,
            "total": 2535.0,
        },
        {
            "sr_no": 2,
            "name": "Taparia Universal Tool Kit",
            "quantity": 1,
            "rate": 1270.0,
            "total": 1270.0,
        },
    ]
    assert result["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert result["invoice"]["total_amount"] == 4490.0
    assert result["purchases"][1]["name"] == "Taparia Universal Tool Kit"


def test_extract_structured_data_parses_fenced_json_invoice():
    result = extract_structured_data(
        """```json
{
  "invoice_details": {
    "invoice_number": "GST-3425-26",
    "invoice_date": "23-Jul-2025"
  },
  "seller_details": {
    "company_name": "GUJARAT FREIGHT TOOLS"
  },
  "items": [
    {
      "sr_no": 1,
      "product_name": "Bosch All-in-One Metal Hand Tool Kit",
      "qty": "1 NOS",
      "rate": "2,535.00",
      "taxable_value": "2,535.00"
    },
    {
      "sr_no": 2,
      "product_name": "Taparia Universal Tool Kit",
      "qty": "1 NOS",
      "rate": "1,270.00",
      "taxable_value": "1,270.00"
    }
  ],
  "tax_summary": {
    "total_taxable_value": "3,805.00",
    "igst_amount": "684.90"
  },
  "total_amount": {
    "amount": "4,490.00"
  }
}
```"""
    )

    assert result["vendor"] == "GUJARAT FREIGHT TOOLS"
    assert result["invoice_number"] == "GST-3425-26"
    assert result["date"] == "23-Jul-2025"
    assert result["currency"] == "INR"
    assert result["items"][1]["name"] == "Taparia Universal Tool Kit"
    assert result["items"][1]["quantity"] == 1
    assert result["items"][1]["rate"] == 1270.0
    assert result["summary"]["subtotal"] == 3805.0
    assert result["summary"]["tax"] == 684.9
    assert result["summary"]["total_amount"] == 4490.0
    assert result["invoice"]["vendor"] == "GUJARAT FREIGHT TOOLS"
    assert result["purchases"][0]["total"] == 2535.0


def test_extract_structured_data_parses_common_json_summary():
    result = extract_structured_data(
        """```json
{
  "invoice_id": "26CORPP3939N1",
  "vendor": "Gujarat Freight Tools",
  "invoice_number": "GSTIN: 26CORPP3939N1",
  "date": "23-Jul-2025",
  "currency": "INR",
  "items": [
    {
      "sr_no": 1,
      "name": "Bosch All-in-One Metal Hand Tool Kit",
      "quantity": 1,
      "rate": 2535.0,
      "total": 2535.0
    },
    {
      "sr_no": 2,
      "name": "Taparia Universal Tool Kit",
      "quantity": 1,
      "rate": 1270.0,
      "total": 1270.0
    }
  ],
  "summary": {
    "subtotal": 3805.0,
    "tax": 684.9,
    "total_amount": 4490.0
  }
}
```"""
    )

    assert result["invoice_number"] == "GSTIN: 26CORPP3939N1"
    assert result["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert result["invoice"]["subtotal"] == 3805.0


def test_extract_structured_data_parses_multiline_markdown_invoice_details():
    result = extract_structured_data(
        "\n".join(
            [
                "The invoice contains the following data:",
                "",
                "**Invoice Details:**",
                "*   **Invoice No.:** GST-3425-26",
                "*   **Invoice Date:** 23-Jul-2025",
                "",
                "**Supplier Details:**",
                "*   **Company Name:** GUJARAT FREIGHT TOOLS",
                "",
                "**Products/Services:**",
                "1.  **Name:** Bosch All-in-One Metal Hand Tool Kit",
                "    *   **HSN / SAC:** 8302",
                "    *   **Qty:** 1 NOS",
                "    *   **Rate:** 2,535.00",
                "    *   **Taxable Value:** 2,535.00",
                "2.  **Name:** Taparia Universal Tool Kit",
                "    *   **HSN / SAC:** 8302",
                "    *   **Qty:** 1 NOS",
                "    *   **Rate:** 1,270.00",
                "    *   **Taxable Value:** 1,270.00",
                "",
                "**Tax Details:**",
                "*   **IGST (18.00 %):** 684.90",
                "",
                "**Totals:**",
                "*   **Sub Total:** 3,805.00",
                "*   **Grand Total:** 4,490.00",
            ]
        )
    )

    assert result["invoice"] == {
        "vendor": "GUJARAT FREIGHT TOOLS",
        "invoice_number": "GST-3425-26",
        "date": "23-Jul-2025",
        "currency": "INR",
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert result["purchases"] == [
        {
            "sr_no": 1,
            "name": "Bosch All-in-One Metal Hand Tool Kit",
            "quantity": 1,
            "rate": 2535.0,
            "total": 2535.0,
        },
        {
            "sr_no": 2,
            "name": "Taparia Universal Tool Kit",
            "quantity": 1,
            "rate": 1270.0,
            "total": 1270.0,
        },
    ]
