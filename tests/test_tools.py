"""MVP tools: retrieval, risk, trace, feasibility. No LLM required."""

from __future__ import annotations

from backend.tools.judgement import check_feasibility
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from backend.tools.tracing import trace_order
from tests.conftest import parse_tool


def test_get_order_status_by_id(db):
    payload = parse_tool(get_order_status.invoke({"order_id": "ORD-120"}))
    assert payload["ok"] is True
    order = payload["data"]["order"]
    assert order["customer"] == "TrendCart"
    assert order["product"] == "Vest"
    assert order["status"] == "IN_PROGRESS"
    assert order["current_stage"] == "ASSEMBLY"
    assert payload["data"]["computed"]["is_overdue"] is True
    assert payload["trace"]["source_file"] == "orders.csv"


def test_get_order_status_ambiguous_customer(db):
    payload = parse_tool(get_order_status.invoke({"customer": "TrendCart"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "AMBIGUOUS"
    assert len(payload["error"]["candidates"]) > 1


def test_get_order_status_not_found(db):
    payload = parse_tool(get_order_status.invoke({"order_id": "ORD-999"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_get_order_status_requires_filter(db):
    payload = parse_tool(get_order_status.invoke({}))
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_get_orders_at_risk_includes_known_overdue(db):
    payload = parse_tool(get_orders_at_risk.invoke({}))
    assert payload["ok"] is True
    ids = {row["order_id"] for row in payload["data"]["orders"]}
    assert "ORD-120" in ids  # due 2026-03-17, still IN_PROGRESS
    assert payload["data"]["count"] == len(payload["data"]["orders"])
    for row in payload["data"]["orders"]:
        assert row["flags"]
        assert set(row["flags"]) <= {"OVERDUE", "STALLED", "TIGHT_DEADLINE"}


def test_get_orders_at_risk_flag_filter(db):
    payload = parse_tool(get_orders_at_risk.invoke({"flag": "OVERDUE"}))
    assert payload["ok"] is True
    assert payload["data"]["orders"]
    assert all("OVERDUE" in row["flags"] for row in payload["data"]["orders"])


def test_trace_order(db):
    payload = parse_tool(trace_order.invoke({"order_id": "ORD-120"}))
    assert payload["ok"] is True
    assert payload["trace"]["rows"][0]["order_id"] == "ORD-120"
    assert "OVERDUE" in payload["data"]["risk"]["flags"]
    assert payload["data"]["limitations"]


def test_check_feasibility_hoodie_august(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 800, "due_date": "2026-08-25", "product": "Hoodie"}
        )
    )
    assert payload["ok"] is True
    assert payload["data"]["category"] == "TOPS"
    assert payload["data"]["working_days"] > 100
    assert payload["data"]["verdict"] in {
        "FEASIBLE_IN_HOUSE",
        "FEASIBLE_WITH_WORKSHOPS",
        "NOT_FEASIBLE",
    }
    # Long window should not be past-due.
    assert payload["data"]["verdict"] != "NOT_FEASIBLE" or payload["data"]["spare_factory_capacity"] >= 0
    assert payload["data"]["limitations"]
    assert "bottleneck_median" in payload["data"]["throughput"]


def test_check_feasibility_past_due(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 800, "due_date": "2026-03-01", "category": "TOPS"}
        )
    )
    assert payload["ok"] is True
    assert payload["data"]["verdict"] == "NOT_FEASIBLE"
    assert payload["data"]["feasible_in_house"] is False


def test_check_feasibility_unknown_product(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 10, "due_date": "2026-08-25", "product": "Spaceship"}
        )
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNKNOWN_PRODUCT"
