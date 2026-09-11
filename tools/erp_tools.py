from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import get_connection, transaction


MOCK_ERP_NAME = "chatbot.db"


def push_invoice_to_erp(invoice: dict[str, Any]) -> dict[str, Any]:
    erp_id = _next_erp_id()
    accepted_at = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(invoice, ensure_ascii=True)

    with transaction() as conn:
        conn.execute(
            "INSERT INTO erp_submissions (erp_id, status, accepted_at, payload) "
            "VALUES (?, ?, ?, ?)",
            (erp_id, "accepted", accepted_at, payload_json),
        )

    return {
        "erp_id": erp_id,
        "status": "accepted",
        "accepted_at": accepted_at,
        "payload": invoice,
        "mock_erp_file": MOCK_ERP_NAME,
    }


def _load_erp_database() -> dict[str, list[dict[str, Any]]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT erp_id, status, accepted_at, payload "
            "FROM erp_submissions ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    submissions = []
    for row in rows:
        entry: dict[str, Any] = {
            "erp_id": row["erp_id"],
            "status": row["status"],
            "accepted_at": row["accepted_at"],
        }
        if row["payload"]:
            try:
                entry["payload"] = json.loads(row["payload"])
            except json.JSONDecodeError:
                entry["payload"] = row["payload"]
        submissions.append(entry)

    return {"submissions": submissions}


def _next_erp_id() -> str:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT erp_id FROM erp_submissions ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    highest = 0
    if row:
        erp_id = str(row["erp_id"])
        if erp_id.startswith("ERP_") and erp_id.removeprefix("ERP_").isdigit():
            highest = int(erp_id.removeprefix("ERP_"))
    return f"ERP_{highest + 1:05d}"
