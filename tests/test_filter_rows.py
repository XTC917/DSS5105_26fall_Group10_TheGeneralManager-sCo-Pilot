"""Filter the original lookup rows without the model supplying those rows."""

from __future__ import annotations

from backend.tools.filter_rows import filter_rows
from backend.tools.lookup_rows import bind_lookup_rows, lookup_rows, note_lookup_payload, reset_lookup_rows
from backend.tools.summarize_rows import summarize_rows
from tests.conftest import parse_tool


def _orders():
    return {
        "ok": True,
        "tool": "find_orders",
        "data": {
            "orders": [
                {"order_id": "ORD-1", "status": "IN_PROGRESS", "pieces": 10},
                {"order_id": "ORD-2", "status": "IN_PROGRESS", "pieces": 5},
                {"order_id": "ORD-3", "status": "COMPLETE", "pieces": 7},
            ]
        },
    }


def test_filter_keeps_rows_at_or_above_a_threshold():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            filter_rows.invoke({"filters": [{"column": "pieces", "op": "gte", "value": 8}]})
        )
        working, _source = lookup_rows()
    finally:
        reset_lookup_rows(tokens)
    assert [row["order_id"] for row in payload["data"]["rows"]] == ["ORD-1"]
    assert payload["data"]["source_count"] == 3
    assert [row["order_id"] for row in working] == ["ORD-1"]


def test_second_filter_starts_from_the_original_lookup():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        filter_rows.invoke({"filters": [{"column": "pieces", "op": "gte", "value": 8}]})
        payload = parse_tool(
            filter_rows.invoke({"filters": [{"column": "status", "op": "eq", "value": "COMPLETE"}]})
        )
    finally:
        reset_lookup_rows(tokens)
    assert [row["order_id"] for row in payload["data"]["rows"]] == ["ORD-3"]


def test_median_filter_is_computed_in_python():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            filter_rows.invoke({"filters": [{"column": "pieces", "op": "gte_median"}]})
        )
    finally:
        reset_lookup_rows(tokens)
    assert [row["order_id"] for row in payload["data"]["rows"]] == ["ORD-1", "ORD-3"]
    assert payload["data"]["filters"][0]["median"] == 7


def test_unknown_filter_column_lists_real_columns():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            filter_rows.invoke({"filters": [{"column": "revenue", "op": "gt", "value": 1}]})
        )
    finally:
        reset_lookup_rows(tokens)
    assert payload["ok"] is False
    assert "pieces" in payload["error"]["columns"]


def test_empty_filter_leaves_summarize_with_no_rows():
    tokens = bind_lookup_rows()
    try:
        note_lookup_payload(_orders())
        payload = parse_tool(
            filter_rows.invoke({"filters": [{"column": "pieces", "op": "gt", "value": 100}]})
        )
        summary = parse_tool(summarize_rows.invoke({"group_by": "status", "metric": "count"}))
    finally:
        reset_lookup_rows(tokens)
    assert payload["data"]["matched_count"] == 0
    assert payload["data"]["count"] == 0
    assert summary["data"]["rows"] == []
