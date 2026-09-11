"""Lightweight SQLite audit + local notes/reminders.

Lives in copilot_state.db so it is not wiped when factory.db is rebuilt from CSV.
Wall-clock timestamps record when the system ran; business dates still use FACTORY_TODAY.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import FACTORY_TODAY, STATE_DB_PATH

_STATE_PATH: Path | None = None


def init_state_db(path: Path | None = None) -> Path:
    global _STATE_PATH
    _STATE_PATH = Path(path) if path else STATE_DB_PATH
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                factory_today TEXT NOT NULL,
                conversation_id TEXT,
                user_query TEXT,
                event_type TEXT NOT NULL,
                tool TEXT,
                inputs_json TEXT,
                result_ok INTEGER,
                result_summary TEXT,
                confirmation_status TEXT,
                execution_status TEXT,
                target TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                order_id TEXT NOT NULL,
                note TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                order_id TEXT,
                remind_on TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                created_factory_today TEXT NOT NULL,
                order_id TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                params_json TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL,
                last_evaluated_as_of TEXT,
                fired_as_of TEXT,
                fired_at TEXT,
                notify_channel TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                as_of TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                delivery_status TEXT NOT NULL,
                FOREIGN KEY (watch_id) REFERENCES watches(id)
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_watch_events_one_fired
            ON watch_events(watch_id)
            WHERE event_type = 'fired'
            """
        )
    return _STATE_PATH


def _connect() -> sqlite3.Connection:
    if _STATE_PATH is None:
        init_state_db()
    assert _STATE_PATH is not None
    conn = sqlite3.connect(_STATE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def connect_state() -> sqlite3.Connection:
    """Public connection for copilot_state.db (watches live here, not factory.db)."""
    return _connect()


def record_event(
    *,
    event_type: str,
    conversation_id: str | None = None,
    user_query: str | None = None,
    tool: str | None = None,
    inputs: dict[str, Any] | None = None,
    result_ok: bool | None = None,
    result_summary: str | None = None,
    confirmation_status: str | None = None,
    execution_status: str | None = None,
    target: str | None = None,
) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log (
                timestamp, factory_today, conversation_id, user_query, event_type,
                tool, inputs_json, result_ok, result_summary, confirmation_status,
                execution_status, target
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                FACTORY_TODAY.isoformat(),
                conversation_id,
                user_query,
                event_type,
                tool,
                json.dumps(inputs, ensure_ascii=False, default=str) if inputs else None,
                None if result_ok is None else int(bool(result_ok)),
                (result_summary or "")[:500],
                confirmation_status,
                execution_status,
                target,
            ),
        )
        return int(cur.lastrowid)


def list_audit(limit: int = 20) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw = item.get("inputs_json")
        if raw:
            try:
                item["inputs"] = json.loads(raw)
            except json.JSONDecodeError:
                item["inputs"] = None
        items.append(item)
    return items


def add_note(order_id: str, note: str) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO order_notes (timestamp, order_id, note) VALUES (?, ?, ?)",
            (now, order_id, note),
        )
        return int(cur.lastrowid)


def list_notes(order_id: str | None = None) -> list[dict[str, Any]]:
    with _connect() as conn:
        if order_id:
            rows = conn.execute(
                "SELECT * FROM order_notes WHERE order_id = ? ORDER BY id DESC",
                (order_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM order_notes ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def add_reminder(order_id: str | None, remind_on: str, message: str) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reminders (timestamp, order_id, remind_on, message, status)
            VALUES (?, ?, ?, ?, 'OPEN')
            """,
            (now, order_id, remind_on, message),
        )
        return int(cur.lastrowid)


def list_reminders() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM reminders ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def clear_state() -> None:
    """Test helper. Leaves the schema in place."""
    with _connect() as conn:
        conn.execute("DELETE FROM audit_log")
        conn.execute("DELETE FROM order_notes")
        conn.execute("DELETE FROM reminders")
        conn.execute("DELETE FROM watch_events")
        conn.execute("DELETE FROM watches")
