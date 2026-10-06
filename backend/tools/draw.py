"""Chart specification tool for visualising grounded factory data."""

from __future__ import annotations

import math
from contextvars import ContextVar, Token
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.tools.common import tool_error, tool_json

_FRONTEND_CHARTS: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "frontend_charts", default=None
)
_FRONTEND_CHART_MESSAGE = "The chart has already been generated in the frontend."


def bind_frontend_charts() -> Token[list[dict[str, Any]] | None]:
    return _FRONTEND_CHARTS.set([])


def take_frontend_charts(token: Token[list[dict[str, Any]] | None]) -> list[dict[str, Any]]:
    charts = list(_FRONTEND_CHARTS.get() or [])
    _FRONTEND_CHARTS.reset(token)
    return charts


class DrawInput(BaseModel):
    chart_type: Literal["bar", "pie", "line", "area", "combo"] = Field(
        description="Chart type: bar, pie, line, area, or combo (bar and line series together).",
    )
    stacked: bool = Field(
        default=False,
        description="Set true only for a stacked bar chart; otherwise leave false.",
    )
    percentage: bool = Field(
        default=False,
        description="Set true with stacked=true for a 100% stacked bar chart.",
    )
    title: str = Field(min_length=1, max_length=100)
    data: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=40,
        description="Rows of tool-grounded values, each including category and numeric series.",
    )
    category_key: str = Field(min_length=1, max_length=40)
    value_keys: list[str] = Field(min_length=1, max_length=5)
    series_types: dict[str, Literal["bar", "line"]] = Field(
        default_factory=dict,
        description="For combo charts, map every value key to either bar or line.",
    )


@tool(args_schema=DrawInput)
def draw(
    chart_type: Literal["bar", "pie", "line", "area", "combo"],
    title: str,
    data: list[dict[str, Any]],
    category_key: str,
    value_keys: list[str],
    stacked: bool = False,
    percentage: bool = False,
    series_types: dict[str, Literal["bar", "line"]] | None = None,
) -> str:
    """Create a chart from values returned by factory data tools.

    Calling this tool displays the chart. Do not draw it again in the reply,
    and do not write an image, a data URL, or plotting code.
    Use after retrieving the values from another tool. Never invent or calculate
    chart values. Use pie for a composition, bar for category comparisons, line
    or area for a time series, and combo for bars and lines together. Set
    stacked=true for stacked bars and percentage=true for 100% stacked bars.
    Combo charts must set series_types for each value key to bar or line. Provide
    rows with category_key and value_keys.
    """
    tool_name = "draw"
    if stacked and chart_type != "bar":
        return tool_error(tool_name, "INVALID_CHART", "Only bar charts can be stacked.")
    if percentage and (chart_type != "bar" or not stacked):
        return tool_error(tool_name, "INVALID_CHART", "Percentage mode requires a stacked bar chart.")
    series_types = series_types or {}
    if chart_type == "combo" and set(series_types) != set(value_keys):
        return tool_error(tool_name, "INVALID_CHART", "Combo charts require a bar or line type for every value key.")
    if chart_type != "combo" and series_types:
        return tool_error(tool_name, "INVALID_CHART", "Series types are only valid for combo charts.")
    if chart_type == "pie" and len(value_keys) != 1:
        return tool_error(tool_name, "INVALID_CHART", "Pie charts require exactly one value key.")

    required_keys = {category_key, *value_keys}
    for row in data:
        if not required_keys.issubset(row):
            return tool_error(tool_name, "INVALID_DATA", "Every row must include the category and value keys.")
        if not isinstance(row[category_key], (str, int, float)):
            return tool_error(tool_name, "INVALID_DATA", "Category values must be text or numbers.")
        for key in value_keys:
            value = row[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return tool_error(tool_name, "INVALID_DATA", f"Chart value '{key}' must be a finite number.")
            if percentage and value < 0:
                return tool_error(tool_name, "INVALID_DATA", "Percentage stacked bar values must be non-negative.")
        if percentage and sum(row[key] for key in value_keys) <= 0:
            return tool_error(tool_name, "INVALID_DATA", "Each percentage stacked bar category must have a positive total.")

    chart = {
        "type": chart_type,
        "title": title.strip(),
        "data": data,
        "category_key": category_key,
        "value_keys": value_keys,
        "stacked": stacked,
        "percentage": percentage,
        "series_types": series_types,
    }
    bucket = _FRONTEND_CHARTS.get()
    if bucket is not None:
        bucket.append(chart)
    return tool_json(
        {"ok": True, "tool": tool_name, "data": {"message": _FRONTEND_CHART_MESSAGE}}
    )