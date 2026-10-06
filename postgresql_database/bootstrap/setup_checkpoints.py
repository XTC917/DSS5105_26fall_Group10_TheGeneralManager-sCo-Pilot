"""Initialize LangGraph checkpoint tables in the copilot schema."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import sql
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set in .env")
    return value


def main() -> None:
    schema = os.getenv("PG_COPILOT_SCHEMA", "copilot")

    with psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "factory_copilot_db"),
        user=os.getenv("PG_ADMIN_USER", "factory_admin"),
        password=required_env("PG_ADMIN_PASSWORD"),
        connect_timeout=int(os.getenv("PGCONNECT_TIMEOUT", "5")),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    ) as connection:
        schema_row = connection.execute(
            """
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = %s
            """,
            (schema,),
        ).fetchone()

        if schema_row is None:
            raise RuntimeError(
                f"Schema {schema!r} does not exist. Run Alembic first."
            )

        connection.execute(
            sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
        )

        checkpointer = PostgresSaver(connection)
        checkpointer.setup()

        rows = connection.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = %s
              AND tablename LIKE 'checkpoint%%'
            ORDER BY tablename
            """,
            (schema,),
        ).fetchall()

    tables = [row["tablename"] for row in rows]
    if not tables:
        raise RuntimeError("No checkpoint tables were created")

    print(f"LangGraph checkpoint schema initialized: {schema}")
    for table in tables:
        print(f"- {schema}.{table}")


if __name__ == "__main__":
    main()