"""Tests for the database module."""

import sqlite3

import database as db_module


def test_get_connection_creates_tables(db_path):
    conn = db_module.get_connection(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()

    expected = {"invoices", "invoice_items", "conversations", "tasks", "erp_submissions"}
    assert expected.issubset(tables)


def test_get_connection_is_idempotent(db_path):
    conn1 = db_module.get_connection(db_path)
    conn1.close()
    conn2 = db_module.get_connection(db_path)
    conn2.close()
    # Should not raise — tables already exist


def test_transaction_commits_on_success(db_path):
    with db_module.transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO invoices (invoice_id, vendor, invoice_number) "
            "VALUES (?, ?, ?)",
            ("INV_10001", "Test Vendor", "T-001"),
        )

    conn = db_module.get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM invoices WHERE invoice_id = ?", ("INV_10001",)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["vendor"] == "Test Vendor"


def test_transaction_rolls_back_on_error(db_path):
    try:
        with db_module.transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO invoices (invoice_id, vendor, invoice_number) "
                "VALUES (?, ?, ?)",
                ("INV_99999", "Bad Vendor", "B-001"),
            )
            raise ValueError("intentional error")
    except ValueError:
        pass

    conn = db_module.get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM invoices WHERE invoice_id = ?", ("INV_99999",)).fetchone()
    finally:
        conn.close()

    assert row is None


def test_foreign_keys_enabled(db_path):
    conn = db_module.get_connection(db_path)
    try:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
    finally:
        conn.close()
    assert result[0] == 1


def test_row_factory_returns_dicts(db_path):
    conn = db_module.get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO invoices (invoice_id, vendor, invoice_number) "
            "VALUES (?, ?, ?)",
            ("INV_10001", "Dict Test", "D-001"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM invoices LIMIT 1").fetchone()
    finally:
        conn.close()

    # sqlite3.Row supports dict-like access by column name
    assert row["vendor"] == "Dict Test"
    assert row["invoice_id"] == "INV_10001"
