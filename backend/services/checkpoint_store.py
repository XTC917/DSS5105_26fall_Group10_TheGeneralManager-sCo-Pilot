"""Runtime connection pool for LangGraph PostgreSQL checkpoints."""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.pg_config import COPILOT_SCHEMA, PG_CONNECT_TIMEOUT, postgres_dsn


_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@contextmanager
def postgres_checkpointer() -> Generator[PostgresSaver, None, None]:
    """Open the checkpoint pool; schema creation remains Alembic-owned."""

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
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT max(v) AS version FROM checkpoint_migrations"
            ).fetchone()
            expected = len(PostgresSaver.MIGRATIONS) - 1
            if row is None or row["version"] != expected:
                raise RuntimeError(
                    "Checkpoint schema is outdated. Run alembic upgrade head."
                )
        yield PostgresSaver(pool)
    finally:
        pool.close()
