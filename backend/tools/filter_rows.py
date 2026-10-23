"""Keep rows from the original lookup. The model names the conditions, not the rows."""

from __future__ import annotations

import logging
import statistics
from typing import Any, Literal, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.common import tool_error, tool_json
from backend.tools.lookup_rows import initial_rows, set_working_rows

logger = logging.getLogger(__name__)

_OPS = (
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "in",
    "gt_median",
    "gte_median",
    "lt_median",
    "lte_median",
)
_MEDIAN_OPS = frozenset({"gt_median", "gte_median", "lt_median", "lte_median"})


class RowFilter(BaseModel):
    column: str = Field(min_length=1, description="Column name on the original lookup rows.")
    op: Literal[
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "contains",
        "in",
        "gt_median",
        "gte_median",
        "lt_median",
        "lte_median",
    ] = Field(description="Comparison. Median ops ignore value and use the column's median.")
    value: Optional[Any] = Field(
        default=None,
        description="Number, text, boolean, or a list when op is in. Omit for median ops.",
    )


class FilterRowsInput(BaseModel):
    filters: list[RowFilter] = Field(
        min_length=1,
        max_length=8,
        description="Every condition is applied together to the original lookup rows.",
    )


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    return keys


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


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join("" if item is None else str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _same(left: Any, right: Any) -> bool:
    left_num = _numeric(left)
    right_num = _numeric(right)
    if left_num is not None and right_num is not None:
        return left_num == right_num
    return _text(left).casefold() == _text(right).casefold()


def _ordered(left: Any, right: Any) -> tuple[Any, Any] | None:
    left_num = _numeric(left)
    right_num = _numeric(right)
    if left_num is not None and right_num is not None:
        return left_num, right_num
    if left is None or right is None:
        return None
    return _text(left), _text(right)


def _matches(cell: Any, op: str, value: Any, median: float | None) -> bool:
    if op == "eq":
        return _same(cell, value)
    if op == "ne":
        return not _same(cell, value)
    if op == "contains":
        return _text(value).casefold() in _text(cell).casefold()
    if op == "in":
        choices = value if isinstance(value, list) else [value]
        return any(_same(cell, choice) for choice in choices)
    if op in _MEDIAN_OPS:
        number = _numeric(cell)
        if number is None or median is None:
            return False
        if op == "gt_median":
            return number > median
        if op == "gte_median":
            return number >= median
        if op == "lt_median":
            return number < median
        return number <= median
    ordered = _ordered(cell, value)
    if ordered is None:
        return False
    left, right = ordered
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    return left <= right


def _median(rows: list[dict[str, Any]], column: str) -> float | None:
    numbers = [number for row in rows if (number := _numeric(row.get(column))) is not None]
    if not numbers:
        return None
    return float(statistics.median(numbers))


@tool(args_schema=FilterRowsInput)
def filter_rows(filters: list[RowFilter]) -> str:
    """Keep rows from the original lookup that match every condition.

    Do not pass the rows. Call this after a retrieval tool when the manager
    wants a subset, including a threshold chosen in clarification. A later
    call still starts from the original lookup, so pass every condition.
    Then summarize_rows, draw, or render_table uses the kept rows.
    This tool does not display a chart or a table.
    """
    tool_name = "filter_rows"
    rows, source = initial_rows()
    if not rows:
        return tool_error(
            tool_name,
            "NO_ROWS",
            "No lookup rows are available. Call a retrieval tool before filtering.",
        )
    present = _columns(rows)
    prepared: list[tuple[str, str, Any, float | None]] = []
    for item in filters:
        spec = item if isinstance(item, RowFilter) else RowFilter.model_validate(item)
        column = spec.column.strip()
        if any(column not in row for row in rows):
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"'{column}' is not a column on the original {source or 'lookup'} rows.",
                columns=present,
            )
        if spec.op == "in" and not isinstance(spec.value, list):
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                "op in requires value to be a list.",
                columns=present,
            )
        if spec.op not in _MEDIAN_OPS and spec.op != "in" and spec.value is None:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"op {spec.op} requires value.",
                columns=present,
            )
        median = _median(rows, column) if spec.op in _MEDIAN_OPS else None
        if spec.op in _MEDIAN_OPS and median is None:
            return tool_error(
                tool_name,
                "INVALID_INPUT",
                f"'{column}' has no numeric values to take a median from.",
                columns=present,
            )
        prepared.append((column, spec.op, spec.value, median))

    kept = [
        row
        for row in rows
        if all(_matches(row.get(column), op, value, median) for column, op, value, median in prepared)
    ]
    set_working_rows(kept)
    applied = [
        {"column": column, "op": op, "value": value, "median": median}
        for column, op, value, median in prepared
    ]
    logger.info(
        "filter_rows source=%s filters=%s kept=%s of %s",
        source,
        len(applied),
        len(kept),
        len(rows),
    )
    data: dict[str, Any] = {
        "source_tool": source,
        "source_count": len(rows),
        "matched_count": len(kept),
        "filters": applied,
        "rows": kept,
    }
    if not kept:
        data["count"] = 0
    return tool_json(
        {
            "ok": True,
            "tool": tool_name,
            "data": data,
            "trace": {
                "tool": tool_name,
                "source_file": source or "previous lookup",
                "filter": {"filters": applied},
                "rows": kept,
                "calculations": [{"name": "filter", "result": len(kept)}],
                "basis": (
                    "Filtered the original lookup rows in Python. "
                    "The model did not supply the rows or drop them itself."
                ),
            },
        }
    )
