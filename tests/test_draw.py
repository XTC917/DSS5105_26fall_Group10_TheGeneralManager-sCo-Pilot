"""Chart tool validation and output shape."""

from __future__ import annotations

import json

import pytest

from backend.tools.draw import draw


@pytest.mark.parametrize("chart_type", ["bar", "pie", "line", "area", "combo"])
def test_draw_returns_chart_spec(chart_type):
    chart_args = {
        "chart_type": chart_type,
        "title": "Orders by stage",
        "data": [{"stage": "KNITTING", "count": 3}],
        "category_key": "stage",
        "value_keys": ["count"],
    }
    if chart_type == "combo":
        chart_args["series_types"] = {"count": "line"}
    result = json.loads(
        draw.invoke(chart_args)
    )

    assert result["ok"] is True
    assert result["tool"] == "draw"
    assert result["data"]["chart"]["type"] == chart_type
    assert result["data"]["chart"]["data"][0]["count"] == 3


def test_draw_rejects_non_finite_values():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "bar",
                "title": "Orders by stage",
                "data": [{"stage": "KNITTING", "count": float("nan")}],
                "category_key": "stage",
                "value_keys": ["count"],
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_DATA"


def test_draw_supports_stacked_bars():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "bar",
                "title": "Orders by risk flag",
                "data": [{"stage": "KNITTING", "overdue": 2, "stalled": 1}],
                "category_key": "stage",
                "value_keys": ["overdue", "stalled"],
                "stacked": True,
            }
        )
    )

    assert result["ok"] is True
    assert result["data"]["chart"]["stacked"] is True


def test_draw_rejects_stacked_non_bar_chart():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "line",
                "title": "Orders by risk flag",
                "data": [{"stage": "KNITTING", "count": 2}],
                "category_key": "stage",
                "value_keys": ["count"],
                "stacked": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_CHART"


def test_draw_supports_percentage_stacked_bars():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "bar",
                "title": "Production mix by stage",
                "data": [{"date": "2026-04-01", "knitting": 60, "assembly": 40}],
                "category_key": "date",
                "value_keys": ["knitting", "assembly"],
                "stacked": True,
                "percentage": True,
            }
        )
    )

    chart = result["data"]["chart"]
    assert result["ok"] is True
    assert chart["stacked"] is True
    assert chart["percentage"] is True


def test_draw_supports_bar_line_combo():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "combo",
                "title": "Output and median",
                "data": [{"stage": "KNITTING", "output": 12, "median": 10}],
                "category_key": "stage",
                "value_keys": ["output", "median"],
                "series_types": {"output": "bar", "median": "line"},
            }
        )
    )

    assert result["ok"] is True
    assert result["data"]["chart"]["series_types"] == {"output": "bar", "median": "line"}


def test_draw_rejects_percentage_mode_without_stacked_bar():
    result = json.loads(
        draw.invoke(
            {
                "chart_type": "bar",
                "title": "Production mix",
                "data": [{"stage": "KNITTING", "count": 2}],
                "category_key": "stage",
                "value_keys": ["count"],
                "percentage": True,
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_CHART"