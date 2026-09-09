from __future__ import annotations

from typing import Dict, List

import psycopg
from psycopg import sql

from config import Config
from db import get_postgres_connection


class SchemaService:
    def get_live_schema(self) -> str:
        parts = ["Database tables available for query:", ""]
        conn = get_postgres_connection()
        try:
            for table_name in Config.QUERY_CONTEXT_TABLES:
                parts.append(f"## Table: {table_name}")
                description = Config.QUERY_CONTEXT_DESCRIPTIONS[table_name]
                parts.append(f"Description: {description}")

                columns = conn.execute(
                    """
                    SELECT
                        column_name,
                        CASE
                            WHEN data_type = 'numeric'
                            THEN
                                'numeric(' || numeric_precision || ', ' || numeric_scale || ')'
                            ELSE data_type
                        END AS display_type,
                        is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                        AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (Config.PG_SCHEMA, table_name),
                ).fetchall()

                primary_key_rows = conn.execute(
                    """
                    SELECT attribute.attname AS column_name
                    FROM pg_catalog.pg_constraint AS constraint_info
                    JOIN pg_catalog.pg_class AS table_info
                      ON table_info.oid = constraint_info.conrelid
                    JOIN pg_catalog.pg_namespace AS schema_info
                      ON schema_info.oid = table_info.relnamespace
                    CROSS JOIN LATERAL
                      unnest(constraint_info.conkey) WITH ORDINALITY
                      AS key_column(attribute_number, key_position)
                    JOIN pg_catalog.pg_attribute AS attribute
                      ON attribute.attrelid = table_info.oid
                      AND attribute.attnum = key_column.attribute_number
                    WHERE constraint_info.contype = 'p'
                      AND schema_info.nspname = %s
                      AND table_info.relname = %s
                    ORDER BY key_column.key_position
                    """,
                    (Config.PG_SCHEMA, table_name),
                ).fetchall()

                primary_keys = {row["column_name"] for row in primary_key_rows}

                for column in columns:
                    primary_key = " [PRIMARY KEY]" if column["column_name"] in primary_keys else ""
                    nullable = " [NULL]" if column["is_nullable"] == "YES" else " [NOT NULL]"
                    parts.append(f"  - {column['column_name']}: {column['display_type']}{primary_key}{nullable}")

                qualified_table = sql.Identifier(Config.PG_SCHEMA, table_name)

                count_query = sql.SQL(
                    "SELECT COUNT(*) AS cnt FROM {}"
                ).format(qualified_table)

                count = conn.execute(count_query).fetchone()["cnt"]
                parts.append(f"  Row count: {count}")

                sample_query = sql.SQL(
                    "SELECT * FROM {} LIMIT 2"
                ).format(qualified_table)

                sample = conn.execute(sample_query).fetchall()

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
                "- workshops stores one row per workshop-category capability",
                "- Count physical workshops with COUNT(DISTINCT workshop_id)",
                "- snapshot stores prior IN_PROGRESS order stage observations",
                "- Combine snapshot with current IN_PROGRESS orders to query order stage history",
                "- Current date is 2026-04-01",
            ]
        )
        return "\n".join(parts)

    def execute_query(self, query_text: str) -> List[Dict]:
        stripped = query_text.strip()
        if stripped.endswith(";"):
            stripped = stripped[:-1].strip()
        if not stripped:
            raise ValueError("SQL statement is required")
        if ";" in stripped:
            raise ValueError("Multiple SQL statements are not allowed")
        if not stripped.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        conn = get_postgres_connection()

        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                conn.execute("SET LOCAL statement_timeout = '5s'")

                search_path_query = sql.SQL(
                    "SET LOCAL search_path TO {}, pg_catalog"
                ).format(sql.Identifier(Config.PG_SCHEMA))

                conn.execute(search_path_query)

                cursor = conn.execute(stripped)
                rows = cursor.fetchmany(101)

                return [dict(row) for row in rows]
        except psycopg.Error as exc:
            raise ValueError(str(exc)) from exc
        finally:
            conn.close()


schema_service = SchemaService()
