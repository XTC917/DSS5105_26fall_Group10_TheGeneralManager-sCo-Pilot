"""Read-only PostgreSQL SQL gateway for approved operational tables."""
from __future__ import annotations

from typing import Any

from psycopg import sql

from backend.pg_config import PG_SCHEMA
from backend.services.data_admin import ALLOWED_TABLES, DATA_SOURCES_META, assert_allowed_table, quote_table
from backend.services.pg_database import connect


class SchemaService:
    def _columns(self, table_name: str) -> list[dict[str, Any]]:
        assert_allowed_table(table_name)
        with connect() as conn:
            rows = conn.execute(
                """SELECT ordinal_position AS cid, column_name AS name, data_type AS type,
                    (is_nullable = 'NO') AS notnull
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position""",
                (PG_SCHEMA, table_name),
            ).fetchall()
        return [dict(row) | {"dflt_value": None, "pk": 0} for row in rows]

    def pragma_table_info(self, table_name: str):
        return self._columns(table_name)

    def get_live_schema(self) -> str:
        parts = ["Database tables available for query:", ""]
        with connect() as conn:
            for table_name in ALLOWED_TABLES:
                parts.extend([f"## Table: {table_name}", f"Description: {DATA_SOURCES_META[table_name]['description']}"])
                for col in self._columns(table_name):
                    parts.append(f"  - {col['name']}: {col['type']}" + (" [NOT NULL]" if col["notnull"] else " [NULL]"))
                count = conn.execute(sql.SQL("SELECT COUNT(*) AS cnt FROM {}.{}").format(sql.Identifier(PG_SCHEMA), sql.Identifier(table_name))).fetchone()["cnt"]
                parts.append(f"  Row count: {count}")
                parts.append("")
        parts.extend(["## Business Rules", "- Factory is closed on Sundays", "- Order lifecycle: ORDERED -> KNITTING -> ASSEMBLY -> WASHING -> PACKING -> COMPLETE", "- production_log stages: KNITTING -> ASSEMBLY -> WASHING -> PACKING", "- Current date is 2026-04-01"])
        return "\n".join(parts)

    def execute_query(self, query_text: str) -> list[dict[str, Any]]:
        stripped = query_text.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1].strip()
        if not stripped or ";" in stripped or not stripped.upper().startswith("SELECT"):
            raise ValueError("Only one SELECT statement is allowed")
        with connect() as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SET LOCAL statement_timeout = '5s'")
                conn.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(sql.Identifier(PG_SCHEMA)))
                rows = conn.execute(stripped).fetchmany(101)
        return [dict(row) for row in rows]


schema_service = SchemaService()
