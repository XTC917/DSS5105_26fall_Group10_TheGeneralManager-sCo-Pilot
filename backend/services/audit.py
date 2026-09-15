"""User-scoped PostgreSQL Copilot state repository."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect
from backend.services.request_context import get_current_user_id


def record_event(*, user_id: int | None = None, event_type: str, conversation_id: str | None = None,
                 user_query: str | None = None, tool: str | None = None, inputs: dict[str, Any] | None = None,
                 result_ok: bool | None = None, result_summary: str | None = None,
                 confirmation_status: str | None = None, execution_status: str | None = None,
                 target: str | None = None) -> int:
    if user_id is None:
        try:
            user_id = get_current_user_id(required=False)
        except PermissionError:
            user_id = None
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(f"""INSERT INTO {COPILOT_SCHEMA}.audit_log
            (user_id,timestamp,factory_today,conversation_id,user_query,event_type,tool,inputs_json,result_ok,result_summary,confirmation_status,execution_status,target)
            VALUES (%s,CURRENT_TIMESTAMP,'2026-04-01',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (user_id, conversation_id, user_query, event_type, tool,
             json.dumps(inputs, ensure_ascii=False, default=str) if inputs else None,
             result_ok, (result_summary or "")[:500], confirmation_status, execution_status, target)).fetchone()
    return int(row["id"])


def list_audit(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    resolved = user_id if user_id is not None else get_current_user_id(required=False)
    with connect(admin=True) as conn:
        if resolved is None:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.audit_log ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.audit_log WHERE user_id=%s ORDER BY id DESC LIMIT %s", (resolved, limit)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        if isinstance(item.get("inputs_json"), str):
            item["inputs"] = json.loads(item["inputs_json"])
        items.append(item)
    return items


def add_note(*, user_id: int | None = None, order_id: str, note: str) -> int:
    resolved = user_id if user_id is not None else get_current_user_id(required=False)
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(f"INSERT INTO {COPILOT_SCHEMA}.order_notes (user_id,timestamp,order_id,note) VALUES (%s,CURRENT_TIMESTAMP,%s,%s) RETURNING id", (resolved, order_id, note)).fetchone()
    return int(row["id"])


def list_notes(*, user_id: int | None = None, order_id: str | None = None) -> list[dict[str, Any]]:
    resolved = user_id if user_id is not None else get_current_user_id(required=False)
    with connect(admin=True) as conn:
        if resolved is None:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.order_notes ORDER BY id DESC").fetchall()
        elif order_id:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.order_notes WHERE user_id=%s AND order_id=%s ORDER BY id DESC", (resolved, order_id)).fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.order_notes WHERE user_id=%s ORDER BY id DESC", (resolved,)).fetchall()
    return [dict(row) for row in rows]


def add_reminder(*, user_id: int | None = None, order_id: str | None, remind_on: str, message: str) -> int:
    resolved = user_id if user_id is not None else get_current_user_id(required=False)
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(f"INSERT INTO {COPILOT_SCHEMA}.reminders (user_id,timestamp,order_id,remind_on,message,status) VALUES (%s,CURRENT_TIMESTAMP,%s,%s,%s,'OPEN') RETURNING id", (resolved, order_id, remind_on, message)).fetchone()
    return int(row["id"])


def list_reminders(*, user_id: int | None = None) -> list[dict[str, Any]]:
    resolved = user_id if user_id is not None else get_current_user_id(required=False)
    with connect(admin=True) as conn:
        if resolved is None:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.reminders ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(f"SELECT * FROM {COPILOT_SCHEMA}.reminders WHERE user_id=%s ORDER BY id DESC", (resolved,)).fetchall()
    return [dict(row) for row in rows]


def clear_state() -> None:
    """Test helper that clears user-scoped copilot rows without changing schema."""
    with connect(admin=True) as conn, conn.transaction():
        conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.watch_events")
        conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.watches")
        conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.order_notes")
        conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.reminders")
        conn.execute(f"DELETE FROM {COPILOT_SCHEMA}.audit_log")
