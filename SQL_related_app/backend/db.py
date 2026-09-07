"""Database helpers for the legacy SQLite backend and PostgreSQL integration."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Sequence

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from config import Config, assert_allowed_table, quote_table

def get_postgres_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=Config.PG_HOST,
        port=Config.PG_PORT,
        dbname=Config.PG_DATABASE,
        user=Config.PG_USER,
        password=Config.PG_PASSWORD,
        connect_timeout=Config.PG_CONNECT_TIMEOUT,
        row_factory=dict_row,
    )


def get_postgres_admin_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=Config.PG_HOST,
        port=Config.PG_PORT,
        dbname=Config.PG_DATABASE,
        user=Config.PG_ADMIN_USER,
        password=Config.PG_ADMIN_PASSWORD,
        connect_timeout=Config.PG_CONNECT_TIMEOUT,
        row_factory=dict_row,
    )


def get_connection() -> sqlite3.Connection:
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(Config.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_postgres_table_count(table_name: str) -> int:
    allowed_table = assert_allowed_table(table_name)

    query = sql.SQL(
        "SELECT COUNT(*) AS cnt FROM {}.{}"
        ).format(
            sql.Identifier(Config.PG_SCHEMA),
            sql.Identifier(allowed_table),
        )
    conn = get_postgres_connection()
    try:
        row = conn.execute(query).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


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
