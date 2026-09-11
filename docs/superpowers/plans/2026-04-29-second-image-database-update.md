# Second Image Database Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the second uploaded invoice update `invoice_database.json` when it is a real, different invoice, and return a clear reason when it is intentionally rejected.

**Architecture:** Keep storage as the single source of truth. OCR and model JSON remain untrusted helper input; `store_data()` normalizes the candidate, explains validation failures, checks duplicates, then generates `invoice_id` only when saving.

**Tech Stack:** Python, pytest, JSON file storage, Streamlit UI consuming storage result fields.

---

## Root Cause To Verify

The second image is probably not updating because storage is rejecting it before save. In the screenshots, the second image looked like a sample/template invoice with placeholder vendor text (`Brand Name`, `Lorem Ipsum`, `Dummy Street`, `add your bank details`). The current validation correctly blocks template/sample invoices, invalid vendors, missing purchase items, and duplicates. The issue is that the UI only shows a broad validation message, so it feels like the database failed instead of explaining that the invoice was rejected.

## Files

- Modify: `tools/storage_tools.py`
- Modify: `tests/test_storage_tools.py`
- Optional modify: `user_interface.py` only if the UI does not display `validation_reason`

---

### Task 1: Add A Regression Test For A Real Second Invoice

- [ ] **Step 1: Add test data for a real non-template second invoice**

Add this helper to `tests/test_storage_tools.py` near the other payload helpers:

```python
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
```

- [ ] **Step 2: Add the failing/passing storage test**

```python
def test_real_second_invoice_updates_database_after_first_invoice(monkeypatch):
    database_file = _database_file(".test-invoice-database-real-second.json")
    monkeypatch.setattr(storage_tools, "INVOICE_DATABASE_FILE", database_file)
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(_real_second_invoice_payload())

    database = json.loads(database_file.read_text(encoding="utf-8"))
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is True
    assert second["duplicate"] is False
    assert second["record_id"] == "INV_10002"
    assert len(database["invoices"]) == 2
    assert database["invoices"][1]["invoice_number"] == "AC-52148"
    assert len(database["invoices"][1]["items"]) == 2
    database_file.unlink()
```

- [ ] **Step 3: Run the focused test**

Run:

```powershell
$env:PYTHONPATH='.'; pytest tests/test_storage_tools.py::test_real_second_invoice_updates_database_after_first_invoice -v
```

Expected: PASS if the storage flow already supports real second invoices. FAIL means the normalization/storage code still needs Task 3.

---

### Task 2: Add A Test That Template/Sample Second Image Is Rejected Clearly

- [ ] **Step 1: Add test for the yellow sample invoice image behavior**

```python
def test_template_second_invoice_is_rejected_with_clear_reason(monkeypatch):
    database_file = _database_file(".test-invoice-database-template-second.json")
    monkeypatch.setattr(storage_tools, "INVOICE_DATABASE_FILE", database_file)
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first = storage_tools.store_data(_gujarat_ocr_payload())
    second = storage_tools.store_data(
        {
            "vendor": "Brand Name",
            "invoice_number": "52148",
            "date": "01/02/2020",
            "currency": "USD",
            "items": [
                {"sr_no": 1, "name": "Lorem Ipsum Dolor", "quantity": 1, "rate": 50, "total": 50}
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

    database = json.loads(database_file.read_text(encoding="utf-8"))
    assert first["record_id"] == "INV_10001"
    assert second["stored"] is False
    assert second["duplicate"] is False
    assert second["validation_reason"] == "template/sample invoice is not a real invoice"
    assert len(database["invoices"]) == 1
    database_file.unlink()
```

- [ ] **Step 2: Run the focused test**

Run:

```powershell
$env:PYTHONPATH='.'; pytest tests/test_storage_tools.py::test_template_second_invoice_is_rejected_with_clear_reason -v
```

Expected: PASS. This confirms the database is not broken; the second image is intentionally blocked.

---

### Task 3: Make Rejection Reasons Visible And Stable

- [ ] **Step 1: Ensure `store_data()` returns complete failure details**

In `tools/storage_tools.py`, confirm invalid responses include:

```python
{
    "stored": False,
    "duplicate": False,
    "message": "Invalid invoice structure",
    "validation_reason": validation_reason,
    "normalized_invoice": normalized_invoice,
    "database_file": INVOICE_DATABASE_NAME,
}
```

For duplicate responses, confirm:

```python
{
    "stored": False,
    "duplicate": True,
    "duplicate_reason": duplicate["duplicate_reason"],
    "duplicate_type": duplicate["duplicate_type"],
    "message": duplicate["message"],
}
```

- [ ] **Step 2: If needed, update UI display**

Only modify `user_interface.py` if the UI hides `validation_reason`. Show:

```python
if result.get("validation_reason"):
    st.warning(f"Validation reason: {result['validation_reason']}")
elif result.get("duplicate"):
    st.warning(result.get("message", "Duplicate invoice detected. This invoice was not stored."))
else:
    st.error(result.get("message", "Invoice was not stored."))
```

- [ ] **Step 3: Run UI/storage tests**

Run:

```powershell
$env:PYTHONPATH='.'; pytest tests/test_storage_tools.py tests/test_user_interface.py
```

Expected: PASS.

---

### Task 4: Confirm Duplicate Logic Does Not Block Different Invoices

- [ ] **Step 1: Add same-vendor/date/different-total test if missing**

```python
def test_same_vendor_and_date_with_different_total_is_not_duplicate(monkeypatch):
    database_file = _database_file(".test-invoice-database-different-total.json")
    monkeypatch.setattr(storage_tools, "INVOICE_DATABASE_FILE", database_file)
    monkeypatch.setattr(storage_tools, "store_task_result", lambda data: {"id": "task"})

    first_payload = _invoice_payload(invoice_number="GST-3425-26")
    second_payload = _invoice_payload(invoice_number="GST-9999-26")
    second_payload["summary"] = {"subtotal": 1000.0, "tax": 180.0, "total_amount": 1180.0}
    second_payload["items"] = [
        {"sr_no": 1, "name": "Different Tool Kit", "quantity": 1, "rate": 1000.0, "total": 1000.0}
    ]

    first = storage_tools.store_data(first_payload)
    second = storage_tools.store_data(second_payload)

    database = json.loads(database_file.read_text(encoding="utf-8"))
    assert first["record_id"] == "INV_10001"
    assert second["record_id"] == "INV_10002"
    assert len(database["invoices"]) == 2
    database_file.unlink()
```

- [ ] **Step 2: Run all storage tests**

Run:

```powershell
$env:PYTHONPATH='.'; pytest tests/test_storage_tools.py
```

Expected: all tests pass.

---

## Expected Final Behavior

Real second invoice:

```text
stored=True
duplicate=False
record_id=INV_10002
invoice_database.json contains 2 invoices
```

Same invoice uploaded again:

```text
stored=False
duplicate=True
message="Duplicate invoice detected. This invoice was not stored."
invoice_database.json still contains 1 invoice
```

Template/sample invoice:

```text
stored=False
duplicate=False
validation_reason="template/sample invoice is not a real invoice"
invoice_database.json is not updated
```

## Verification Command

Run:

```powershell
$env:PYTHONPATH='.'; pytest tests
```

Expected: all tests pass.
