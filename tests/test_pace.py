"""Pace estimates and snapshot timeline. No LLM."""

from backend.services.discovery import discover_factory_issues as run_discover
from backend.services.pace import (
    likely_to_miss_due_dates,
    likely_to_miss_due_next_n_days,
    today_priority,
)
from backend.tools.retrieval import get_orders_at_risk
from backend.tools.tracing import trace_order
from tests.conftest import parse_tool


def test_likely_to_miss_due_matches_q001(db):
    ids = [r["order_id"] for r in likely_to_miss_due_dates(db)]
    assert ids == ["ORD-029", "ORD-108", "ORD-103"]


def test_likely_to_miss_next_7_days_matches_q002(db):
    ids = [r["order_id"] for r in likely_to_miss_due_next_n_days(db)]
    assert ids == ["ORD-108", "ORD-103", "ORD-062"]
    by_id = {r["order_id"]: r for r in likely_to_miss_due_next_n_days(db)}
    assert by_id["ORD-108"]["estimated_remaining_working_days"] == 8.4
    assert by_id["ORD-103"]["estimated_remaining_working_days"] == 8.4


def test_get_orders_at_risk_exposes_pace_groups(db):
    payload = parse_tool(get_orders_at_risk.invoke({}))
    assert payload["data"]["likely_to_miss_due_dates"]["order_ids"] == [
        "ORD-029",
        "ORD-108",
        "ORD-103",
    ]
    assert payload["data"]["likely_to_miss_due_next_7_days"]["order_ids"] == [
        "ORD-108",
        "ORD-103",
        "ORD-062",
    ]


def test_today_priority_matches_q005(db):
    buckets = today_priority(db)
    assert [r["order_id"] for r in buckets["1st_priority"]] == [
        "ORD-107",
        "ORD-114",
        "ORD-093",
    ]
    assert [r["order_id"] for r in buckets["2nd_priority"]] == [
        "ORD-029",
        "ORD-120",
        "ORD-083",
        "ORD-002",
    ]
    assert [r["order_id"] for r in buckets["3rd_priority"]] == ["ORD-108", "ORD-103"]


def test_discover_includes_priority_and_production(db):
    data = run_discover(db, limit=5)
    assert data["today_priority"]["1st_priority"][0]["order_id"] == "ORD-107"
    prod = data["production"]
    assert prod["in_progress_order_count"] == 34
    assert prod["in_progress_by_stage"] == {
        "KNITTING": 12,
        "ASSEMBLY": 10,
        "WASHING": 10,
        "PACKING": 2,
    }
    flagged = prod["flagged_stages"]
    assert len(flagged) == 1
    assert flagged[0]["stage"] == "ASSEMBLY"
    assert flagged[0]["last_day_pieces"] == 455
    assert flagged[0]["lookback_median"] == 758.0


def test_trace_order_uses_snapshot(db):
    payload = parse_tool(trace_order.invoke({"order_id": "ORD-120"}))
    snap = payload["data"]["snapshot"]
    assert snap["order_date"] == "2026-02-27"
    assert snap["first_production_stage_date"] == "2026-03-27"
    assert snap["calendar_days_order_to_first_production"] == 28
    assert payload["data"]["pace"]["estimated_remaining_working_days"] == 6.3
    assert payload["data"]["consider_external_workshop"] is True
    assert payload["data"]["computed"]["calendar_days_until_due"] == -15


def test_trace_order_107_start_delay(db):
    payload = parse_tool(trace_order.invoke({"order_id": "ORD-107"}))
    snap = payload["data"]["snapshot"]
    assert snap["order_date"] == "2026-03-01"
    assert snap["calendar_days_order_to_first_production"] == 22
    assert payload["data"]["order"]["current_stage"] == "PACKING"
    assert payload["data"]["pace"]["estimated_remaining_working_days"] == 3.0
