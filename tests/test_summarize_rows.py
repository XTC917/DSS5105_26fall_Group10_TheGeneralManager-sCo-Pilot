"""REVERT-SUMMARIZE: delete this file with the grouped-count tool."""

from __future__ import annotations

from backend.tools.lookup_rows import bind_lookup_rows, note_lookup_payload, reset_lookup_rows
from backend.tools.summarize_rows import summarize_rows
from tests.conftest import parse_tool


def _orders():
    return {
        "ok": True,
        "tool": "find_orders",
        "data": {
            "orders": [
                {"order_id": "ORD-1", "current_stage": "KNITTING", "pieces": 10},
                {"order_id": "ORD-2", "current_stage": "KNITTING", "pieces": 5},
                {"order_id": "ORD-3", "current_stage": "COMPLETE", "pieces": 7},
            ]
        },
    }


def test_count_groups_latest_lookup_rows():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            summarize_rows.invoke({"group_by": "current_stage", "metric": "count"})
        )
    finally:
        reset_lookup_rows(tokens)
    assert payload["ok"] is True
    assert payload["data"]["rows"] == [
        {"current_stage": "COMPLETE", "order_count": 1},
        {"current_stage": "KNITTING", "order_count": 2},
    ]
    assert payload["data"]["source_count"] == 3


def test_unknown_column_lists_real_columns():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            summarize_rows.invoke({"group_by": "current_status", "metric": "count"})
        )
    finally:
        reset_lookup_rows(tokens)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"
    assert "current_stage" in payload["error"]["columns"]
    assert "current_status" not in payload["error"]["columns"]


def test_sum_uses_numeric_column():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            summarize_rows.invoke(
                {"group_by": "current_stage", "metric": "sum", "value_column": "pieces"}
            )
        )
    finally:
        reset_lookup_rows(tokens)
    assert payload["data"]["rows"] == [
        {"current_stage": "COMPLETE", "pieces_sum": 7},
        {"current_stage": "KNITTING", "pieces_sum": 15},
    ]


def test_without_a_lookup_has_no_rows():
    payload = parse_tool(summarize_rows.invoke({"group_by": "status"}))
    assert payload["error"]["code"] == "NO_ROWS"
