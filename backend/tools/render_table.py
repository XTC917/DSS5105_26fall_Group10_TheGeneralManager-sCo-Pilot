"""Structured table output tool for grounded factory data."""

from __future__ import annotations

import math
from contextvars import ContextVar, Token
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.common import tool_error, tool_json

_FRONTEND_TABLES: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "frontend_tables", default=None
)
_FRONTEND_TABLE_MESSAGE = "The table has already been generated in the frontend."


def bind_frontend_tables() -> Token[list[dict[str, Any]] | None]:
    return _FRONTEND_TABLES.set([])


def take_frontend_tables(token: Token[list[dict[str, Any]] | None]) -> list[dict[str, Any]]:
    tables = list(_FRONTEND_TABLES.get() or [])
    _FRONTEND_TABLES.reset(token)
    return tables


class TableColumn(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=60)


class RenderTableInput(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    columns: list[TableColumn] = Field(min_length=1, max_length=12)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=100)


@tool(args_schema=RenderTableInput)
def render_table(
    title: str,
    columns: list[TableColumn],
    rows: list[dict[str, Any]],
) -> str:
    """Format rows returned by a factory data tool as a readable table.

    Calling this tool displays the table. Do not write those rows again in the reply.
    Use after retrieving the rows from another tool. Include only supplied values;
    do not invent, calculate, or aggregate table cells.
    """
    tool_name = "render_table"
    keys = [column.key for column in columns]
    if len(set(keys)) != len(keys):
        return tool_error(tool_name, "INVALID_COLUMNS", "Column keys must be unique.")

    for row in rows:
        if not set(keys).issubset(row):
            return tool_error(tool_name, "INVALID_DATA", "Every row must include all requested column keys.")
        for key in keys:
            value = row[key]
            if value is not None and not isinstance(value, (str, int, float, bool)):
                return tool_error(tool_name, "INVALID_DATA", f"Table cell '{key}' must be a scalar value.")
            if isinstance(value, float) and not math.isfinite(value):
                return tool_error(tool_name, "INVALID_DATA", f"Table cell '{key}' must be a finite number.")

    table = {
        "title": title.strip(),
        "columns": [column.model_dump() for column in columns],
        "rows": [{key: row[key] for key in keys} for row in rows],
    }
    bucket = _FRONTEND_TABLES.get()
    if bucket is not None:
        bucket.append(table)
    return tool_json(
        {"ok": True, "tool": tool_name, "data": {"message": _FRONTEND_TABLE_MESSAGE}}
    )