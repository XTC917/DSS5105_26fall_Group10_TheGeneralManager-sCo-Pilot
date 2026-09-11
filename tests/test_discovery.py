"""find_orders and ranked discover_factory_issues. No LLM required."""

from __future__ import annotations

from backend.services.audit import list_audit
from backend.services.discovery import (
    ISSUE_ORDER_OVERDUE,
    ISSUE_ORDER_STALLED,
    ISSUE_ORDER_TIGHT_DUE,
    ISSUE_STAGE_BELOW_BASELINE,
    collect_stage_issues,
    discover_factory_issues as run_discover,
    sort_issues,
)
from backend.services.watches import list_watches
from backend.tools.discovery import discover_factory_issues, find_orders
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from tests.conftest import parse_tool


def test_find_orders_by_customer_lists_all_matches(db):
    payload = parse_tool(find_orders.invoke({"customer": "TrendCart"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 17
    ids = payload["data"]["order_ids"]
    assert "ORD-120" in ids
    assert len(ids) == 17


def test_find_orders_does_not_pick_one_trendcart_order(db):
    listed = parse_tool(find_orders.invoke({"customer": "TrendCart"}))
    status = parse_tool(get_order_status.invoke({"customer": "TrendCart"}))
    assert listed["data"]["count"] > 1
    assert status["ok"] is False
    assert status["error"]["code"] == "AMBIGUOUS"


def test_find_orders_by_stage(db):
    payload = parse_tool(find_orders.invoke({"current_stage": "ASSEMBLY"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 10
    assert all(row["current_stage"] == "ASSEMBLY" for row in payload["data"]["orders"])


def test_find_orders_by_status(db):
    payload = parse_tool(find_orders.invoke({"status": "IN_PROGRESS"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 34
    assert all(row["status"] == "IN_PROGRESS" for row in payload["data"]["orders"])


def test_find_orders_product_plural_maps_to_hoodie(db):
    payload = parse_tool(find_orders.invoke({"product": "hoodies"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 26
    assert payload["data"]["filter"]["matched_product"] == "Hoodie"
    assert all(row["product"] == "Hoodie" for row in payload["data"]["orders"])


def test_find_orders_empty_result(db):
    payload = parse_tool(find_orders.invoke({"customer": "NoSuchBuyer"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 0
    assert payload["data"]["orders"] == []


def test_find_orders_unknown_product_is_empty(db):
    payload = parse_tool(find_orders.invoke({"product": "Spaceship"}))
    assert payload["ok"] is True
    assert payload["data"]["count"] == 0


def test_find_orders_invalid_status(db):
    payload = parse_tool(find_orders.invoke({"status": "SHIPPED"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_find_orders_invalid_stage(db):
    payload = parse_tool(find_orders.invoke({"current_stage": "SHIPPING"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_find_orders_requires_a_filter(db):
    payload = parse_tool(find_orders.invoke({}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_find_orders_customer_and_product(db):
    payload = parse_tool(
        find_orders.invoke({"customer": "TrendCart", "product": "Vest"})
    )
    assert payload["ok"] is True
    assert payload["data"]["count"] >= 1
    assert all(
        row["customer"] == "TrendCart" and row["product"] == "Vest"
        for row in payload["data"]["orders"]
    )


def _tool_data(limit=5):
    return parse_tool(discover_factory_issues.invoke({"limit": limit}))


def test_discover_finds_order_risk(db):
    payload = _tool_data()
    assert payload["ok"] is True
    data = payload["data"]
    assert data["factory_today"] == "2026-04-01"
    assert data["total_found"] == 11
    types = {item["issue_type"] for item in data["issues"]}
    assert ISSUE_ORDER_OVERDUE in types
    risk = parse_tool(get_orders_at_risk.invoke({}))
    risk_ids = {row["order_id"] for row in risk["data"]["orders"]}
    discovered_orders = {
        item["order_id"]
        for item in run_discover(db, limit=20)["issues"]
        if item.get("order_id")
    }
    assert discovered_orders == risk_ids


def test_discover_includes_overdue_order(db):
    issues = run_discover(db, limit=20)["issues"]
    overdue = [i for i in issues if i["issue_type"] == ISSUE_ORDER_OVERDUE]
    assert any(i["order_id"] == "ORD-120" for i in overdue)
    ord120 = next(i for i in overdue if i["order_id"] == "ORD-120")
    assert ord120["priority"] == 1
    assert "OVERDUE" in ord120["evidence"]["flags"]


def test_discover_includes_stalled_order(db):
    issues = run_discover(db, limit=20)["issues"]
    stalled = next(i for i in issues if i["order_id"] == "ORD-005")
    assert stalled["issue_type"] == ISSUE_ORDER_STALLED
    assert stalled["priority"] == 2
    assert stalled["evidence"]["flags"] == ["STALLED"]


def test_discover_includes_stage_below_baseline(db):
    issues = run_discover(db, limit=20)["issues"]
    stages = [i for i in issues if i["issue_type"] == ISSUE_STAGE_BELOW_BASELINE]
    assert len(stages) == 1
    assembly = stages[0]
    assert assembly["stage"] == "ASSEMBLY"
    assert assembly["priority"] == 3
    assert assembly["source_file"] == "production_log.csv"
    assert assembly["threshold"] == 0.70
    assert assembly["latest_output"] == 455
    assert assembly["median_30d"] == 758.0
    assert assembly["ratio"] == 0.6
    assert assembly["result"] is True


def test_discover_priority_sort_is_deterministic(db):
    first = run_discover(db, limit=20)["issues"]
    second = run_discover(db, limit=20)["issues"]
    ids = [i["issue_id"] for i in first]
    assert ids == [i["issue_id"] for i in second]
    assert ids == [
        "order:ORD-107",
        "order:ORD-120",
        "order:ORD-083",
        "order:ORD-114",
        "order:ORD-002",
        "order:ORD-093",
        "order:ORD-020",
        "order:ORD-055",
        "order:ORD-029",
        "order:ORD-005",
        "stage:ASSEMBLY",
    ]
    priorities = [i["priority"] for i in first]
    assert priorities == sorted(priorities)
    assert first[0]["issue_type"] == ISSUE_ORDER_OVERDUE
    assert first[-2]["issue_type"] == ISSUE_ORDER_STALLED
    assert first[-1]["issue_type"] == ISSUE_STAGE_BELOW_BASELINE
    shuffled = list(reversed(first))
    resorted = sort_issues(shuffled)
    assert [i["issue_id"] for i in resorted] == ids


def test_discover_limit_five(db):
    payload = _tool_data(5)
    data = payload["data"]
    assert data["returned_count"] == 5
    assert len(data["issues"]) == 5
    assert data["total_found"] == 11
    assert data["limit"] == 5


def test_discover_one_issue_per_order_with_combined_flags(db):
    issues = run_discover(db, limit=20)["issues"]
    order_ids = [i.get("order_id") for i in issues if i.get("order_id")]
    assert len(order_ids) == len(set(order_ids))
    combined = next(i for i in issues if i["order_id"] == "ORD-002")
    assert combined["issue_type"] == ISSUE_ORDER_OVERDUE
    assert set(combined["evidence"]["flags"]) == {"OVERDUE", "STALLED"}
    tight = next(i for i in issues if i["order_id"] == "ORD-029")
    assert tight["issue_type"] == ISSUE_ORDER_TIGHT_DUE


def test_discover_issue_has_traceability(db):
    payload = _tool_data(5)
    item = payload["data"]["issues"][0]
    for key in (
        "issue_id",
        "issue_type",
        "priority",
        "severity",
        "title",
        "summary",
        "evidence",
        "source_file",
        "rule",
        "inputs",
        "result",
    ):
        assert key in item
    assert item["source_file"] == "orders.csv"
    assert item["result"] is True
    assert item["inputs"]["factory_today"] == "2026-04-01"
    assert payload["trace"]["source_file"] == "orders.csv, production_log.csv"


def test_discover_empty_list_when_no_rules_fire(db, monkeypatch):
    monkeypatch.setattr(
        "backend.services.discovery.collect_order_risk_issues",
        lambda _db: [],
    )
    monkeypatch.setattr(
        "backend.services.discovery.collect_stage_issues",
        lambda _db: [],
    )
    result = run_discover(db, limit=5)
    assert result["issues"] == []
    assert result["total_found"] == 0
    assert result["returned_count"] == 0
    assert result["message"]
    assert result["counts_by_type"][ISSUE_ORDER_OVERDUE] == 0


def test_discover_does_not_write_state(db, clean_state):
    before_audit = list_audit(50)
    before_watches = list_watches()
    payload = _tool_data(5)
    assert payload["ok"] is True
    assert list_audit(50) == before_audit
    assert list_watches() == before_watches


def test_discover_invalid_limit(db):
    bad = parse_tool(discover_factory_issues.invoke({"limit": 0}))
    assert bad["ok"] is False
    assert bad["error"]["code"] == "INVALID_INPUT"
    also = parse_tool(discover_factory_issues.invoke({"limit": 99}))
    assert also["ok"] is False


def test_collect_stage_issues_uses_briefing_flag(db, monkeypatch):
    fake = [
        {
            "stage": "PACKING",
            "last_working_date": "2026-03-31",
            "last_day_pieces": 10,
            "lookback_median": 100,
            "ratio_to_median": 0.1,
            "flagged": True,
            "rule": "flag if last working day pieces < 0.70 × lookback median",
        }
    ]
    monkeypatch.setattr("backend.services.discovery.unusual_stage_output", lambda _db: fake)
    issues = collect_stage_issues(db)
    assert len(issues) == 1
    assert issues[0]["issue_type"] == ISSUE_STAGE_BELOW_BASELINE
    assert issues[0]["stage"] == "PACKING"