"""REVERT-SUMMARIZE: delete this file to drop grouped-count processing.

Groups rows already returned by a lookup. The model names the column and the
metric. It does not pass rows and does not calculate the numbers.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.common import tool_error, tool_json
from backend.tools.lookup_rows import lookup_rows

logger = logging.getLogger(__name__)


class SummarizeRowsInput(BaseModel):
    group_by: str = Field(
        min_length=1,
        description=(
            "Column name that already exists on the latest lookup rows. "
            "Use that name, not a synonym. status and current_stage are different columns."
        ),
    )
    metric: Literal["count", "sum"] = Field(
        default="count",
        description="count rows in each group, or sum one numeric column.",
    )
    value_column: Optional[str] = Field(
        default=None,
        description="Required when metric is sum. A numeric column on the same rows. Ignored for count.",
    )


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    return keys


@tool(args_schema=SummarizeRowsInput)
def summarize_rows(
    group_by: str,
    metric: Literal["count", "sum"] = "count",
    value_column: Optional[str] = None,
) -> str:
    """Group the latest lookup rows by one existing column.

    Do not pass the rows. Call this after a retrieval tool, before draw or
    render_table, when the manager wants a count or a sum by a column.
    Then chart or tabulate data.rows. This tool does not display a chart.
    """
    tool_name = "summarize_rows"
    column = group_by.strip()
    rows, source = lookup_rows()
    if rows is None:
        return tool_error(
            tool_name,
            "NO_ROWS",
            "No lookup rows are available. Call a retrieval tool before summarizing.",
        )
    if not rows:
        return tool_json(
            {
                "ok": True,
                "tool": tool_name,
                "data": {
                    "source_tool": source,
                    "source_count": 0,
                    "group_by": group_by.strip(),
                    "metric": metric,
                    "value_key": "order_count",
                    "rows": [],
                },
                "trace": {
                    "tool": tool_name,
                    "source_file": source or "previous lookup",
                    "filter": {"group_by": group_by.strip(), "metric": metric},
                    "rows": [],
                    "calculations": [],
                    "basis": "The latest lookup rows were empty, so there was nothing to group.",
                },
            }
        )
    present = _columns(rows)
    if any(column not in row for row in rows):
        return tool_error(
            tool_name,
            "INVALID_INPUT",
            f"'{column}' is not a column on the latest {source or 'lookup'} rows.",
            columns=present,
        )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = "" if row.get(column) is None else str(row.get(column))
        grouped.setdefault(key, []).append(row)

    value_key = "order_count"
    summarized: list[dict[str, Any]] = []
    if metric == "sum":
        measure = (value_column or "").strip()
        if not measure:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "metric sum requires value_column.",
                columns=present,
            )
        if any(measure not in row for row in rows):
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"'{measure}' is not a column on the latest {source or 'lookup'} rows.",
                columns=present,
            )
        value_key = f"{measure}_sum"
        for key in sorted(grouped):
            total = 0.0
            for row in grouped[key]:
                number = _numeric(row.get(measure))
                if number is None:
                    return tool_error(
                        tool_name,
                        "INVALID_INPUT",
                        f"'{measure}' is not numeric on every row.",
                        columns=present,
                    )
                total += number
            summarized.append({column: key, value_key: total})
    else:
        for key in sorted(grouped):
            summarized.append({column: key, value_key: len(grouped[key])})

    logger.info(
        "summarize_rows source=%s group_by=%s metric=%s groups=%s",
        source,
        column,
        metric,
        len(summarized),
    )
    return tool_json(
        {
            "ok": True,
            "tool": tool_name,
            "data": {
                "source_tool": source,
                "source_count": len(rows),
                "group_by": column,
                "metric": metric,
                "value_key": value_key,
                "rows": summarized,
            },
            "trace": {
                "tool": tool_name,
                "source_file": source or "previous lookup",
                "filter": {"group_by": column, "metric": metric, "value_column": value_column},
                "rows": summarized,
                "calculations": [
                    {
                        "name": metric,
                        "result": summarized,
                    }
                ],
                "basis": (
                    "Grouped the latest lookup rows in Python. "
                    "The model did not supply the rows or the numbers."
                ),
            },
        }
    )
