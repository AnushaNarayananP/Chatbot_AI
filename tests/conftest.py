"""Shared test fixtures for SQLite-backed tests."""

import os
import shutil
import tempfile

import pytest

import database as db_module


@pytest.fixture()
def db_path(monkeypatch):
    """Provide an isolated SQLite database for each test.

    Creates a fresh database in a temporary directory, monkeypatches
    ``database.DATABASE_PATH`` so all modules use it, and returns
    the path for direct assertions.

    Uses ``tempfile.mkdtemp`` instead of pytest's ``tmp_path`` to avoid
    PermissionError on Windows when pytest tries to clean up directories
    containing SQLite WAL/SHM journal files.
    """
    tmp_dir = tempfile.mkdtemp(prefix="chatbot-test-")
    path = os.path.join(tmp_dir, "chatbot.db")
    from pathlib import Path

    db_file = Path(path)
    monkeypatch.setattr(db_module, "DATABASE_PATH", db_file)
    # Ensure tables are created; use DELETE journal to avoid WAL lock files
    conn = db_module.get_connection(db_file)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    yield db_file
    # Cleanup: remove the temp directory; ignore errors on Windows
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
