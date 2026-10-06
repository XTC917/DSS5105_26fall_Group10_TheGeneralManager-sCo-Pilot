"""Structured table tool validation and output shape."""

from __future__ import annotations

import json

from backend.tools.render_table import bind_frontend_tables, render_table, take_frontend_tables


def test_render_table_returns_selected_columns_and_rows():
    token = bind_frontend_tables()
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
    tables = take_frontend_tables(token)

    assert result["ok"] is True
    assert result["tool"] == "render_table"
    assert result["data"]["message"] == "The table has already been generated in the frontend."
    assert "table" not in result["data"]
    assert tables[0]["columns"][0]["label"] == "Order"
    assert tables[0]["rows"] == [{"order_id": "ORD-120", "status": "IN_PROGRESS"}]


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