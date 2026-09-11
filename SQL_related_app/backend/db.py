"""PostgreSQL connection and table helpers."""

from __future__ import annotations

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from config import Config, assert_upload_table

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


def get_postgres_table_count(table_name: str) -> int:
    upload_table = assert_upload_table(table_name)

    query = sql.SQL(
        "SELECT COUNT(*) AS cnt FROM {}.{}"
        ).format(
            sql.Identifier(Config.PG_SCHEMA),
            sql.Identifier(upload_table),
        )
    conn = get_postgres_connection()
    try:
        row = conn.execute(query).fetchone()
        return int(row["cnt"]) if row else 0
    finally:
        conn.close()


def postgres_table_exists(table_name: str) -> bool:
    upload_table = assert_upload_table(table_name)
    conn = get_postgres_admin_connection()
    try:
        row = conn.execute(
            """
            SELECT EXISTS(
                SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = %s
                    AND table_type = 'BASE TABLE'
            ) AS table_exists
            """,
            (Config.PG_SCHEMA, upload_table),
        ).fetchone()
        return bool(row["table_exists"])
    finally:
        conn.close()
