from __future__ import annotations

import json
from typing import Any

from database import DATABASE_PATH, get_connection, transaction


def load_memory() -> dict[str, Any]:
    """Load conversation turns and task results from the database.

    Returns the same ``{"conversation": [...], "tasks": [...]}`` shape
    as the previous JSON-based implementation for backward compatibility.
    """
    conn = get_connection()
    try:
        conversation_rows = conn.execute(
            "SELECT role, content, metadata FROM conversations ORDER BY id"
        ).fetchall()
        task_rows = conn.execute(
            "SELECT task_id, payload FROM tasks ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    conversation = []
    for row in conversation_rows:
        turn: dict[str, Any] = {"role": row["role"], "content": row["content"]}
        if row["metadata"]:
            try:
                extra = json.loads(row["metadata"])
                if isinstance(extra, dict):
                    turn.update(extra)
            except json.JSONDecodeError:
                pass
        conversation.append(turn)

    tasks = []
    for row in task_rows:
        payload = {}
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                payload = {"raw_payload": row["payload"]}
        if isinstance(payload, dict):
            tasks.append({"id": row["task_id"], **payload})
        else:
            tasks.append({"id": row["task_id"], "raw_payload": payload})

    return {"conversation": conversation, "tasks": tasks}


def save_memory(memory: dict[str, Any]) -> None:
    """Persist a full memory dict to the database (replaces all rows)."""
    with transaction() as conn:
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM tasks")

        for turn in memory.get("conversation", []):
            role = turn.get("role", "")
            content = turn.get("content", "")
            extra = {
                k: v for k, v in turn.items() if k not in ("role", "content")
            }
            metadata_json = json.dumps(extra, ensure_ascii=True) if extra else None
            conn.execute(
                "INSERT INTO conversations (role, content, metadata) VALUES (?, ?, ?)",
                (role, content, metadata_json),
            )

        for task in memory.get("tasks", []):
            task_id = task.get("id", "")
            payload = {k: v for k, v in task.items() if k != "id"}
            conn.execute(
                "INSERT INTO tasks (task_id, payload) VALUES (?, ?)",
                (task_id, json.dumps(payload, ensure_ascii=True)),
            )


def append_conversation_turn(turn: dict[str, Any]) -> None:
    """Append a single conversation turn, keeping at most 50 turns."""
    role = turn.get("role", "")
    content = turn.get("content", "")
    extra = {k: v for k, v in turn.items() if k not in ("role", "content")}
    metadata_json = json.dumps(extra, ensure_ascii=True) if extra else None

    with transaction() as conn:
        conn.execute(
            "INSERT INTO conversations (role, content, metadata) VALUES (?, ?, ?)",
            (role, content, metadata_json),
        )
        # Keep only the most recent 50 turns
        conn.execute(
            """
            DELETE FROM conversations
            WHERE id NOT IN (
                SELECT id FROM conversations ORDER BY id DESC LIMIT 50
            )
            """
        )


def store_task_result(task_result: Any) -> dict[str, Any]:
    """Store a task result and return the record with its assigned id."""
    with transaction() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM tasks").fetchone()
        task_id = f"task-{row['cnt'] + 1}"

        if isinstance(task_result, dict):
            record = {"id": task_id, **task_result}
        else:
            record = {"id": task_id, "raw_payload": task_result}

        payload = {k: v for k, v in record.items() if k != "id"}
        conn.execute(
            "INSERT INTO tasks (task_id, payload) VALUES (?, ?)",
            (task_id, json.dumps(payload, ensure_ascii=True)),
        )

    return record
