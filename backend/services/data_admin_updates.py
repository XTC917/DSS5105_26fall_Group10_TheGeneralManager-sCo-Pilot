"""Safe, transactional administrator updates for existing business rows."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.pg_config import ADMIN_META_SCHEMA, PG_SCHEMA
from backend.services.data_admin import assert_allowed_table
from backend.services.pg_database import connect


MAX_BATCH_SIZE = 50

_TABLE_COLUMNS = {
    "orders": (
        "order_id",
        "customer",
        "product",
        "category",
        "pieces",
        "order_date",
        "due_date",
        "status",
        "current_stage",
        "last_activity_date",
        "completed_date",
        "days_late",
    ),
    "production_log": ("production_date", "stage", "pieces_completed"),
    "workshops": (
        "workshop_id",
        "name",
        "capacity_pieces_per_day",
        "pickup_lead_days",
        "defect_rate",
        "cost_per_piece",
        "makes",
        "status",
        "max_batch_pieces",
        "current_queue_days",
        "notes",
    ),
}

_PRIMARY_KEYS = {
    "orders": ("order_id",),
    "production_log": ("production_date", "stage"),
    "workshops": ("workshop_id", "makes"),
}


class DataSourceNotFoundError(LookupError):
    """The requested data source does not exist or is inactive."""


class DataRowNotFoundError(LookupError):
    """A row key does not identify an existing business row."""


class DataUpdateValidationError(ValueError):
    """The requested update is outside the bounded update contract."""


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _json_object(values: Mapping) -> dict:
    return {key: _json_value(value) for key, value in values.items()}


def _validated_update(table_name: str, item: Mapping) -> tuple[dict, dict]:
    key = item.get("key")
    changes = item.get("changes")
    if not isinstance(key, Mapping) or not isinstance(changes, Mapping):
        raise DataUpdateValidationError("Each update requires key and changes objects")

    expected_keys = _PRIMARY_KEYS[table_name]
    if set(key) != set(expected_keys):
        expected = ", ".join(expected_keys)
        raise DataUpdateValidationError(f"Row key must contain exactly: {expected}")
    if any(key[column] is None for column in expected_keys):
        raise DataUpdateValidationError("Row key values cannot be null")
    if not changes:
        raise DataUpdateValidationError("changes cannot be empty")

    primary_keys = set(expected_keys)
    requested_columns = set(changes)
    attempted_primary_keys = requested_columns & primary_keys
    if attempted_primary_keys:
        names = ", ".join(sorted(attempted_primary_keys))
        raise DataUpdateValidationError(f"Primary-key columns cannot be changed: {names}")

    editable_columns = set(_TABLE_COLUMNS[table_name]) - primary_keys
    unknown_columns = requested_columns - editable_columns
    if unknown_columns:
        names = ", ".join(sorted(unknown_columns))
        raise DataUpdateValidationError(f"Columns are not editable for {table_name}: {names}")

    return dict(key), dict(changes)


def update_datasource_rows(
    datasource_id: int,
    *,
    actor_user_id: int,
    updates: Sequence[Mapping],
) -> dict:
    """Apply one bounded batch atomically and record before/after evidence."""

    if not updates or len(updates) > MAX_BATCH_SIZE:
        raise DataUpdateValidationError(
            f"updates must contain between 1 and {MAX_BATCH_SIZE} rows"
        )

    request_id = uuid4()
    try:
        with connect(admin=True) as connection, connection.transaction():
            source = connection.execute(
                sql.SQL(
                    "SELECT id, table_name, is_active FROM {}.data_sources "
                    "WHERE id = %s FOR UPDATE"
                ).format(sql.Identifier(ADMIN_META_SCHEMA)),
                (datasource_id,),
            ).fetchone()
            if source is None or not source["is_active"]:
                raise DataSourceNotFoundError("Active data source not found")

            table_name = assert_allowed_table(source["table_name"])
            validated = [_validated_update(table_name, item) for item in updates]

            seen_keys: set[str] = set()
            for key, _changes in validated:
                marker = json.dumps(_json_object(key), sort_keys=True)
                if marker in seen_keys:
                    raise DataUpdateValidationError(
                        "The same row cannot appear twice in one batch"
                    )
                seen_keys.add(marker)

            updated_rows: list[dict] = []
            table_identifier = sql.Identifier(PG_SCHEMA, table_name)
            primary_keys = _PRIMARY_KEYS[table_name]

            for key, changes in validated:
                where_clause = sql.SQL(" AND ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column))
                    for column in primary_keys
                )
                key_values = tuple(key[column] for column in primary_keys)
                before = connection.execute(
                    sql.SQL("SELECT * FROM {} WHERE {} FOR UPDATE").format(
                        table_identifier,
                        where_clause,
                    ),
                    key_values,
                ).fetchone()
                if before is None:
                    raise DataRowNotFoundError(
                        f"Row not found in {table_name}: {_json_object(key)}"
                    )

                change_columns = tuple(changes)
                set_clause = sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(column))
                    for column in change_columns
                )
                after = connection.execute(
                    sql.SQL("UPDATE {} SET {} WHERE {} RETURNING *").format(
                        table_identifier,
                        set_clause,
                        where_clause,
                    ),
                    tuple(changes[column] for column in change_columns) + key_values,
                ).fetchone()

                connection.execute(
                    sql.SQL(
                        "INSERT INTO {}.data_change_audit "
                        "(request_id, actor_user_id, actor_label, datasource_id, table_name, "
                        "row_key, before_json, after_json) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    ).format(sql.Identifier(ADMIN_META_SCHEMA)),
                    (
                        request_id,
                        actor_user_id,
                        f"user:{actor_user_id}",
                        datasource_id,
                        table_name,
                        Jsonb(_json_object(key)),
                        Jsonb(_json_object(before)),
                        Jsonb(_json_object(after)),
                    ),
                )
                updated_rows.append(dict(after))

            connection.execute(
                sql.SQL(
                    "UPDATE {}.data_sources SET updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = %s"
                ).format(sql.Identifier(ADMIN_META_SCHEMA)),
                (datasource_id,),
            )
    except (psycopg.IntegrityError, psycopg.DataError) as exc:
        raise DataUpdateValidationError(
            "Update violates the database constraints for this table"
        ) from exc

    return {
        "success": True,
        "request_id": request_id,
        "datasource_id": datasource_id,
        "table_name": table_name,
        "updated_count": len(updated_rows),
        "rows": updated_rows,
    }
