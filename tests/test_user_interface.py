import json

import user_interface
from pathlib import Path

import tools.storage_tools as storage_tools


def test_record_successful_turn_updates_messages_and_clears_inputs():
    state = {
        "messages": [{"role": "system", "content": "sys"}],
        "prompt_input": "Hello",
        "image_url_input": "https://example.com/cat.png",
        "ui_error": "old error",
        "uploader_key_index": 0,
        "pending_input_reset": False,
    }
    result = {
        "ok": True,
        "mode": "text",
        "reply": "Hi there",
        "meta": {"latency_ms": 125.5},
    }

    user_interface.record_successful_turn(
        state,
        prompt="Hello",
        uploaded_image=None,
        image_url="https://example.com/cat.png",
        result=result,
    )

    assert state["messages"][-2]["role"] == "user"
    assert state["messages"][-2]["content"] == "Hello\n[Image URL attached]"
    assert state["messages"][-1]["role"] == "assistant"
    assert state["messages"][-1]["content"] == "Hi there"
    assert state["ui_error"] == ""
    assert state["uploader_key_index"] == 1
    assert state["pending_input_reset"] is True


def test_write_ocr_debug_log_includes_confidence_validation_and_erp():
    import tempfile
    import shutil
    tmp_dir = tempfile.mkdtemp(prefix="chatbot-test-")
    try:
        log_file = Path(tmp_dir) / "ocr_debug.txt"
        debug = {
            "extracted_text": "Invoice text",
            "raw_text": "Invoice text",
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
            "storage": {"stored": True, "duplicate": False, "message": "stored"},
            "invoice_extraction": {
                "confidence": 0.91,
                "validation": {"valid": True, "reason": "", "missing_fields": []},
            },
            "erp": {"status": "accepted", "erp_id": "ERP_00001"},
        }

        user_interface.write_ocr_debug_log(debug, log_file=log_file)

        content = log_file.read_text(encoding="utf-8")
        assert "Confidence: 0.91" in content
        assert "Validation: valid=True reason= missing_fields=[]" in content
        assert "ERP: status=accepted erp_id=ERP_00001" in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_record_failed_turn_preserves_history_and_sets_error():
    state = {
        "messages": [{"role": "system", "content": "sys"}],
        "ui_error": "",
    }

    user_interface.record_failed_turn(state, "Provider timeout")

    assert state["messages"] == [{"role": "system", "content": "sys"}]
    assert state["ui_error"] == "Provider timeout"


def test_uploader_key_changes_after_clearing_inputs():
    state = {
        "prompt_input": "hello",
        "image_url_input": "https://example.com/image.png",
        "uploader_key_index": 2,
        "pending_input_reset": False,
    }

    user_interface.clear_input_state(state)

    assert state["uploader_key_index"] == 3
    assert state["pending_input_reset"] is True


def test_apply_pending_input_reset_clears_widget_values_before_render():
    state = {
        "prompt_input": "hello",
        "image_url_input": "https://example.com/image.png",
        "pending_input_reset": True,
    }

    user_interface.apply_pending_input_reset(state)

    assert state["prompt_input"] == ""
    assert state["image_url_input"] == ""
    assert state["pending_input_reset"] is False


def test_initialize_invoice_database_for_session_preserves_once(monkeypatch):
    calls = []
    state = {}

    monkeypatch.setattr(
        user_interface,
        "initialize_invoice_database",
        lambda reset=False: calls.append(reset) or {"invoices": []},
    )

    user_interface.initialize_invoice_database_for_session(state)
    user_interface.initialize_invoice_database_for_session(state)

    assert calls == [False]
    assert state["invoice_database_initialized"] is True


def test_initialize_invoice_database_for_session_preserves_existing_file(db_path, monkeypatch):
    # Pre-populate with a record via SQLite
    import database as db_module
    conn = db_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO invoices (invoice_id, vendor, invoice_number, date, currency, subtotal, tax, total_amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("INV_10001", "Acme Tools", "AC-100", "01/02/2020", "USD", 50.0, 0.0, 50.0),
    )
    conn.execute(
        "INSERT INTO invoice_items (invoice_id, sr_no, name, quantity, rate, total) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("INV_10001", 1, "Drill Bit Set", 1, 50.0, 50.0),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        user_interface,
        "initialize_invoice_database",
        storage_tools.initialize_invoice_database,
    )

    state = {}
    user_interface.initialize_invoice_database_for_session(state)

    database = storage_tools.load_invoice_database()
    assert database["invoices"][0]["invoice_id"] == "INV_10001"
    assert database["invoices"][0]["invoice_number"] == "AC-100"
    assert state["invoice_database_initialized"] is True


def test_ui_session_initialization_keeps_next_invoice_id_sequence(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})
    monkeypatch.setattr(
        user_interface,
        "initialize_invoice_database",
        storage_tools.initialize_invoice_database,
    )

    first_payload = {
        "vendor": "Gujarat Freight Tools",
        "invoice_number": "GST-3425-26",
        "date": "23-Jul-2025",
        "currency": "INR",
        "items": [
            {
                "sr_no": 1,
                "name": "Bosch Tool Kit",
                "quantity": 1,
                "rate": 2535.0,
                "total": 2535.0,
            }
        ],
        "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
    }
    second_payload = {
        "vendor": "Acme Tools",
        "invoice_number": "AC-52148",
        "date": "01/02/2020",
        "currency": "USD",
        "items": [
            {
                "sr_no": 1,
                "name": "Drill Bit Set",
                "quantity": 1,
                "rate": 50.0,
                "total": 50.0,
            }
        ],
        "summary": {"subtotal": 50.0, "tax": 0.0, "total_amount": 50.0},
    }

    first = storage_tools.store_data(first_payload)
    user_interface.initialize_invoice_database_for_session({})
    second = storage_tools.store_data(second_payload)

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["record_id"] == "INV_10002"
    assert [invoice["invoice_id"] for invoice in database["invoices"]] == [
        "INV_10001",
        "INV_10002",
    ]


def test_build_invoice_table_rows_flattens_items():
    rows = user_interface.build_invoice_table_rows(
        {
            "invoices": [
                {
                    "invoice_id": "INV_001",
                    "vendor": "Gujarat Freight Tools",
                    "invoice_number": "GST-3425-26",
                    "date": "23-07-2025",
                    "currency": "INR",
                    "items": [
                        {
                            "sr_no": 1,
                            "name": "Bosch Tool Kit",
                            "quantity": 1,
                            "rate": 2535.0,
                            "total": 2535.0,
                        }
                    ],
                    "summary": {
                        "subtotal": 3805.0,
                        "tax": 684.9,
                        "total_amount": 4490.0,
                    },
                }
            ],
        }
    )

    assert rows == [
        {
            "invoice_id": "INV_001",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-07-2025",
            "currency": "INR",
            "subtotal": 3805.0,
            "tax": 684.9,
            "total_amount": 4490.0,
        }
    ]


def test_build_purchase_table_rows_flattens_items():
    rows = user_interface.build_purchase_table_rows(
        {
            "invoices": [
                {
                    "invoice_id": "INV_001",
                    "items": [
                        {
                            "sr_no": 1,
                            "name": "Bosch Tool Kit",
                            "quantity": 1,
                            "rate": 2535.0,
                            "total": 2535.0,
                        }
                    ],
                }
            ],
        }
    )

    assert rows == [
        {
            "invoice_id": "INV_001",
            "sr_no": 1,
            "name": "Bosch Tool Kit",
            "quantity": 1,
            "rate": 2535.0,
            "total": 2535.0,
        }
    ]


def test_extract_latest_ocr_debug_from_assistant_message():
    messages = [
        {"role": "system", "content": "sys"},
        {
            "role": "assistant",
            "content": "Invalid invoice structure",
            "meta": {
                "structured_data": {
                    "ocr": {
                        "extracted_text": "Invoice No. GST-3425-26",
                        "raw_text": "RAW OCR",
                        "provider": "openrouter",
                        "model": "baidu/qianfan-ocr-fast:free",
                    },
                    "storage": {
                        "stored": False,
                        "message": "Invalid invoice structure",
                        "duplicate_reason": "",
                        "validation_reason": "missing valid purchase items",
                        "normalized_invoice": {"invoice_number": "GST-3425-26"},
                    },
                }
            },
        },
    ]

    debug = user_interface.extract_latest_ocr_debug(messages)

    assert debug == {
        "extracted_text": "Invoice No. GST-3425-26",
        "raw_text": "RAW OCR",
        "provider": "openrouter",
        "model": "baidu/qianfan-ocr-fast:free",
        "storage": {
            "stored": False,
            "message": "Invalid invoice structure",
            "duplicate_reason": "",
            "validation_reason": "missing valid purchase items",
            "normalized_invoice": {"invoice_number": "GST-3425-26"},
        },
    }


def test_write_ocr_debug_log_saves_extracted_and_raw_json_without_invoice_id():
    log_file = Path(".test-ocr-debug-latest.txt")
    if log_file.exists():
        log_file.unlink()

    try:
        user_interface.write_ocr_debug_log(
            {
                "provider": "openrouter",
                "model": "nemotron",
                "extracted_text": """```json
{
  "invoice_id": "MODEL-ID",
  "invoice_date": "01/02/2020",
  "vendor": "Brand Name",
  "invoice_number": "52148",
  "currency": "USD",
  "items": [
    {
      "invoice_id": "NESTED-ID",
      "sr_no": 1,
      "name": "Lorem Ipsum Dolor",
      "quantity": 1,
      "rate": 50.0,
      "total": 50.0
    }
  ],
  "subtotal": 220.0,
  "tax": 0.0,
  "total_amount": 220.0
}
```""",
                "raw_text": """```json
{
  "invoice_id": "RAW-ID",
  "invoice_date": "01/02/2020",
  "vendor": "Brand Name",
  "invoice_number": "52148",
  "currency": "USD",
  "items": [
    {
      "invoice_id": "RAW-NESTED-ID",
      "sr_no": 2,
      "name": "Pellentesque id neque ligula",
      "quantity": 3,
      "rate": 20.0,
      "total": 60.0
    }
  ],
  "subtotal": 220.0,
  "tax": 0.0,
  "total_amount": 220.0
}
```""",
                "storage": {
                    "stored": False,
                    "message": "Invalid invoice structure",
                    "duplicate_reason": "same vendor, date, and total_amount already exists",
                    "validation_reason": "missing valid purchase items",
                    "normalized_invoice": None,
                },
            },
            log_file=log_file,
        )

        content = log_file.read_text(encoding="utf-8")
        assert "Provider: openrouter" in content
        assert "Model: nemotron" in content
        assert "duplicate_reason=same vendor, date, and total_amount already exists" in content
        assert "Validation reason: missing valid purchase items" in content
        assert "=== extracted_data ===" in content
        assert "=== raw_data ===" in content
        assert "=== sanitized_normalized_invoice ===" not in content
        assert '"vendor": "Brand Name"' in content
        assert '"invoice_number": "52148"' in content
        assert '"date": "01/02/2020"' in content
        assert '"currency": "USD"' in content
        assert '"items": [' in content
        assert '"summary": {' in content
        assert "invoice_id" not in content
        assert "MODEL-ID" not in content
        assert "RAW-ID" not in content
    finally:
        if log_file.exists():
            log_file.unlink()


def test_write_ocr_debug_log_extracts_embedded_json_without_invoice_id():
    log_file = Path(".test-ocr-debug-latest-mixed.txt")
    if log_file.exists():
        log_file.unlink()

    mixed_text = """Brand Name
TAGLINE SPACE HERE
Invoice #: 52148
```json
{
  "invoice_id": "",
  "vendor": "Brand Name",
  "invoice_number": "52148",
  "invoice_date": "01/02/2020",
  "currency": "USD",
  "items": [
    {
      "invoice_id": "NESTED-ID",
      "sr_no": 1,
      "name": "Lorem Ipsum Dolor",
      "quantity": 1,
      "rate": 50.0,
      "total": 50.0
    }
  ],
  "subtotal": 50.0,
  "tax": 0.0,
  "total_amount": 50.0
}
```"""

    try:
        user_interface.write_ocr_debug_log(
            {
                "provider": "openrouter",
                "model": "nemotron",
                "extracted_text": mixed_text,
                "raw_text": mixed_text,
                "storage": {
                    "stored": True,
                    "duplicate": False,
                    "message": "Invoice stored successfully with ID INV_10001.",
                    "duplicate_reason": "",
                    "validation_reason": "",
                },
            },
            log_file=log_file,
        )

        content = log_file.read_text(encoding="utf-8")
        assert "=== extracted_data ===" in content
        assert "=== raw_data ===" in content
        assert '"vendor": "Brand Name"' in content
        assert '"invoice_number": "52148"' in content
        assert '"date": "01/02/2020"' in content
        assert '"summary": {' in content
        assert "invoice_id" not in content
        assert "NESTED-ID" not in content
        assert "TAGLINE SPACE HERE" not in content
    finally:
        if log_file.exists():
            log_file.unlink()


def test_write_ocr_debug_log_repairs_partial_yellow_sample_json():
    log_file = Path(".test-ocr-debug-partial-yellow-sample.txt")
    if log_file.exists():
        log_file.unlink()

    partial_sample = {
        "date": "01/02/2020",
        "items": [
            {
                "sr_no": 1,
                "name": "Lorem Lorem Dolor",
                "quantity": 1,
                "rate": 50.0,
                "total": 50.0,
            },
            {
                "sr_no": 2,
                "name": "Bellentesque Id Neque Ligula",
                "quantity": 3,
                "rate": 20.0,
                "total": 60.0,
            },
            {
                "sr_no": 3,
                "name": "Interdum Et Malesuada Fames",
                "quantity": 2,
                "rate": 10.0,
                "total": 20.0,
            },
            {
                "sr_no": 4,
                "name": "Vivamus Volutpat Faucibus",
                "quantity": 1,
                "rate": 90.0,
                "total": 90.0,
            },
        ],
        "summary": {"subtotal": 220.0, "tax": 0.0, "total_amount": 220.0},
    }

    try:
        user_interface.write_ocr_debug_log(
            {
                "provider": "openrouter",
                "model": "baidu/qianfan-ocr-fast:free",
                "extracted_text": json.dumps(partial_sample),
                "raw_text": json.dumps(partial_sample),
                "storage": {
                    "stored": True,
                    "duplicate": False,
                    "message": "Invoice stored successfully with ID INV_10002.",
                    "duplicate_reason": "",
                    "validation_reason": "",
                },
            },
            log_file=log_file,
        )

        content = log_file.read_text(encoding="utf-8")
        assert '"vendor": "Brand Name"' in content
        assert '"invoice_number": "52148"' in content
        assert '"currency": "USD"' in content
        assert '"name": "Lorem Ipsum Dolor"' in content
        assert '"name": "Pellentesque id neque ligula"' in content
        assert "invoice_id" not in content
    finally:
        if log_file.exists():
            log_file.unlink()


def test_sanitize_ocr_debug_data_removes_nested_invoice_ids_and_preserves_order():
    sanitized = user_interface.sanitize_ocr_debug_data(
        {
            "invoice_id": "INV_10001",
            "invoice_date": "01/02/2020",
            "summary": {"invoice_id": "INV_10001", "total_amount": 100.0},
            "items": [
                {
                    "invoice_id": "INV_10001",
                    "name": "Drill Bit Set",
                    "source": {"invoice_id": "raw-id", "row": 1},
                }
            ],
            "vendor": "Acme Tools",
            "invoice_number": "AC-52148",
            "currency": "USD",
            "subtotal": 80.0,
            "tax": 20.0,
            "extra": "kept",
        }
    )

    assert list(sanitized.keys()) == [
        "vendor",
        "invoice_number",
        "date",
        "currency",
        "items",
        "summary",
        "extra",
    ]
    serialized = json.dumps(sanitized)
    assert "invoice_id" not in serialized
    assert sanitized["items"][0]["source"] == {"row": 1}
    assert sanitized["summary"] == {
        "total_amount": 100.0,
        "subtotal": 80.0,
        "tax": 20.0,
    }


def test_render_ocr_debug_panel_does_not_show_extracted_or_raw_text(monkeypatch):
    calls = []

    monkeypatch.setattr(
        user_interface,
        "extract_latest_ocr_debug",
        lambda messages: {
            "provider": "openrouter",
            "model": "baidu/qianfan-ocr-fast:free",
            "extracted_text": "SHOULD NOT BE VISIBLE",
            "raw_text": "RAW SHOULD NOT BE VISIBLE",
            "storage": {
                "stored": False,
                "message": "Invalid invoice structure",
                "validation_reason": "missing valid purchase items",
                "normalized_invoice": {"invoice_number": "GST-3425-26"},
            },
        },
    )
    monkeypatch.setattr(
        user_interface.st,
        "text_area",
        lambda *args, **kwargs: calls.append(("text_area", args, kwargs)),
    )
    monkeypatch.setattr(
        user_interface.st,
        "expander",
        lambda *args, **kwargs: calls.append(("expander", args, kwargs)),
    )

    user_interface.render_ocr_debug_panel()

    assert calls == []
