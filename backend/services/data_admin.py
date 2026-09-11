"""Data Admin safety primitives.

Migrated from SQL_related_app/backend/config.py (identifier allowlist only).
Path/env settings stay in backend.config + backend.services.database.
"""

from __future__ import annotations

import re

_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ALLOWED_TABLES = ("orders", "production_log", "workshops")

FILE_TABLE_MAPPING = {
    "orders.csv": "orders",
    "production_log.csv": "production_log",
    "workshops.csv": "workshops",
}

DATA_SOURCES_META = {
    "orders": {
        "source_name": "Orders",
        "original_file": "orders.csv",
        "description": "Customer order information, includes TOPS and ACCESSORIES categories",
    },
    "production_log": {
        "source_name": "Production Log",
        "original_file": "production_log.csv",
        "description": "Daily production output by stage",
    },
    "workshops": {
        "source_name": "Workshops",
        "original_file": "workshops.csv",
        "description": "External workshop capacity and cost information",
    },
}

TABLE_SCHEMAS = {
    "orders": {
        "columns": [
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
        ],
        "date_columns": [
            "order_date",
            "due_date",
            "last_activity_date",
            "completed_date",
        ],
        "int_columns": ["pieces", "days_late"],
        "float_columns": [],
        "nullable_columns": ["completed_date", "days_late"],
    },
    "production_log": {
        "columns": ["date", "stage", "pieces_completed"],
        "date_columns": ["date"],
        "int_columns": ["pieces_completed"],
        "float_columns": [],
        "nullable_columns": [],
    },
    "workshops": {
        "columns": [
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
        ],
        "date_columns": [],
        "int_columns": [
            "capacity_pieces_per_day",
            "pickup_lead_days",
            "max_batch_pieces",
        ],
        "float_columns": [
            "defect_rate",
            "cost_per_piece",
            "current_queue_days",
        ],
        "nullable_columns": ["max_batch_pieces", "notes"],
    },
}


def assert_allowed_table(table_name: str) -> str:
    if not table_name or table_name not in ALLOWED_TABLES:
        allowed = ", ".join(ALLOWED_TABLES)
        raise ValueError(f"table_name must be one of: {allowed}")
    return table_name


def quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier: {name}")
    return f'"{name}"'


def quote_table(table_name: str) -> str:
    return quote_ident(assert_allowed_table(table_name))


def quote_column(table_name: str, column: str) -> str:
    schema = TABLE_SCHEMAS[assert_allowed_table(table_name)]
    if column not in schema["columns"]:
        raise ValueError(f"Unknown column {column} for table {table_name}")
    return quote_ident(column)
