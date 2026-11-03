"""Bounded row updates for the trusted local SQL administration app."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from config import Config, assert_upload_table
from db import get_postgres_admin_connection


MAX_BATCH_SIZE = 50
LOCAL_ACTOR_LABEL = "sql-related-app-local-admin"

TABLE_COLUMNS = {
    "orders": (
        "order_id", "customer", "product", "category", "pieces",
        "order_date", "due_date", "status", "current_stage",
        "last_activity_date", "completed_date", "days_late",
    ),
    "production_log": ("production_date", "stage", "pieces_completed"),
    "workshops": (
        "workshop_id", "name", "capacity_pieces_per_day",
        "pickup_lead_days", "defect_rate", "cost_per_piece", "makes",
        "status", "max_batch_pieces", "current_queue_days", "notes",
    ),
}

PRIMARY_KEYS = {
    "orders": ("order_id",),
    "production_log": ("production_date", "stage"),
    "workshops": ("workshop_id", "makes"),
}


class DataSourceNotFoundError(LookupError):
    pass


class DataRowNotFoundError(LookupError):
    pass


class DataUpdateValidationError(ValueError):
    pass


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _json_object(values: Mapping) -> dict:
    return {key: _json_value(value) for key, value in values.items()}


def _validate_update(table_name: str, item: Mapping) -> tuple[dict, dict]:
    key = item.get("key")
    changes = item.get("changes")
    if not isinstance(key, Mapping) or not isinstance(changes, Mapping):
        raise DataUpdateValidationError("Each update requires key and changes objects")

    primary_keys = PRIMARY_KEYS[table_name]
    if set(key) != set(primary_keys):
        raise DataUpdateValidationError(
            f"Row key must contain exactly: {', '.join(primary_keys)}"
        )
    if any(key[column] is None for column in primary_keys):
        raise DataUpdateValidationError("Row key values cannot be null")
    if not changes:
        raise DataUpdateValidationError("changes cannot be empty")

    attempted_keys = set(changes) & set(primary_keys)
    if attempted_keys:
        raise DataUpdateValidationError(
            "Primary-key columns cannot be changed: "
            + ", ".join(sorted(attempted_keys))
        )
    unknown = set(changes) - (set(TABLE_COLUMNS[table_name]) - set(primary_keys))
    if unknown:
        raise DataUpdateValidationError(
            f"Columns are not editable for {table_name}: "
            + ", ".join(sorted(unknown))
        )
    return dict(key), dict(changes)


def update_rows(datasource_id: int, updates: Sequence[Mapping]) -> dict:
    if not updates or len(updates) > MAX_BATCH_SIZE:
        raise DataUpdateValidationError(
            f"updates must contain between 1 and {MAX_BATCH_SIZE} rows"
        )

    request_id = uuid4()
    connection = get_postgres_admin_connection()
    try:
        with connection.transaction():
            source = connection.execute(
                """
                SELECT id, table_name, is_active
                FROM admin_meta.data_sources
                WHERE id = %s
                FOR UPDATE
                """,
                (datasource_id,),
            ).fetchone()
            if source is None or not source["is_active"]:
                raise DataSourceNotFoundError("Active data source not found")

            table_name = assert_upload_table(source["table_name"])
            validated = [_validate_update(table_name, item) for item in updates]
            seen: set[str] = set()
            for key, _changes in validated:
                marker = json.dumps(_json_object(key), sort_keys=True)
                if marker in seen:
                    raise DataUpdateValidationError(
                        "The same row cannot appear twice in one batch"
                    )
                seen.add(marker)

            table = sql.Identifier(Config.PG_SCHEMA, table_name)
            primary_keys = PRIMARY_KEYS[table_name]
            changed_rows: list[dict] = []

            for key, changes in validated:
                where_clause = sql.SQL(" AND ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column))
                    for column in primary_keys
                )
                key_values = tuple(key[column] for column in primary_keys)
                before = connection.execute(
                    sql.SQL("SELECT * FROM {} WHERE {} FOR UPDATE").format(
                        table, where_clause
                    ),
                    key_values,
                ).fetchone()
                if before is None:
                    raise DataRowNotFoundError(
                        f"Row not found in {table_name}: {_json_object(key)}"
                    )

                columns = tuple(changes)
                set_clause = sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column))
                    for column in columns
                )
                after = connection.execute(
                    sql.SQL("UPDATE {} SET {} WHERE {} RETURNING *").format(
                        table, set_clause, where_clause
                    ),
                    tuple(changes[column] for column in columns) + key_values,
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO admin_meta.data_change_audit (
                        request_id, actor_user_id, actor_label, datasource_id,
                        table_name, row_key, before_json, after_json
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        request_id,
                        LOCAL_ACTOR_LABEL,
                        datasource_id,
                        table_name,
                        Jsonb(_json_object(key)),
                        Jsonb(_json_object(before)),
                        Jsonb(_json_object(after)),
                    ),
                )
                changed_rows.append(dict(after))

            connection.execute(
                """
                UPDATE admin_meta.data_sources
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (datasource_id,),
            )
    except (psycopg.IntegrityError, psycopg.DataError) as exc:
        raise DataUpdateValidationError(
            "Update violates the database constraints for this table"
        ) from exc
    finally:
        connection.close()

    return {
        "success": True,
        "request_id": request_id,
        "datasource_id": datasource_id,
        "table_name": table_name,
        "updated_count": len(changed_rows),
        "rows": changed_rows,
    }
