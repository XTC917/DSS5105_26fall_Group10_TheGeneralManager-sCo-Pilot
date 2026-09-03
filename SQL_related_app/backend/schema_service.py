from __future__ import annotations

import sqlite3
from typing import Dict, List

from config import Config, quote_table
from db import get_connection, pragma_table_info


_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}


class SchemaService:
    def get_live_schema(self) -> str:
        parts = ["Database tables available for query:", ""]
        conn = get_connection()
        try:
            for table_name in Config.ALLOWED_TABLES:
                parts.append(f"## Table: {table_name}")
                desc = Config.DATA_SOURCES[table_name]["description"]
                parts.append(f"Description: {desc}")
                for col in pragma_table_info(table_name):
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

    def execute_query(self, sql: str) -> List[Dict]:
        stripped = sql.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1].strip()
        if not stripped:
            raise ValueError("SQL statement is required")
        if ";" in stripped:
            raise ValueError("Multiple SQL statements are not allowed")
        if not stripped.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        conn = get_connection()

        def _authorizer(action, arg1, _arg2, _dbname, _source):
            if action not in _ALLOWED_ACTIONS:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and arg1:
                if arg1 not in Config.ALLOWED_TABLES:
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
