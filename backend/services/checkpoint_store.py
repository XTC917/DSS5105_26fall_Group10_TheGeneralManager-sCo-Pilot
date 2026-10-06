"""Runtime connection pool for LangGraph PostgreSQL checkpoints."""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.pg_config import (
    COPILOT_SCHEMA,
    PG_CONNECT_TIMEOUT,
    postgres_dsn,
)


_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@contextmanager
def postgres_checkpointer() -> Generator[PostgresSaver, None, None]:
    """Open the application checkpoint pool and close it on shutdown."""

    if not _SCHEMA_PATTERN.fullmatch(COPILOT_SCHEMA):
        raise RuntimeError("PG_COPILOT_SCHEMA is not a valid SQL identifier")

    pool = ConnectionPool(
        conninfo=postgres_dsn(admin=True),
        min_size=1,
        max_size=4,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "options": f"-csearch_path={COPILOT_SCHEMA}",
        },
    )

    pool.open()
    try:
        pool.wait(timeout=PG_CONNECT_TIMEOUT)
        yield PostgresSaver(pool)
    finally:
        pool.close()


def restrict_checkpoint_access() -> None:
    """setup() creates tables as admin, and copilot's default privilege then
    grants factory_agent read and write. Conversation rows stay admin-only;
    checkpoint rows must too, or the agent role can read every user's memory.
    """
    from backend.services.pg_database import connect

    with connect(admin=True) as conn, conn.transaction():
        conn.execute(
            """
            DO $$
            DECLARE role_name text;
            DECLARE table_name text;
            BEGIN
                FOREACH table_name IN ARRAY ARRAY[
                    'checkpoints',
                    'checkpoint_blobs',
                    'checkpoint_writes',
                    'checkpoint_migrations'
                ]
                LOOP
                    IF to_regclass(format('copilot.%I', table_name)) IS NULL THEN
                        CONTINUE;
                    END IF;
                    EXECUTE format(
                        'REVOKE ALL ON TABLE copilot.%I FROM PUBLIC',
                        table_name
                    );
                    FOREACH role_name IN ARRAY ARRAY[
                        'factory_reader', 'factory_user', 'factory_agent'
                    ]
                    LOOP
                        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                            EXECUTE format(
                                'REVOKE ALL ON TABLE copilot.%I FROM %I',
                                table_name,
                                role_name
                            );
                        END IF;
                    END LOOP;
                END LOOP;
            END $$
            """
        )