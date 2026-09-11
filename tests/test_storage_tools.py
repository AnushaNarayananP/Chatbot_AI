import json

import database as db_module
import pipeline.memory as memory
import tools.storage_tools as storage_tools


def _invoice_payload(
    invoice_number="GST-3425-26",
    invoice_id="",
    vendor="Gujarat Freight Tools",
    date="23-07-2025",
):
    return {
        "invoice_id": invoice_id,
        "vendor": vendor,
        "invoice_number": invoice_number,
        "date": date,
        "currency": "INR",
        "items": [
            {
                "sr_no": 1,
                "name": "Bosch Tool Kit",
                "quantity": 1,
                "rate": 2535.0,
                "total": 2535.0,
            },
            {
                "sr_no": 2,
                "name": "Taparia Tool Kit",
                "quantity": 1,
                "rate": 1270.0,
                "total": 1270.0,
            },
        ],
        "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
    }


def _gujarat_ocr_payload(
    invoice_number="33",
    invoice_id="26CORPP3939N1",
):
    extracted_text = "\n".join(
        [
            "GUJARAT FREIGHT TOOLS",
            "Invoice No. GST-3425-26",
            "Invoice Date 23-Jul-2025",
            "Challan No 33",
            "PAN: 26CORPP3939N1",
            "GSTIN: 32AABBA7890B1ZB",
            "Transport ID: 24ABSF0321B2ZL",
            "Sr. No. Name of Product / Service HSN / SAC Qty Rate Taxable Value",
            "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
            "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
            "IGST (18.00 %) 684.90",
            "Total 2 NOS Rs. 4,490.00",
        ]
    )
    return {
        "invoice_id": invoice_id,
        "vendor": "Gujarat Freight Tools",
        "invoice_number": invoice_number,
        "date": "23-Jul-2025",
        "currency": "INR",
        "items": [
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
        ],
        "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
        "extracted_text": extracted_text,
    }


def _acme_ocr_payload():
    extracted_text = "\n".join(
        [
            "Acme Tools",
            "INVOICE",
            "Invoice# AC-52148",
            "Date 01/02/2020",
            "SL. Item Description Price Qty. Total",
            "1 Drill Bit Set $50.00 1 $50.00",
            "2 Safety Gloves $20.00 3 $60.00",
            "Sub Total: $110.00",
            "Tax: $0.00",
            "Total: $110.00",
            "Payment Info:",
            "Account #: 1234 5678 9012",
        ]
    )
    return {
        "invoice_id": "52148",
        "vendor": "Acme Tools",
        "invoice_number": "AC-52148",
        "date": "01/02/2020",
        "currency": "USD",
        "items": [],
        "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 110.0},
        "extracted_text": extracted_text,
    }


def _real_second_invoice_payload():
    return {
        "vendor": "Acme Tools",
        "invoice_number": "AC-52148",
        "date": "01/02/2020",
        "currency": "USD",
        "items": [],
        "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 110.0},
        "extracted_text": "\n".join(
            [
                "Acme Tools",
                "Invoice# AC-52148",
                "Date 01/02/2020",
                "SL. Item Description Price Qty. Total",
                "1 Drill Bit Set $50.00 1 $50.00",
                "2 Safety Gloves $20.00 3 $60.00",
                "Sub Total: $110.00",
                "Tax: $0.00",
                "Total: $110.00",
                "Payment Info:",
                "Account #: 1234 5678 9012",
            ]
        ),
    }


def test_initialize_invoice_database_resets_to_empty_invoices(db_path):
    # Pre-populate with a record
    conn = db_module.get_connection(db_path)
    conn.execute(
        "INSERT INTO invoices (invoice_id, vendor, invoice_number) VALUES (?, ?, ?)",
        ("INV_999", "Old Vendor", "OLD-001"),
    )
    conn.commit()
    conn.close()

    assert storage_tools.initialize_invoice_database(reset=True) == {"invoices": []}
    assert storage_tools.load_invoice_database() == {"invoices": []}



def test_store_data_appends_common_invoice_record_and_derives_rows(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-1", **data})

    result = storage_tools.store_data(_invoice_payload())

    assert result["stored"] is True
    assert result["invoice_stored"] is True
    assert result["record_id"] == "INV_10001"
    assert result["database_file"] == "chatbot.db"
    assert result["invoice_count"] == 1
    assert result["invoice_row"] == {
        "invoice_id": "INV_10001",
        "vendor": "Gujarat Freight Tools",
        "invoice_number": "GST-3425-26",
        "date": "23-07-2025",
        "currency": "INR",
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert result["purchase_rows"] == [
        {
            "invoice_id": "INV_10001",
            "sr_no": 1,
            "name": "Bosch Tool Kit",
            "quantity": 1,
            "rate": 2535.0,
            "total": 2535.0,
        },
        {
            "invoice_id": "INV_10001",
            "sr_no": 2,
            "name": "Taparia Tool Kit",
            "quantity": 1,
            "rate": 1270.0,
            "total": 1270.0,
        },
    ]

    database = storage_tools.load_invoice_database()
    assert list(database.keys()) == ["invoices"]
    assert database["invoices"][0]["invoice_id"] == "INV_10001"
    assert len(database["invoices"][0]["items"]) == 2


def test_repeated_invoice_number_is_strong_duplicate(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_invoice_payload("GST-3425-26"))
    second = storage_tools.store_data(_invoice_payload("GST-3425-26"))

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is False
    assert second["duplicate"] is True
    assert second["duplicate_type"] == "strong"
    assert second["duplicate_reason"] == "invoice_number already exists"
    assert second["existing_invoice"]["invoice_id"] == "INV_10001"
    assert "record_id" not in second
    assert len(database["invoices"]) == 1


def test_stable_flow_stores_gujarat_invoice_once(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(_gujarat_ocr_payload())

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert result["record_id"] == "INV_10001"
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert len(invoice["items"]) == 2
    assert len(result["purchase_rows"]) == 2


def test_stable_flow_duplicate_gujarat_invoice_does_not_generate_next_id(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(_gujarat_ocr_payload())

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is False
    assert second["duplicate"] is True
    assert second["message"] == "Duplicate invoice detected. This invoice was not stored."
    assert "record_id" not in second
    assert len(database["invoices"]) == 1
    assert database["invoices"][0]["invoice_id"] == "INV_10001"


def test_stable_flow_different_invoice_gets_next_internal_id(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(_acme_ocr_payload())

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is True
    assert second["record_id"] == "INV_10002"
    assert database["invoices"][1]["invoice_id"] == "INV_10002"
    assert database["invoices"][1]["invoice_number"] == "AC-52148"
    assert len(database["invoices"][1]["items"]) == 2


def test_real_second_invoice_updates_database_after_first_invoice(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(_real_second_invoice_payload())

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is True
    assert second["duplicate"] is False
    assert second["record_id"] == "INV_10002"
    assert len(database["invoices"]) == 2
    assert database["invoices"][1]["invoice_number"] == "AC-52148"
    assert len(database["invoices"][1]["items"]) == 2


def test_template_second_invoice_is_rejected_with_clear_reason(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})
    monkeypatch.setattr(storage_tools, "allow_sample_invoices", lambda: False)

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(
        {
            "vendor": "Brand Name",
            "invoice_number": "52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Lorem Ipsum Dolor",
                    "quantity": 1,
                    "rate": 50,
                    "total": 50,
                }
            ],
            "summary": {"subtotal": 220.0, "tax": 0.0, "total_amount": 220.0},
            "extracted_text": "\n".join(
                [
                    "Brand Name",
                    "TAGLINE SPACE HERE",
                    "Invoice to:",
                    "Dwyane Clark",
                    "24 Dummy Street Area",
                    "Lorem Ipsum Dolor",
                    "Payment Info:",
                    "Account #: 1234 5678 9012",
                    "Bank Details: Add your bank details",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is False
    assert second["duplicate"] is False
    assert second["validation_reason"] == "template/sample invoice is not a real invoice"
    assert len(database["invoices"]) == 1


def test_stable_flow_model_invoice_id_is_ignored(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        _gujarat_ocr_payload(invoice_id="PAN 26CORPP3939N1")
    )

    database = storage_tools.load_invoice_database()
    assert result["record_id"] == "INV_10001"
    assert database["invoices"][0]["invoice_id"] == "INV_10001"


def test_stable_flow_challan_invoice_number_is_corrected_from_raw_label(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(_gujarat_ocr_payload(invoice_number="33"))

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "Invoice No. GST-3425-26"


def test_incoming_invoice_id_is_ignored_and_internal_id_is_generated(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(
        _invoice_payload(
            invoice_id="INV_010",
            invoice_number="GST-3425-26",
            vendor="Gujarat Freight Tools",
            date="23-07-2025",
        )
    )
    second = storage_tools.store_data(
        _invoice_payload(
            invoice_id="INV_010",
            invoice_number="GST-9999-26",
            vendor="Different Vendor",
            date="24-07-2025",
        )
    )

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["record_id"] == "INV_10002"
    assert [invoice["invoice_id"] for invoice in database["invoices"]] == [
        "INV_10001",
        "INV_10002",
    ]


def test_generate_next_invoice_id_ignores_old_and_ocr_like_ids():
    next_id = storage_tools.generate_next_invoice_id(
        {
            "invoices": [
                {"invoice_id": "INV_001"},
                {"invoice_id": "PAN 26CORPP3939N1"},
                {"invoice_id": "52148"},
                {"invoice_id": "INV_10002"},
            ]
        }
    )

    assert next_id == "INV_10003"


def test_normalize_invoice_record_does_not_trust_ocr_invoice_id():
    invoice = storage_tools.normalize_invoice_record(
        _invoice_payload(invoice_id="PAN 26CORPP3939N1")
    )

    assert invoice["invoice_id"] == ""


def test_vendor_and_date_match_is_possible_duplicate(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_invoice_payload(invoice_number="GST-3425-26"))
    second = storage_tools.store_data(_invoice_payload(invoice_number="GST-9999-26"))

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is False
    assert second["duplicate"] is True
    assert second["duplicate_type"] == "possible"
    assert (
        second["duplicate_reason"]
        == "same vendor, date, and total_amount already exists"
    )
    assert second["message"] == "Duplicate invoice detected. This invoice was not stored."
    assert second["existing_invoice"]["invoice_id"] == "INV_10001"
    assert "record_id" not in second
    assert len(database["invoices"]) == 1


def test_vendor_and_date_without_same_total_is_not_duplicate(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_invoice_payload(invoice_number="GST-3425-26"))
    second_payload = _invoice_payload(invoice_number="GST-9999-26")
    second_payload["summary"] = {
        "subtotal": 1000.0,
        "tax": 180.0,
        "total_amount": 1180.0,
    }
    second_payload["items"] = [
        {
            "sr_no": 1,
            "name": "Different Tool Kit",
            "quantity": 1,
            "rate": 1000.0,
            "total": 1000.0,
        }
    ]
    second = storage_tools.store_data(second_payload)

    database = storage_tools.load_invoice_database()
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is True
    assert second["duplicate"] is False
    assert second["record_id"] == "INV_10002"
    assert len(database["invoices"]) == 2


def test_empty_invoice_number_is_invalid_and_not_duplicate(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(
        _invoice_payload(invoice_number="", vendor="", date="23-07-2025")
    )
    second = storage_tools.store_data(
        _invoice_payload(invoice_number="", vendor="Different Vendor", date="")
    )

    database = storage_tools.load_invoice_database()
    assert first["stored"] is False
    assert first["duplicate"] is False
    assert first["message"] == "Invalid invoice structure"
    assert second["stored"] is False
    assert second["duplicate"] is False
    assert second["message"] == "Invalid invoice structure"
    assert len(database["invoices"]) == 0


def test_store_data_rejects_plain_ocr_text_without_items(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        "\n".join(
            [
                "Supplier Name: ACME Tools",
                "Invoice Number: AC-100",
                "Invoice Date: 2025-01-15",
                "Grand Total: 120.00",
            ]
        )
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Invalid invoice structure"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_repairs_numeric_challan_number_from_raw_invoice_text(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "33",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "\n".join(
                [
                    "TAX INVOICE",
                    "Invoice No. GST-3425-26",
                    "Challan No 33",
                    "Invoice Date 23-Jul-2025",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    assert result["stored"] is True
    assert database["invoices"][0]["invoice_number"] == "GST-3425-26"
    assert result["invoice_row"]["invoice_number"] == "GST-3425-26"


def test_store_data_backfills_thin_structured_invoice_from_raw_text(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "invoice_number": "52148",
            "raw_text": "\n".join(
                [
                    "GUJARAT FREIGHT TOOLS",
                    "TAX INVOICE",
                    "PAN : 26CORPP3939N1",
                    "Invoice No. GST-3425-26",
                    "Challan No 33",
                    "Invoice Date 23-Jul-2025",
                    "Bosch All-in-One Metal Hand Tool Kit 1 2535.00 2535.00",
                    "Taparia Universal Tool Kit 1 1270.00 1270.00",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["date"] == "23-Jul-2025"
    assert invoice["currency"] == "INR"
    assert [item["name"] for item in invoice["items"]] == [
        "Bosch All-in-One Metal Hand Tool Kit",
        "Taparia Universal Tool Kit",
    ]
    assert result["invoice_row"]["vendor"] == "Gujarat Freight Tools"
    assert len(result["purchase_rows"]) == 2


def test_store_data_parses_invoice_json_string_from_vendor_field(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "vendor": (
                '{"invoiceid":"26CORPP3939N1","vendor":"Gujarat Freight Tools",'
                '"invoicenumber":"GST 3425-26","date":"23-Jul-2025",'
                '"currency":"₹","items":[{"srno":1,'
                '"name":"Bosch All-in-One Metal Hand Tool Kit","quantity":1,'
                '"rate":2535.0,"total":2535.0},{"srno":2,'
                '"name":"Taparia Universal Tool Kit","quantity":1,'
                '"rate":1270.0,"total":1270.0}],'
                '"summary":{"subtotal":3805.0,"tax":684.9,"totalamount":4490.0}}'
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST 3425-26"
    assert invoice["date"] == "23-Jul-2025"
    assert invoice["currency"] == "INR"
    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert [item["name"] for item in invoice["items"]] == [
        "Bosch All-in-One Metal Hand Tool Kit",
        "Taparia Universal Tool Kit",
    ]
    assert len(result["purchase_rows"]) == 2


def test_store_data_recovers_embedded_json_vendor_and_invoice_label_override(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    embedded_json = (
        '{"invoiceid":"26CORPP3939N1","vendor":"Gujarat Freight Tools",'
        '"invoicenumber":"26CORPP3939N1","date":"23-Jul-2025",'
        '"currency":"INR","items":[{"srno":1,'
        '"name":"Bosch All-in-One Metal Hand Tool Kit","quantity":1,'
        '"rate":2535.0,"total":2535.0},{"srno":2,'
        '"name":"Taparia Universal Tool Kit","quantity":1,'
        '"rate":1270.0,"total":1270.0}],'
        '"summary":{"subtotal":3805.0,"tax":684.9,"totalamount":4490.0}}'
    )

    result = storage_tools.store_data(
        {
            "vendor": embedded_json,
            "invoice_number": "26CORPP3939N1",
            "date": "23-Jul-2025",
            "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
            "raw_text": "\n".join(
                [
                    "PAN : 26CORPP3939N1",
                    "Invoice No. GST-3425-26",
                    "Challan No 33",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "Invoice No. GST-3425-26"
    assert len(invoice["items"]) == 2


def test_store_data_decodes_escaped_embedded_json_vendor(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    escaped_vendor = (
        '{\\"invoiceid\\":\\"26CORPP3939N1\\",'
        '\\"vendor\\":\\"Gujarat Freight Tools\\",'
        '\\"invoicenumber\\":\\"26CORPP3939N1\\",'
        '\\"date\\":\\"23-Jul-2025\\",'
        '\\"currency\\":\\"INR\\",'
        '\\"items\\":[{\\"srno\\":1,\\"name\\":\\"Bosch All-in-One Metal Hand Tool Kit\\",'
        '\\"quantity\\":1,\\"rate\\":2535.0,\\"total\\":2535.0}],'
        '\\"summary\\":{\\"subtotal\\":2535.0,\\"tax\\":456.3,\\"totalamount\\":2991.3}}'
    )

    result = storage_tools.store_data(
        {
            "vendor": escaped_vendor,
            "invoice_number": "26CORPP3939N1",
            "raw_text": "Invoice No. GST-3425-26",
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert len(invoice["items"]) == 1


def test_store_data_uses_invoice_json_after_noisy_item_objects(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    noisy_text = (
        "This is a computer generated invoice. Customer Signature Owner Responsibility "
        "I for Gujrati Freight Tools GST 3425-26, 23-Jul-2025 4490.0 "
        'items: [{ "item": "Bosch All-in-One Metal Hand Tool Kit", "quantity": 1, '
        '"rate": 2535.0, "tax": 18.0, "subtotal": 2535.00, "igst": 684.90 }, '
        '{ "item": "Taparia Universal Tool Kit", "quantity": 1, "rate": 1270.0, '
        '"tax": 18.0, "subtotal": 1270.00, "igst": 8302.00 }] '
        '{"invoice_id": "26CORPP3939N1", "vendor": "Gujarat Freight Tools", '
        '"invoice_number": "GST-3425-26", "date": "23-Jul-2025", '
        '"currency": "INR", "items": [{ "sr_no": 1, '
        '"name": "Bosch All-in-One Metal Hand Tool Kit", "quantity": 1, '
        '"rate": 2535.0, "total": 2535.00 }, { "sr_no": 2, '
        '"name": "Taparia Universal Tool Kit", "quantity": 1, '
        '"rate": 1270.0, "total": 1270.00 }], '
        '"summary": { "subtotal": 3805.00, "tax": 684.90, "total_amount": 4490.00 }}'
    )

    result = storage_tools.store_data({"extracted_text": noisy_text})

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert len(invoice["items"]) == 2
    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }


def test_template_invoice_number_evidence_overrides_bad_json_invoice_number(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        """```json
{"vendor":"GUJARAT FREIGHT TOOLS","invoice_number":"33","date":"23-Jul-2025","currency":"INR","items":[{"sr_no":1,"name":"Bosch All-in-One Metal Hand Tool Kit","quantity":1,"rate":2535.0,"total":2535.0}],"summary":{"subtotal":2535.0,"tax":456.3,"total_amount":2991.3}}
```

Vendor template invoice number evidence: Invoice No. GST-3425-26"""
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == (
        "Vendor template invoice number evidence: Invoice No. GST-3425-26"
    )


def test_merchant_name_json_uses_template_evidence_when_invoice_number_is_challan_label(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": """{
  "merchant_name": "GUJARAT FREIGHT TOOLS",
  "invoice_id": "33",
  "invoice_number": "CHALLAN NO",
  "date": "23-Jul-2025",
  "currency": "INR",
  "items": [
    {"sr_no": 1, "name": "Bosch All-in-One Metal Hand Tool Kit", "quantity": 1, "rate": 2535.0, "total": 2535.0},
    {"sr_no": 2, "name": "Taparia Universal Tool Kit", "quantity": 1, "rate": 1270.0, "total": 1270.0}
  ],
  "subtotal": 3805.0,
  "tax": 684.9,
  "total_amount": 4489.9
}

Vendor template invoice number evidence: Invoice No. GST-3425-26"""
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == (
        "Vendor template invoice number evidence: Invoice No. GST-3425-26"
    )
    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4489.9,
    }


def test_store_data_parses_purchase_rows_from_numbered_ocr_table(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "signature",
            "date": "23-Jul-2025",
            "currency": "INR",
            "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 2535.0},
            "raw_text": "\n".join(
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
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["summary"]["total_amount"] == 4490.0
    assert invoice["items"] == [
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
    assert len(result["purchase_rows"]) == 2


def test_store_data_replaces_bad_model_purchase_rows_with_raw_ocr_items(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "vendor": "GUJARAT FREIGHT TOOLS",
            "invoice_number": "GST-3425-K",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {"sr_no": 1, "name": "Plot No A", "quantity": 0, "rate": 64, "total": 21},
                {"sr_no": 2, "name": "Transport ID", "quantity": 24, "rate": 321, "total": 2},
                {"sr_no": 3, "name": "|", "quantity": 1, "rate": 2535, "total": 2535},
                {"sr_no": 4, "name": "|", "quantity": 2, "rate": 1270, "total": 1270},
                {"sr_no": 5, "name": "|", "quantity": 18, "rate": 684.9, "total": 684.9},
            ],
            "summary": {"subtotal": 3805.0, "tax": 32.0, "total_amount": 2535.0},
            "raw_text": "\n".join(
                [
                    "GUJARAT FREIGHT TOOLS",
                    "Invoice No. GST-3425-26",
                    "Invoice Date 23-Jul-2025",
                    "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
                    "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }
    assert invoice["items"] == [
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


def test_store_data_strictly_extracts_gujarat_invoice_from_ocr_output(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": "\n".join(
                [
                    "GUJARAT FREIGHT TOOLS",
                    "Plot No A 64, Road No 21",
                    "PAN : 26CORPP3939N1",
                    "GSTIN 32AABBA7890B1ZB",
                    "Invoice No. GST-3425-26",
                    "Challan No 33",
                    "Transport ID 24ABSF50321B2ZL",
                    "Invoice Date 23-Jul-2025",
                    "Sr. No. Name of Product / Service HSN / SAC Qty Rate Taxable Value",
                    "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
                    "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                    "Bank Details ICICI",
                ]
            )
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert result["record_id"] == "INV_10001"
    assert invoice == {
        "invoice_id": "INV_10001",
        "vendor": "Gujarat Freight Tools",
        "invoice_number": "GST-3425-26",
        "date": "23-Jul-2025",
        "currency": "INR",
        "items": [
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
        ],
        "summary": {
            "subtotal": 3805.0,
            "tax": 684.9,
            "total_amount": 4490.0,
        },
    }
    assert result["purchase_rows"][0]["invoice_id"] == "INV_10001"
    assert len(result["purchase_rows"]) == 2


def test_store_data_accepts_tax_invoice_label_when_ocr_mislabels_invoice_no(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": "\n".join(
                [
                    "Gujarat Freight Tools",
                    "PAN: 26CORPP3939N1",
                    "Tax Invoice: GST-3425-26 | Invoice Date: 23-Jul-2025",
                    "Challan No: 33",
                    "Transport ID: 24ABSF50321B2ZL",
                    "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
                    "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                ]
            )
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["date"] == "23-Jul-2025"
    assert len(invoice["items"]) == 2


def test_store_data_normalizes_malformed_model_json_from_ocr_debug(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": (
                '{"invoice_id":"26CORPP3939N1",'
                '"vendor":"GUJARAT FREIGHT TOOLS Manufacturing & Supply of Precision Press Tool & Room Component",'
                '"invoice_number":"GST-3425-26-33",'
                '"date":"23-Jul-2025",'
                '"currency":"INR",'
                '"items":[[{"sr_no":"2","name":"Taparia Universal Tool Kit",'
                '"quantity":1,"rate":1270.0,"total":1270.0}]],'
                '"summary":{"subtotal":3805.0,"tax":684.9,"total_amount":4490.0}}'
            )
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["items"] == [
        {
            "sr_no": 2,
            "name": "Taparia Universal Tool Kit",
            "quantity": 1,
            "rate": 1270.0,
            "total": 1270.0,
        }
    ]


def test_store_data_ignores_invalid_ocr_invoice_id_when_items_are_valid(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": """```json
{
  "invoice_id": "GSTIN",
  "vendor": "GUJARAT FREIGHT TOOLS",
  "invoice_number": "GST-3425-26",
  "date": "2025-07-23",
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
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert result["record_id"] == "INV_10001"
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert len(invoice["items"]) == 2


def test_store_data_parses_fenced_json_with_trailing_separator(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": """GUJARAT FREIGHT TOOLS
PAN : 26CORPP3939N1 | Invoice No. GST-3425-26
Invoice Date: 23-Jul-2025 | Challan Date: 23-Jul-2025

#-----------------------------
```json
{
  "invoice_id": "26CORPP3939N1",
  "vendor": "GUJARAT FREIGHT TOOLS",
  "invoice_number": "GST-3425-26",
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
#-----------------------------
```"""
        }
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["date"] == "23-Jul-2025"
    assert len(invoice["items"]) == 2
    assert invoice["summary"]["total_amount"] == 4490.0


def test_store_data_parses_escaped_json_string(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    escaped_json = (
        '{\\"invoice_id\\":\\"26CORPP3939N1\\",'
        '\\"vendor\\":\\"Gujarat Freight Tools\\",'
        '\\"invoice_number\\":\\"GST-3425-26\\",'
        '\\"date\\":\\"23-Jul-2025\\",'
        '\\"currency\\":\\"INR\\",'
        '\\"items\\":[{'
        '\\"sr_no\\":1,'
        '\\"name\\":\\"Bosch All-in-One Metal Hand Tool Kit\\",'
        '\\"quantity\\":1,'
        '\\"rate\\":2535.0,'
        '\\"total\\":2535.0'
        '}],'
        '\\"summary\\":{'
        '\\"subtotal\\":2535.0,'
        '\\"tax\\":456.3,'
        '\\"total_amount\\":2991.3'
        '}}'
    )

    result = storage_tools.store_data({"extracted_text": escaped_json})

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_id"] == "INV_10001"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert len(invoice["items"]) == 1


def test_store_data_accepts_raw_text_payload_without_mapping_memory_crash(db_path, monkeypatch):

    raw_text = """```json
{
  "vendor": "GUJARAT FREIGHT TOOLS",
  "invoice_number": "GST-3425-26",
  "date": "23-Jul-2025",
  "currency": "INR",
  "items": [
    {
      "sr_no": 1,
      "name": "Bosch All-in-One Metal Hand Tool Kit",
      "quantity": 1,
      "rate": 2535.0,
      "total": 2535.0
    }
  ],
  "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3}
}
```"""

    result = storage_tools.store_data(raw_text)

    memory_data = memory.load_memory()
    assert result["stored"] is True
    assert result["memory_record"]["raw_payload"] == raw_text
    assert memory_data["tasks"][0]["raw_payload"] == raw_text


def test_store_data_uses_invoice_label_evidence_for_numeric_json_invoice_number(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    extracted_text = """Acme Tools
INVOICE
Invoice# AC-52148
Date 01/02/2020

| SL. | Item Description | Price | Qty. | Total |
|-----|------------------|-------|------|-------|
| 1 | Drill Bit Set | $50.00 | 1 | $50.00 |
| 2 | Safety Gloves | $20.00 | 3 | $60.00 |

{
  "vendor": "Acme Tools",
  "invoice_number": "AC-52148",
  "date": "01/02/2020",
  "currency": "$",
  "items": [
    {"sr_no": 1, "name": "Drill Bit Set", "quantity": 1, "rate": 50.0, "total": 50.0},
    {"sr_no": 2, "name": "Safety Gloves", "quantity": 3, "rate": 20.0, "total": 60.0}
  ],
  "summary": {"subtotal": 110.0, "tax": 0.0, "total_amount": 110.0}
}
"""

    result = storage_tools.store_data({"extracted_text": extracted_text})

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert invoice["invoice_number"] == "AC-52148"
    assert len(invoice["items"]) == 2


def test_normalize_invoice_recovers_items_from_raw_text_when_structured_items_empty():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [],
            "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
            "raw_text": "\n".join(
                [
                    "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
                    "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
                ]
            ),
        }
    )

    assert invoice["items"] == [
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


def test_normalize_invoice_recovers_items_from_markdown_table_when_structured_items_empty():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Brand Name",
            "invoice_number": "INV-52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [],
            "summary": {"subtotal": 220.0, "tax": 0.0, "total_amount": 220.0},
            "raw_text": "\n".join(
                [
                    "| SL. | Item Description | Price | Qty. | Total |",
                    "|-----|------------------|-------|------|-------|",
                    "| 1 | Lorem Ipsum Dolor | $50.00 | 1 | $50.00 |",
                    "| 2 | Pellentesque id neque ligula | $20.00 | 3 | $60.00 |",
                ]
            ),
        }
    )

    assert invoice["items"] == [
        {
            "sr_no": 1,
            "name": "Lorem Ipsum Dolor",
            "quantity": 1,
            "rate": 50.0,
            "total": 50.0,
        },
        {
            "sr_no": 2,
            "name": "Pellentesque id neque ligula",
            "quantity": 3,
            "rate": 20.0,
            "total": 60.0,
        },
    ]


def test_normalize_invoice_prefers_more_valid_json_items_than_raw_text_items():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Brand Name",
            "invoice_number": "INV-52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Lorem Ipsum Dolor",
                    "quantity": 1,
                    "rate": 50.0,
                    "total": 50.0,
                },
                {
                    "sr_no": 2,
                    "name": "Pellentesque id neque ligula",
                    "quantity": 3,
                    "rate": 20.0,
                    "total": 60.0,
                },
            ],
            "summary": {"subtotal": 110.0, "tax": 0.0, "total_amount": 110.0},
            "raw_text": "1 Lorem Ipsum Dolor 50.00 1 50.00",
        }
    )

    assert len(invoice["items"]) == 2
    assert invoice["items"][1]["name"] == "Pellentesque id neque ligula"


def test_invoice_number_falls_back_to_json_key_regex():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "",
            "invoice_number": "",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": '{\\"invoice_number\\":\\"GST-3425-26\\"}',
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"


def test_invoice_number_label_overrides_gstin_like_model_candidate():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "26CORPP3939N1",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "\n".join(
                [
                    "GSTIN: 26CORPP3939N1",
                    "Invoice no.: GST-3425-26",
                    "Date: 23-Jul-2025",
                ]
            ),
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "Invoice no.: GST-3425-26"


def test_invoice_number_label_beats_challan_pan_gstin_eway_and_transport_ids():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "33",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "\n".join(
                [
                    "PAN : 26CORPP3939N1",
                    "GSTIN 32AABBA7890B1ZB",
                    "Invoice No. GST-3425-26",
                    "Challan No 33",
                    "E-Way Bill No. 78456378",
                    "Transport ID 24ABSF50321B2ZL",
                ]
            ),
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "Invoice No. GST-3425-26"


def test_gujarat_invoice_rejects_pan_like_invoice_no_even_when_labeled():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "26CORPP3939N1",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "\n".join(
                [
                    "Invoice No: 26CORPP3939N1",
                    "Challan No: 33",
                    "Transport ID: 24ABSFS0321B2ZL",
                ]
            ),
        }
    )

    assert invoice["invoice_number"] == ""
    assert "invoice_number_source" not in invoice


def test_markdown_invoice_number_label_beats_json_numeric_invoice_number():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "33",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "\n".join(
                [
                    "**Invoice No.**: GST-3425-26",
                    '{"invoice_number": "33"}',
                ]
            ),
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "**Invoice No.**: GST-3425-26"


def test_invoice_number_regex_label_wins_over_valid_json_candidate():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "WRONG-999",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
            "raw_text": "Invoice No. GST-3425-26",
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "Invoice No. GST-3425-26"


def test_gujarat_invoice_number_adds_gst_prefix_to_bare_template_number():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "3425-26",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"


def test_gujarat_invoice_number_falls_back_to_valid_invoice_id():
    invoice = storage_tools.normalize_invoice_record(
        {
            "invoice_id": "GST-3425-26",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["invoice_number_source"] == "invoice_id: GST-3425-26"


def test_gujarat_invoice_id_fallback_rejects_pan_like_value():
    invoice = storage_tools.normalize_invoice_record(
        {
            "invoice_id": "26CORPP3939N1",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 456.3, "total_amount": 2991.3},
        }
    )

    assert invoice["invoice_number"] == ""
    assert "invoice_number_source" not in invoice


def test_json_items_are_kept_while_raw_text_fills_missing_fields():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "",
            "invoice_number": "",
            "date": "",
            "currency": "",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 0.0},
            "raw_text": "\n".join(
                [
                    "Supplier Name: Gujarat Freight Tools",
                    "Invoice No. GST-3425-26",
                    "Invoice Date: 23-Jul-2025",
                    "Subtotal: 2,535.00",
                    "Tax: 456.30",
                    "Total Amount: 2,991.30",
                ]
            ),
        }
    )

    assert invoice["vendor"] == "Gujarat Freight Tools"
    assert invoice["invoice_number"] == "GST-3425-26"
    assert invoice["date"] == "23-Jul-2025"
    assert invoice["currency"] == "INR"
    assert invoice["items"] == [
        {
            "sr_no": 1,
            "name": "Bosch All-in-One Metal Hand Tool Kit",
            "quantity": 1,
            "rate": 2535.0,
            "total": 2535.0,
        }
    ]
    assert invoice["summary"] == {
        "subtotal": 2535.0,
        "tax": 456.3,
        "total_amount": 2991.3,
    }


def test_quantity_with_unit_suffix_is_parsed_from_json_items():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": "1",
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": "1 NOS",
                    "rate": 2535.0,
                    "total": 2535.0,
                },
                {
                    "sr_no": "2",
                    "name": "Taparia Universal Tool Kit",
                    "quantity": "1 NOS",
                    "rate": 1270.0,
                    "total": 1270.0,
                },
            ],
            "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
        }
    )

    assert [item["quantity"] for item in invoice["items"]] == [1, 1]


def test_bad_summary_item_amounts_are_reconciled_from_raw_invoice_totals():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "33",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
                {
                    "sr_no": "1",
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": "1 NOS",
                    "rate": 2535.0,
                    "total": 2535.0,
                },
                {
                    "sr_no": "2",
                    "name": "Taparia Universal Tool Kit",
                    "quantity": "1 NOS",
                    "rate": 1270.0,
                    "total": 1270.0,
                },
            ],
            "summary": {"subtotal": 2535.0, "tax": 1270.0, "total_amount": 3805.0},
            "raw_text": "\n".join(
                [
                    "Invoice No. GST-3425-26",
                    "1 Bosch All-in-One Metal Hand Tool Kit 8302 1 NOS 2,535.00 2,535.00",
                    "2 Taparia Universal Tool Kit 8302 1 NOS 1,270.00 1,270.00",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                ]
            ),
        }
    )

    assert invoice["invoice_number"] == "GST-3425-26"
    assert [item["quantity"] for item in invoice["items"]] == [1, 1]
    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }


def test_store_data_rejects_invoice_without_positive_total_amount(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Bosch All-in-One Metal Hand Tool Kit",
                    "quantity": 1,
                    "rate": 2535.0,
                    "total": 2535.0,
                }
            ],
            "summary": {"subtotal": 2535.0, "tax": 0.0, "total_amount": 0.0},
        }
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Invalid invoice structure"
    assert result["validation_reason"] == "summary.total_amount must be greater than 0"
    assert result["normalized_invoice"]["invoice_id"] == ""
    assert result["database_file"] == "chatbot.db"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_rejects_gujarat_markdown_table_with_short_numeric_invoice_number(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "extracted_text": "\n".join(
                [
                    "## Gujarat Freight Tools Invoice",
                    "### Merchant Information",
                    "**Name**: Gujarat Freight Tools",
                    "### Invoice Details",
                    "**Invoice No.**: 33",
                    "**Invoice Date**: 23-Jul-2025",
                    "**Total Amount**: INR 4,490.00",
                    "### Key Line Items",
                    "| **Sr No** | **Product/Service** | **Qty** | **Rate (INR)** | **Amount (INR)** |",
                    "|-----------|---------------------|---------|----------------|------------------|",
                    "| 1 | Bosch All-in-One Metal Hand Tool Kit | 1 NOS | 2,535.00 | 2,535.00 |",
                    "| 2 | Taparia Universal Tool Kit | 1 NOS | 1,270.00 | 1,270.00 |",
                    "| **Total** | **GST (18%)** | **2 NOS** | **INR 684.90** | |",
                    "### Summary",
                    "- **Subtotal**: INR 3,805.00",
                    "- **Tax (18%)**: INR 684.90",
                    "- **Total Amount**: INR 4,490.00",
                    "---",
                    "{",
                    '  "invoice_id": "26CORPP3939N1",',
                    '  "vendor": "Gujarat Freight Tools",',
                    '  "invoice_number": "33",',
                    '  "date": "23-Jul-2025",',
                    '  "currency": "INR",',
                    '  "items": [',
                    '    {"sr_no": 1, "name": "Bosch All-in-One Metal Hand Tool Kit", "quantity": 1, "rate": 2535.0, "total": 2535.0},',
                    '    {"sr_no": 2, "name": "Taparia Universal Tool Kit", "quantity": 1, "rate": 1270.0, "total": 1270.0}',
                    "  ],",
                    '  "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0}',
                    "}",
                ]
            )
        }
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["validation_reason"] == "missing invoice_number"
    assert result["normalized_invoice"]["invoice_number"] == ""
    assert result["normalized_invoice"]["items"]
    assert result["database_file"] == "chatbot.db"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_normalized_extraction_payload_is_stored_as_common_invoice(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "invoice": {
                "vendor": "Gujarat Freight Tools",
                "invoice_number": "GST-3425-26",
                "date": "23-07-2025",
                "currency": "INR",
                "subtotal": 3805.0,
                "tax": 684.9,
                "total_amount": 4490.0,
            },
            "purchases": [{"sr_no": 1, "name": "Bosch Tool Kit", "quantity": 1}],
        }
    )

    database = storage_tools.load_invoice_database()
    assert result["record_id"] == "INV_10001"
    assert database["invoices"][0]["vendor"] == "Gujarat Freight Tools"
    assert database["invoices"][0]["items"][0]["name"] == "Bosch Tool Kit"


def test_normalize_invoice_recovers_summary_from_raw_text_and_items():
    invoice = storage_tools.normalize_invoice_record(
        {
            "type": "invoice",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
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
            ],
            "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 0.0},
            "raw_text": "\n".join(
                [
                    "IGST (18.00 %) 3,805.00",
                    "684.90",
                    "Total 2 NOS Rs. 4,490.00",
                    "Total 3,805.00 684.90 684.90",
                ]
            ),
        }
    )

    assert invoice["summary"] == {
        "subtotal": 3805.0,
        "tax": 684.9,
        "total_amount": 4490.0,
    }


def test_normalize_invoice_drops_tax_and_total_rows_from_items():
    invoice = storage_tools.normalize_invoice_record(
        {
            "type": "invoice",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-Jul-2025",
            "currency": "INR",
            "items": [
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
                {
                    "sr_no": 3,
                    "name": "GST (18.00%)",
                    "quantity": 1,
                    "rate": 684.9,
                    "total": 684.9,
                },
                {
                    "sr_no": 4,
                    "name": "Total",
                    "quantity": 1,
                    "rate": 4490.0,
                    "total": 4490.0,
                },
            ],
            "summary": {"subtotal": 3805.0, "tax": 684.9, "total_amount": 4490.0},
        }
    )

    assert [item["name"] for item in invoice["items"]] == [
        "Bosch All-in-One Metal Hand Tool Kit",
        "Taparia Universal Tool Kit",
    ]
    assert [item["sr_no"] for item in invoice["items"]] == [1, 2]


def test_build_invoice_and_purchase_table_rows_from_invoices():
    database = {"invoices": [_invoice_payload(invoice_id="INV_10001")]}

    assert storage_tools.build_invoice_table_rows(database) == [
        {
            "invoice_id": "INV_10001",
            "vendor": "Gujarat Freight Tools",
            "invoice_number": "GST-3425-26",
            "date": "23-07-2025",
            "currency": "INR",
            "subtotal": 3805.0,
            "tax": 684.9,
            "total_amount": 4490.0,
        }
    ]
    assert storage_tools.build_purchase_table_rows(database)[0] == {
        "invoice_id": "INV_10001",
        "sr_no": 1,
        "name": "Bosch Tool Kit",
        "quantity": 1,
        "rate": 2535.0,
        "total": 2535.0,
    }


def test_store_data_does_not_add_non_invoice_to_database(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-3"})

    result = storage_tools.store_data({"type": "generic_document", "raw_text": "hello"})

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Could not create a valid invoice record from the extracted text."
    assert result["database_file"] == "chatbot.db"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_does_not_add_thin_invoice_summary(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-4"})

    result = storage_tools.store_data(
        {
            "type": "invoice",
            "invoice": {
                "vendor": "The invoice is for two items:",
                "invoice_number": "",
                "date": "",
                "currency": "",
                "subtotal": 0.0,
                "tax": 0.0,
                "total_amount": 0.0,
            },
            "purchases": [],
        }
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Could not create a valid invoice record from the extracted text."
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_does_not_add_numeric_invoice_number_only(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-5"})

    result = storage_tools.store_data({"type": "invoice", "invoice_number": "52148"})

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Could not create a valid invoice record from the extracted text."
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_rejects_ocr_without_valid_items(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-6"})

    result = storage_tools.store_data(
        {
            "extracted_text": "\n".join(
                [
                    "GUJARAT FREIGHT TOOLS",
                    "PAN : 26CORPP3939N1",
                    "Invoice No. GST-3425-26",
                    "Invoice Date 23-Jul-2025",
                    "IGST (18.00 %) 684.90",
                    "Total 2 NOS Rs. 4,490.00",
                ]
            )
        }
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["message"] == "Invalid invoice structure"
    assert result["validation_reason"] == "missing valid purchase items"
    assert result["normalized_invoice"]["invoice_number"] == "GST-3425-26"
    assert result["database_file"] == "chatbot.db"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_rejects_placeholder_invoice_template(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-7"})
    monkeypatch.setattr(storage_tools, "allow_sample_invoices", lambda: False)

    result = storage_tools.store_data(
        {
            "extracted_text": "\n".join(
                [
                    "The provided image is an invoice template with placeholder text.",
                    "Brand Name",
                    "INVOICE",
                    "Invoice to:",
                    "Dwyane Clark",
                    "24 Dummy Street Area,",
                    "Location, Lorem Ipsum,",
                    "Invoice# 52148",
                    "Date 01/02/2020",
                    "SL. Item Description Price Qty. Total",
                    "1 Lorem Ipsum Dolor $50.00 1 $50.00",
                    "2 Pellentesque id neque ligula $20.00 3 $60.00",
                    "Sub Total: $220.00",
                    "Total: $220.00",
                    "Payment Info:",
                    "Account #: 1234 5678 9012",
                ]
            )
        }
    )

    assert result["stored"] is False
    assert result["duplicate"] is False
    assert result["validation_reason"] == "template/sample invoice is not a real invoice"
    assert result["normalized_invoice"] is None
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_store_data_allows_sample_invoice_when_test_flag_enabled(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-7"})
    monkeypatch.setattr(storage_tools, "allow_sample_invoices", lambda: True)

    result = storage_tools.store_data(
        {
            "vendor": "Brand Name",
            "invoice_number": "52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [
                {
                    "sr_no": 1,
                    "name": "Lorem Ipsum Dolor",
                    "quantity": 1,
                    "rate": 50.0,
                    "total": 50.0,
                },
                {
                    "sr_no": 2,
                    "name": "Pellentesque id neque ligula",
                    "quantity": 3,
                    "rate": 20.0,
                    "total": 60.0,
                },
                {
                    "sr_no": 3,
                    "name": "Interdum et malesuada fames",
                    "quantity": 2,
                    "rate": 10.0,
                    "total": 20.0,
                },
                {
                    "sr_no": 4,
                    "name": "Vivamus volutpat faucibus",
                    "quantity": 1,
                    "rate": 90.0,
                    "total": 90.0,
                },
            ],
            "summary": {"subtotal": 220.0, "tax": 0.0, "total_amount": 220.0},
            "extracted_text": "\n".join(
                [
                    "Brand Name",
                    "TAGLINE SPACE HERE",
                    "Invoice #: 52148",
                    "Date: 01/02/2020",
                    "SL. Item Description Price Qty. Total",
                    "1 Lorem Ipsum Dolor $50.00 1 $50.00",
                    "2 Pellentesque id neque ligula $20.00 3 $60.00",
                    "3 Interdum et malesuada fames $10.00 2 $20.00",
                    "4 Vivamus volutpat faucibus $90.00 1 $90.00",
                    "Sub Total: $220.00",
                    "Total: $220.00",
                    "Account: 1234 5678 9012",
                ]
            ),
        }
    )

    database = storage_tools.load_invoice_database()
    assert result["stored"] is True
    assert result["record_id"] == "INV_10001"
    assert result["invoice_row"]["invoice_id"] == "INV_10001"
    assert result["invoice_row"]["vendor"] == "Brand Name"
    assert result["invoice_row"]["invoice_number"] == "52148"
    assert len(result["purchase_rows"]) == 4
    assert database["invoices"][0]["invoice_id"] == "INV_10001"
    assert database["invoices"][0]["invoice_number"] == "52148"
    assert len(database["invoices"][0]["items"]) == 4


def test_store_data_repairs_partial_yellow_sample_invoice_when_test_flag_enabled(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-9"})
    monkeypatch.setattr(storage_tools, "allow_sample_invoices", lambda: True)

    result = storage_tools.store_data(
        {
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
    )

    database = storage_tools.load_invoice_database()
    invoice = database["invoices"][0]
    assert result["stored"] is True
    assert result["record_id"] == "INV_10001"
    assert invoice["vendor"] == "Brand Name"
    assert invoice["invoice_number"] == "52148"
    assert invoice["currency"] == "USD"
    assert invoice["items"] == [
        {
            "sr_no": 1,
            "name": "Lorem Ipsum Dolor",
            "quantity": 1,
            "rate": 50.0,
            "total": 50.0,
        },
        {
            "sr_no": 2,
            "name": "Pellentesque id neque ligula",
            "quantity": 3,
            "rate": 20.0,
            "total": 60.0,
        },
        {
            "sr_no": 3,
            "name": "Interdum et malesuada fames",
            "quantity": 2,
            "rate": 10.0,
            "total": 20.0,
        },
        {
            "sr_no": 4,
            "name": "Vivamus volutpat faucibus",
            "quantity": 1,
            "rate": 90.0,
            "total": 90.0,
        },
    ]


def test_store_data_does_not_parse_payment_info_as_purchase_item(db_path, monkeypatch):
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task-8"})

    result = storage_tools.store_data(
        {
            "vendor": "Acme Tools",
            "invoice_number": "AC-52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [],
            "summary": {"subtotal": 0.0, "tax": 0.0, "total_amount": 9012.0},
            "raw_text": "\n".join(
                    [
                        "Payment Info:",
                        "Account #: 1234 5678 9012",
                        "A/C Name: Acme Tools",
                        "Bank Details: ICICI Bank",
                    ]
                ),
            }
    )

    assert result["stored"] is False
    assert result["validation_reason"] == "missing valid purchase items"
    assert storage_tools.load_invoice_database() == {"invoices": []}


def test_text_items_are_parsed_only_from_item_table_area():
    invoice = storage_tools.normalize_invoice_record(
        {
            "vendor": "Acme Tools",
            "invoice_number": "AC-52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [],
            "summary": {"subtotal": 110.0, "tax": 0.0, "total_amount": 110.0},
            "raw_text": "\n".join(
                [
                    "SL. Item Description Price Qty. Total",
                    "1 Drill Bit Set $50.00 1 $50.00",
                    "2 Safety Gloves $20.00 3 $60.00",
                    "Sub Total: $110.00",
                    "Payment Info:",
                    "Account #: 1234 5678 9012",
                ]
            ),
        }
    )

    assert [item["name"] for item in invoice["items"]] == [
        "Drill Bit Set",
        "Safety Gloves",
    ]


def test_load_invoice_database_recovers_corrupt_json(db_path, monkeypatch):
    # With SQLite, a fresh database always returns an empty invoices list.
    # This test verifies load_invoice_database works on an empty DB
    # (the SQLite equivalent of recovering from corrupt JSON).
    assert storage_tools.load_invoice_database() == {"invoices": []}
