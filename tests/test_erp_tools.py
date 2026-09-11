import database as db_module
from tools import erp_tools


def test_push_invoice_to_erp_returns_receipt_and_records_payload(db_path):
    invoice = {
        "invoice_id": "INV_10001",
        "vendor": "Gujarat Freight Tools",
        "invoice_number": "GST-3425-26",
        "date": "23-Jul-2025",
        "amount": 4490.0,
        "gst": {"total": 684.9},
        "items": [{"name": "Bosch Tool Kit", "total": 2535.0}],
    }

    receipt = erp_tools.push_invoice_to_erp(invoice)

    assert receipt["status"] == "accepted"
    assert receipt["erp_id"] == "ERP_00001"
    assert receipt["payload"] == invoice
    assert receipt["accepted_at"]

    conn = db_module.get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM erp_submissions WHERE erp_id = ?", ("ERP_00001",)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["status"] == "accepted"
