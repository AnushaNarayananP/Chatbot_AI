"""Central SQLite database module for the chatbot application.

Manages the database connection and schema for invoices, line items,
conversation memory, task results, and mock ERP submissions.

Replaces the previous JSON file storage (invoice_database.json,
memory_store.json, mock_erp_submissions.json) with a single SQLite database.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator


DATABASE_PATH: Path = Path(__file__).resolve().parent / "chatbot.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS invoices (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id            TEXT    UNIQUE NOT NULL,
    vendor                TEXT    NOT NULL,
    invoice_number        TEXT    NOT NULL,
    date                  TEXT,
    currency              TEXT,
    subtotal              REAL    DEFAULT 0,
    tax                   REAL    DEFAULT 0,
    total_amount          REAL    DEFAULT 0,
    invoice_number_source TEXT,
    created_at            TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT    NOT NULL REFERENCES invoices(invoice_id),
    sr_no      INTEGER,
    name       TEXT    NOT NULL,
    quantity   INTEGER DEFAULT 0,
    rate       REAL    DEFAULT 0,
    total      REAL    DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT    NOT NULL,
    content    TEXT,
    metadata   TEXT,
    created_at TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT    UNIQUE NOT NULL,
    payload    TEXT,
    created_at TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS erp_submissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    erp_id      TEXT    UNIQUE NOT NULL,
    status      TEXT    DEFAULT 'accepted',
    accepted_at TEXT,
    payload     TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection, creating the database and tables if needed.

    Parameters
    ----------
    db_path:
        Override the default database path.  Useful for tests that want an
        isolated, temporary database.  When *None*, uses ``DATABASE_PATH``.
    """
    path = Path(db_path) if db_path is not None else DATABASE_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


@contextmanager
def transaction(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a connection and commits on success.

    On exception the transaction is rolled back and the error re-raised.
    The connection is always closed when the context exits.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not already exist."""
    conn.executescript(_SCHEMA_SQL)
