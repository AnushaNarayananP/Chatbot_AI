from pipeline.classifier import classify_request
from pipeline.executor import execute_pipeline
from pipeline.models import IntentType, PipelineRequest


def test_classifier_detects_translation_intent():
    request = PipelineRequest(prompt="Translate this text to Hindi")

    result = classify_request(request)

    assert result.intent == IntentType.TRANSLATION
    assert result.target_language == "hindi"


def test_classifier_detects_invoice_extraction_intent():
    request = PipelineRequest(prompt="Extract vendor, amount, and date from this invoice")

    result = classify_request(request)

    assert result.intent == IntentType.DATA_EXTRACTION


def test_executor_runs_summarization_flow(monkeypatch):
    request = PipelineRequest(prompt="Summarize this text", messages=[])

    monkeypatch.setattr(
        "tools.text_tools.answer_question",
        lambda question, context="": {"answer": f"Answered: {question}", "context": context},
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.intent == "summarization"
    assert response.reply == "Answered: Summarize this text"
    assert [tool_call.name for tool_call in response.tool_calls] == ["answer_question"]


def test_executor_runs_image_extraction_and_storage_flow(monkeypatch):
    request = PipelineRequest(
        prompt="Store the invoice details",
        uploaded_image=object(),
    )

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Invoice text",
            "extracted_text": "\n".join(
                [
                    "Acme Tools",
                    "Invoice No. AC-100",
                    "Date 2025-01-01",
                    "Item Description Price Qty Total",
                    "1 Notebook 50.00 2 100.00",
                    "Tax 20.00",
                    "Total 120.00",
                ]
            ),
            "raw_text": "\n".join(
                [
                    "Acme Tools",
                    "Invoice No. AC-100",
                    "Date 2025-01-01",
                    "Item Description Price Qty Total",
                    "1 Notebook 50.00 2 100.00",
                    "Tax 20.00",
                    "Total 120.00",
                ]
            ),
        },
    )
    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: {
            "stored": True,
            "duplicate": False,
            "record_id": "task-1",
            "record": {"id": "task-1", **payload},
        },
    )
    monkeypatch.setattr(
        "tools.erp_tools.push_invoice_to_erp",
        lambda payload: {
            "status": "accepted",
            "erp_id": "ERP_00001",
            "accepted_at": "2026-05-21T00:00:00Z",
            "payload": payload,
        },
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.intent == "workflow_trigger"
    assert [tool_call.name for tool_call in response.tool_calls] == [
        "extract_text_from_image",
        "extract_invoice_data",
        "store_data",
        "push_invoice_to_erp",
    ]
    assert response.structured_data["storage"]["record_id"] == "task-1"
    assert response.structured_data["erp"]["erp_id"] == "ERP_00001"


def test_executor_runs_invoice_image_extraction_storage_and_erp_flow(monkeypatch):
    request = PipelineRequest(
        prompt="Extract vendor, amount, GST, date, and items from this invoice",
        uploaded_image=object(),
    )
    invoice_text = "\n".join(
        [
            "GUJARAT FREIGHT TOOLS",
            "Invoice No. GST-3425-26",
            "Invoice Date 23-Jul-2025",
            "Sr. No. Name of Product / Service HSN / SAC Qty Rate Taxable Value",
            "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
            "IGST (18.00 %) 456.30",
            "Total 1 NOS Rs. 2,991.30",
        ]
    )
    stored_payloads = []
    erp_payloads = []

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Invoice text",
            "extracted_text": invoice_text,
            "raw_text": invoice_text,
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        },
    )
    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: stored_payloads.append(payload)
        or {
            "stored": True,
            "duplicate": False,
            "record_id": "INV_10001",
            "invoice_row": {"invoice_id": "INV_10001"},
        },
    )
    monkeypatch.setattr(
        "tools.erp_tools.push_invoice_to_erp",
        lambda payload: erp_payloads.append(payload)
        or {
            "status": "accepted",
            "erp_id": "ERP_00001",
            "accepted_at": "2026-05-21T00:00:00Z",
            "payload": payload,
        },
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.intent == "data_extraction"
    assert [tool_call.name for tool_call in response.tool_calls] == [
        "extract_text_from_image",
        "extract_invoice_data",
        "store_data",
        "push_invoice_to_erp",
    ]
    assert response.structured_data["invoice_extraction"]["validation"]["valid"] is True
    assert response.structured_data["invoice_extraction"]["confidence"] >= 0.8
    assert stored_payloads[0]["invoice_number"] == "GST-3425-26"
    assert erp_payloads[0]["invoice_number"] == "GST-3425-26"
    assert response.structured_data["erp"]["erp_id"] == "ERP_00001"
    assert "ERP_00001" in response.reply


def test_executor_does_not_store_or_push_invalid_invoice_extraction(monkeypatch):
    request = PipelineRequest(
        prompt="Extract vendor, amount, GST, date, and items from this invoice",
        uploaded_image=object(),
    )
    calls = {"store": 0, "erp": 0}

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Invoice text",
            "extracted_text": "Acme Tools\nInvoice No. AC-100",
            "raw_text": "Acme Tools\nInvoice No. AC-100",
        },
    )
    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: calls.__setitem__("store", calls["store"] + 1),
    )
    monkeypatch.setattr(
        "tools.erp_tools.push_invoice_to_erp",
        lambda payload: calls.__setitem__("erp", calls["erp"] + 1),
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.structured_data["invoice_extraction"]["validation"]["valid"] is False
    assert calls == {"store": 0, "erp": 0}
    assert "missing date, items, amount" in response.reply


def test_executor_does_not_push_duplicate_invoice_to_erp(monkeypatch):
    request = PipelineRequest(
        prompt="Store the invoice details",
        uploaded_image=object(),
    )
    invoice_text = "\n".join(
        [
            "Acme Tools",
            "Invoice No. AC-100",
            "Date 21/05/2026",
            "Item Description Price Qty Total",
            "1 Notebook 50.00 2 100.00",
            "Total 100.00",
        ]
    )
    erp_calls = []

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Invoice text",
            "extracted_text": invoice_text,
            "raw_text": invoice_text,
        },
    )
    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: {
            "stored": False,
            "duplicate": True,
            "duplicate_reason": "invoice_number already exists",
            "duplicate_type": "strong",
            "existing_invoice": {"invoice_id": "INV_10001", "invoice_number": "AC-100"},
            "message": "Duplicate invoice detected. This invoice was not stored.",
        },
    )
    monkeypatch.setattr(
        "tools.erp_tools.push_invoice_to_erp",
        lambda payload: erp_calls.append(payload),
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.structured_data["storage"]["duplicate"] is True
    assert "erp" not in response.structured_data
    assert erp_calls == []


def test_executor_rejects_incomplete_invoice_json_before_storage(monkeypatch):
    request = PipelineRequest(
        prompt="Store the invoice details",
        uploaded_image=object(),
    )
    calls = []

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Invoice text",
            "extracted_text": '{"invoice_number":"GST-3425-26"}',
            "raw_text": '{"invoice_number":"GST-3425-26"}',
        },
    )

    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: calls.append(payload),
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.reply == "Invalid invoice structure\nReason: missing date, items, amount"
    assert calls == []
    assert response.structured_data["storage"]["stored"] is False
    assert response.structured_data["validation"]["missing_fields"] == [
        "date",
        "items",
        "amount",
    ]


def test_executor_skips_storage_when_ocr_text_is_none(monkeypatch):
    request = PipelineRequest(
        prompt="Store the invoice details",
        uploaded_image=object(),
    )
    store_calls = []

    monkeypatch.setattr(
        "tools.vision_tools.extract_text_from_image",
        lambda **kwargs: {
            "task": "ocr",
            "summary": "Merchant: None",
            "extracted_text": "None",
            "raw_text": "None",
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
        },
    )
    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: store_calls.append(payload) or {"stored": True},
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.reply == "OCR did not return readable invoice text. Please retry the image or use a clearer image."
    assert store_calls == []
    assert response.structured_data["storage"]["validation_reason"] == "empty OCR text"


def test_executor_invalid_storage_reply(monkeypatch):
    request = PipelineRequest(prompt="Store this invoice text")

    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: {
            "stored": False,
            "message": "Could not create a valid invoice record from the extracted text.",
            "database_file": "chatbot.db",
        },
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.reply == "Could not create a valid invoice record from the extracted text."


def test_executor_invalid_storage_reply_includes_validation_reason(monkeypatch):
    request = PipelineRequest(prompt="Store this invoice text")

    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: {
            "stored": False,
            "duplicate": False,
            "message": "Invalid invoice structure",
            "validation_reason": "template/sample invoice is not a real invoice",
            "database_file": "chatbot.db",
        },
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.reply == (
        "Invalid invoice structure\n"
        "Reason: template/sample invoice is not a real invoice"
    )


def test_executor_duplicate_storage_reply(monkeypatch):
    request = PipelineRequest(prompt="Store this invoice text")

    monkeypatch.setattr(
        "tools.storage_tools.store_data",
        lambda payload: {
            "stored": False,
            "duplicate": True,
            "duplicate_reason": "invoice_number already exists",
            "duplicate_type": "strong",
            "existing_invoice": {
                "invoice_id": "INV_10001",
                "invoice_number": "AC-100",
            },
            "new_invoice": {"invoice_number": "AC-100"},
            "message": "Duplicate invoice detected. This invoice was not stored.",
        },
    )

    response = execute_pipeline(request)

    assert response.ok is True
    assert response.reply == (
        "Duplicate invoice detected. This invoice was not stored.\n"
        "Reason: invoice_number already exists\n"
        "Existing invoice ID: INV_10001\n"
        "Existing invoice number: AC-100"
    )
