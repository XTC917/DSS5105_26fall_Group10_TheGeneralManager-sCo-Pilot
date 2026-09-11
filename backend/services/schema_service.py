"""Read-only SQL + live schema text for the three business tables.

Migrated from SQL_related_app/backend/schema_service.py.
Reads the shared factory.db through FactoryDB; the SQLite authorizer still
restricts reads to the allowlisted tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.services.data_admin import (
    ALLOWED_TABLES,
    DATA_SOURCES_META,
    assert_allowed_table,
    quote_table,
)
from backend.services.database import FactoryDB, get_db

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}


class SchemaService:
    def _connect(self) -> sqlite3.Connection:
        try:
            db: FactoryDB = get_db()
        except RuntimeError:
            db = FactoryDB()
        db.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _pragma_table_info(self, table_name: str) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                f"PRAGMA table_info({quote_table(table_name)})"
            ).fetchall()
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

    def pragma_table_info(self, table_name: str) -> list[dict[str, Any]]:
        assert_allowed_table(table_name)
        return self._pragma_table_info(table_name)

    def get_live_schema(self) -> str:
        parts = ["Database tables available for query:", ""]
        conn = self._connect()
        try:
            for table_name in ALLOWED_TABLES:
                parts.append(f"## Table: {table_name}")
                parts.append(f"Description: {DATA_SOURCES_META[table_name]['description']}")
                for col in self._pragma_table_info(table_name):
                    pk = " [PRIMARY KEY]" if col["pk"] else ""
                    nullable = " [NOT NULL]" if col["notnull"] else " [NULL]"
                    parts.append(f"  - {col['name']}: {col['type']}{pk}{nullable}")
                count = conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM {quote_table(table_name)}"
                ).fetchone()["cnt"]
                parts.append(f"  Row count: {count}")
                sample = conn.execute(
                    f"SELECT * FROM {quote_table(table_name)} LIMIT 2"
                ).fetchall()
                if sample:
                    parts.append("  Sample data:")
                    for row in sample:
                        parts.append(f"    {dict(row)}")
                parts.append("")
        finally:
            conn.close()

        parts.extend(
            [
                "## Business Rules",
                "- Factory is closed on Sundays (production_log has 0 pieces_completed)",
                "- Production stages: KNITTING -> ASSEMBLY -> WASHING -> PACKING",
                "- days_late = completed_date - due_date (negative means early, NULL means not completed)",
                "- Only ACTIVE workshops can take new orders",
                "- Current date is 2026-04-01",
            ]
        )
        return "\n".join(parts)

    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        stripped = sql.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1].strip()
        if not stripped:
            raise ValueError("SQL statement is required")
        if ";" in stripped:
            raise ValueError("Multiple SQL statements are not allowed")
        if not stripped.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        conn = self._connect()

        def _authorizer(action, arg1, _arg2, _dbname, _source):
            if action not in _ALLOWED_ACTIONS:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and arg1:
                if arg1 not in ALLOWED_TABLES:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        try:
            conn.set_authorizer(_authorizer)
            rows = conn.execute(stripped).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.DatabaseError as exc:
            raise ValueError(str(exc)) from exc
        finally:
            conn.close()


schema_service = SchemaService()
