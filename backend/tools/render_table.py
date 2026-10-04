"""Structured table output tool for grounded factory data."""

from __future__ import annotations

import math
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.common import tool_error, tool_json


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

    Use after retrieving the rows from another tool, especially for lists of
    orders, risks, issues, or stage summaries. Include only supplied values;
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
    return tool_json({"ok": True, "tool": tool_name, "data": {"table": table}})