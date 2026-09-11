"""One-time migration script: JSON files → SQLite database.

Reads existing data from:
  - invoice_database.json
  - memory_store.json
  - mock_erp_submissions.json

Inserts all records into chatbot.db (created automatically).
The JSON files are NOT deleted — remove them manually after verifying.

Usage:
    python migrate_json_to_sqlite.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is on the import path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import get_connection, transaction


INVOICE_DB_FILE = PROJECT_ROOT / "invoice_database.json"
MEMORY_FILE = PROJECT_ROOT / "memory_store.json"
ERP_FILE = PROJECT_ROOT / "mock_erp_submissions.json"


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        print(f"  [skip] {path.name} not found")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"  [read] {path.name} ({path.stat().st_size:,} bytes)")
        return data
    except json.JSONDecodeError as e:
        print(f"  [error] {path.name}: {e}")
        return {}


def migrate_invoices(conn):
    data = _load_json(INVOICE_DB_FILE)
    if not isinstance(data, dict):
        return 0

    invoices = data.get("invoices", [])
    count = 0
    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        invoice_id = inv.get("invoice_id", "")
        summary = inv.get("summary", {}) if isinstance(inv.get("summary"), dict) else {}

        conn.execute(
            "INSERT OR REPLACE INTO invoices "
            "(invoice_id, vendor, invoice_number, date, currency, "
            "subtotal, tax, total_amount, invoice_number_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice_id,
                inv.get("vendor", ""),
                inv.get("invoice_number", ""),
                inv.get("date", ""),
                inv.get("currency", ""),
                summary.get("subtotal", 0.0),
                summary.get("tax", 0.0),
                summary.get("total_amount", 0.0),
                inv.get("invoice_number_source", ""),
            ),
        )

        items = inv.get("items", []) if isinstance(inv.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            conn.execute(
                "INSERT INTO invoice_items "
                "(invoice_id, sr_no, name, quantity, rate, total) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    invoice_id,
                    item.get("sr_no", 0),
                    item.get("name", ""),
                    item.get("quantity", 0),
                    item.get("rate", 0.0),
                    item.get("total", 0.0),
                ),
            )
        count += 1

    return count


def migrate_memory(conn):
    data = _load_json(MEMORY_FILE)
    if not isinstance(data, dict):
        return 0, 0

    conversations = data.get("conversation", [])
    conv_count = 0
    for turn in conversations:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role", "")
        content = turn.get("content", "")
        extra = {k: v for k, v in turn.items() if k not in ("role", "content")}
        metadata_json = json.dumps(extra, ensure_ascii=True) if extra else None
        conn.execute(
            "INSERT INTO conversations (role, content, metadata) VALUES (?, ?, ?)",
            (role, content, metadata_json),
        )
        conv_count += 1

    tasks = data.get("tasks", [])
    task_count = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id", f"task-{task_count + 1}")
        payload = {k: v for k, v in task.items() if k != "id"}
        conn.execute(
            "INSERT INTO tasks (task_id, payload) VALUES (?, ?)",
            (task_id, json.dumps(payload, ensure_ascii=True)),
        )
        task_count += 1

    return conv_count, task_count


def migrate_erp(conn):
    data = _load_json(ERP_FILE)
    if not isinstance(data, dict):
        return 0

    submissions = data.get("submissions", [])
    count = 0
    for sub in submissions:
        if not isinstance(sub, dict):
            continue
        conn.execute(
            "INSERT OR REPLACE INTO erp_submissions "
            "(erp_id, status, accepted_at, payload) VALUES (?, ?, ?, ?)",
            (
                sub.get("erp_id", ""),
                sub.get("status", "accepted"),
                sub.get("accepted_at", ""),
                json.dumps(sub.get("payload", {}), ensure_ascii=True),
            ),
        )
        count += 1

    return count


def main():
    print("=" * 60)
    print("JSON → SQLite Migration")
    print("=" * 60)
    print()

    # Ensure the database and tables exist
    conn = get_connection()
    conn.close()

    with transaction() as conn:
        print("1. Migrating invoices...")
        inv_count = migrate_invoices(conn)
        print(f"   → {inv_count} invoices migrated")
        print()

        print("2. Migrating conversation memory...")
        conv_count, task_count = migrate_memory(conn)
        print(f"   → {conv_count} conversation turns migrated")
        print(f"   → {task_count} task results migrated")
        print()

        print("3. Migrating ERP submissions...")
        erp_count = migrate_erp(conn)
        print(f"   → {erp_count} ERP submissions migrated")
        print()

    print("=" * 60)
    print(f"Migration complete! Database: {get_connection().execute('PRAGMA database_list').fetchone()[2]}")
    print()
    print("The original JSON files have NOT been deleted.")
    print("You can remove them manually after verifying:")
    print(f"  - {INVOICE_DB_FILE.name}")
    print(f"  - {MEMORY_FILE.name}")
    print(f"  - {ERP_FILE.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
