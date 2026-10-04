"""Structured table tool validation and output shape."""

from __future__ import annotations

import json

from backend.tools.render_table import render_table


def test_render_table_returns_selected_columns_and_rows():
    result = json.loads(
        render_table.invoke(
            {
                "title": "At-risk orders",
                "columns": [
                    {"key": "order_id", "label": "Order"},
                    {"key": "status", "label": "Status"},
                ],
                "rows": [
                    {"order_id": "ORD-120", "status": "IN_PROGRESS", "unused": "not shown"},
                ],
            }
        )
    )

    assert result["ok"] is True
    assert result["tool"] == "render_table"
    assert result["data"]["table"]["columns"][0]["label"] == "Order"
    assert result["data"]["table"]["rows"] == [
        {"order_id": "ORD-120", "status": "IN_PROGRESS"}
    ]


def test_render_table_rejects_missing_column_values():
    result = json.loads(
        render_table.invoke(
            {
                "title": "At-risk orders",
                "columns": [{"key": "order_id", "label": "Order"}],
                "rows": [{"status": "IN_PROGRESS"}],
            }
        )
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_DATA"