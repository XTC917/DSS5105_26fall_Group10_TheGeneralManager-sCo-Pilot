"""SQLite helpers. Identifiers are allowlisted; values use bound parameters."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Sequence

from config import Config, quote_table


def get_connection() -> sqlite3.Connection:
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(Config.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute_query(sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_table_count(table_name: str) -> int:
    sql = f"SELECT COUNT(*) AS cnt FROM {quote_table(table_name)}"
    conn = get_connection()
    try:
        row = conn.execute(sql).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def table_exists(table_name: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def pragma_table_info(table_name: str) -> List[Dict[str, Any]]:
    sql = f"PRAGMA table_info({quote_table(table_name)})"
    conn = get_connection()
    try:
        rows = conn.execute(sql).fetchall()
        return [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "dflt_value": row["dflt_value"],
                "pk": row["pk"],
            }
            for row in rows
        ]
    finally:
        conn.close()
