"""Small psycopg3 connection layer with trusted and read-only identities."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from backend.pg_config import (
    PG_CONNECT_TIMEOUT,
    PG_READ_STATEMENT_TIMEOUT_MS,
    PG_STATEMENT_TIMEOUT_MS,
    postgres_dsn,
)


def connect(*, admin: bool = False) -> psycopg.Connection:
    conn = psycopg.connect(
        postgres_dsn(admin=admin),
        connect_timeout=PG_CONNECT_TIMEOUT,
        row_factory=dict_row,
    )
    # SET 不接受绑定参数，必须内插为字面量整数（毫秒）。
    timeout_ms = int(PG_STATEMENT_TIMEOUT_MS if admin else PG_READ_STATEMENT_TIMEOUT_MS)
    conn.execute(f"SET statement_timeout = {timeout_ms}")
    return conn


@contextmanager
def db_connection(*, admin: bool = False) -> Iterator[psycopg.Connection]:
    conn = connect(admin=admin)
    try:
        yield conn
    finally:
        conn.close()
