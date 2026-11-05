"""MVP tools: retrieval, risk, trace, feasibility. No LLM required."""

from __future__ import annotations

from backend.tools.common import reset_manager_text, set_manager_text
from datetime import date, timedelta

from backend.tools.judgement import check_feasibility, earliest_delivery_date
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from backend.tools.tracing import compare_order_progress, trace_order
from tests.conftest import parse_tool


def test_get_order_status_by_id(db):
    payload = parse_tool(get_order_status.invoke({"order_id": "ORD-120"}))
    assert payload["ok"] is True
    order = payload["data"]["order"]
    assert order["customer"] == "TrendCart"
    assert order["product"] == "Vest"
    assert order["pieces"] == 1500
    assert order["status"] == "IN_PROGRESS"
    assert order["current_stage"] == "ASSEMBLY"
    assert order["due_date"] == "2026-03-17"
    assert order["last_activity_date"] == "2026-03-30"
    assert payload["data"]["computed"]["is_overdue"] is True
    assert payload["data"]["computed"]["is_stalled"] is False
    assert payload["trace"]["source_file"] == "orders.csv"


def test_order_id_not_in_the_question_is_refused(db):
    token = set_manager_text("How is the TrendCart order doing?")
    try:
        payload = parse_tool(get_order_status.invoke({"order_id": "ORD-120"}))
    finally:
        reset_manager_text(token)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNGROUNDED_ID"
    assert "data" not in payload


def test_unnamed_product_filter_is_refused(db):
    token = set_manager_text("How is the TrendCart order doing?")
    try:
        payload = parse_tool(
            get_order_status.invoke({"customer": "TrendCart", "product": "Vest"})
        )
    finally:
        reset_manager_text(token)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNGROUNDED_ID"


def test_get_order_status_ambiguous_customer(db):
    payload = parse_tool(get_order_status.invoke({"customer": "TrendCart"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "AMBIGUOUS"
    assert len(payload["error"]["candidates"]) > 1


def test_get_order_status_not_found(db):
    payload = parse_tool(get_order_status.invoke({"order_id": "ORD-999"}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"


def test_get_order_status_product_case_insensitive(db):
    payload = parse_tool(get_order_status.invoke({"order_id": "ORD-120", "product": "vest"}))
    assert payload["ok"] is True
    assert payload["data"]["order"]["product"] == "Vest"


def test_get_order_status_requires_filter(db):
    payload = parse_tool(get_order_status.invoke({}))
    assert payload["error"]["code"] == "INVALID_INPUT"


def test_get_order_status_uses_pace_tight_flag(db):
    tight = parse_tool(get_order_status.invoke({"order_id": "ORD-108"}))
    assert tight["ok"] is True
    assert tight["data"]["computed"]["is_overdue"] is False
    assert tight["data"]["computed"]["is_tight_deadline"] is True
    assert tight["data"]["flags"] == ["TIGHT_DEADLINE"]
    far = parse_tool(get_order_status.invoke({"order_id": "ORD-063"}))
    assert far["data"]["computed"]["is_tight_deadline"] is False
    assert "TIGHT_DEADLINE" not in far["data"]["flags"]


def test_get_orders_at_risk_default_is_pace_miss(db):
    payload = parse_tool(get_orders_at_risk.invoke({}))
    assert payload["ok"] is True
    ids = [row["order_id"] for row in payload["data"]["orders"]]
    assert ids == ["ORD-029", "ORD-108", "ORD-103"]
    assert payload["data"]["count"] == 3
    assert payload["data"]["likely_to_miss_due_dates"]["order_ids"] == ids
    by_id = {row["order_id"]: row["flags"] for row in payload["data"]["orders"]}
    assert by_id["ORD-029"] == ["TIGHT_DEADLINE"]
    assert "OVERDUE" not in by_id["ORD-029"]
    assert "STALLED" not in by_id["ORD-029"]


def test_get_orders_at_risk_fixed_stage_rate(db):
    baseline = parse_tool(get_orders_at_risk.invoke({}))
    assumed = parse_tool(
        get_orders_at_risk.invoke({"stage": "Assembly", "pieces_per_day": 455})
    )
    assert assumed["ok"] is True
    data = assumed["data"]
    assert data["assumption"] == {
        "stage": "ASSEMBLY",
        "pieces_per_day": 455.0,
        "replaces": "30-day median for this stage only",
    }
    assert data["stage_rates_pieces_per_day"]["ASSEMBLY"] == 455.0
    assert data["stage_rates_pieces_per_day"]["KNITTING"] == baseline["data"]["stage_rates_pieces_per_day"]["KNITTING"]
    by_id = {row["order_id"]: row for row in data["orders"]}
    base_by_id = {row["order_id"]: row for row in baseline["data"]["likely_to_miss_due_dates"]["orders"]}
    assert by_id["ORD-029"]["pace"]["days_left"] == base_by_id["ORD-029"]["days_left"]
    assert by_id["ORD-108"]["pace"]["days_left"] > base_by_id["ORD-108"]["days_left"]
    assert "455" in data["basis"]
    refused = parse_tool(get_orders_at_risk.invoke({"stage": "ASSEMBLY"}))
    assert refused["ok"] is False


def test_get_orders_at_risk_flag_filter(db):
    payload = parse_tool(get_orders_at_risk.invoke({"flag": "OVERDUE"}))
    assert payload["ok"] is True
    assert payload["data"]["orders"]
    assert all("OVERDUE" in row["flags"] for row in payload["data"]["orders"])
    assert any(row["order_id"] == "ORD-120" for row in payload["data"]["orders"])
    stalled = parse_tool(get_orders_at_risk.invoke({"flag": "STALLED"}))
    assert any(row["order_id"] == "ORD-005" for row in stalled["data"]["orders"])


def test_trace_order(db):
    payload = parse_tool(trace_order.invoke({"order_id": "ORD-120"}))
    assert payload["ok"] is True
    assert payload["trace"]["rows"][0]["order_id"] == "ORD-120"
    assert "OVERDUE" in payload["data"]["risk"]["flags"]
    assert payload["data"]["limitations"]


def test_compare_order_progress_same_category_and_size(db):
    payload = parse_tool(compare_order_progress.invoke({"order_id": "ORD-029"}))
    assert payload["ok"] is True
    data = payload["data"]
    subject = data["subject"]
    assert subject["category"] == "ACCESSORIES"
    assert subject["product"] == "Beanie"
    assert subject["pieces"] == 1500
    assert subject["current_stage"] == "WASHING"
    assert subject["calendar_days_order_to_first_production"] == 17
    assert subject["elapsed_calendar_days"] == 22
    assert data["size_band"] == {
        "min_pieces": 1200,
        "max_pieces": 1800,
        "rule": "80% to 120% of this order's pieces, inclusive",
    }
    assert data["completed_peer_count"] == 6
    assert data["same_product_completed_count"] == 4
    assert data["cycle_calendar_days"]["median"] == 28.5
    assert data["calendar_days_versus_median"] == -6.5
    assert data["verdict"] == "within_typical_cycle"
    assert data["peer_stage_history_count"] == 0
    spans = {row["stage"]: row["calendar_days_until_next"] for row in subject["stage_spans"]}
    assert spans["ORDERED"] == 17
    assert spans["KNITTING"] == 3
    assert spans["ASSEMBLY"] == 2
    assert spans["WASHING"] is None


def test_earliest_delivery_date_for_new_scarves(db):
    payload = parse_tool(earliest_delivery_date.invoke({"pieces": 2000, "product": "scarves"}))
    assert payload["ok"] is True
    data = payload["data"]
    assert data["category"] == "ACCESSORIES"
    assert data["matched_product"] == "Scarf"
    assert data["earliest_date"]
    chosen = date.fromisoformat(data["earliest_date"])
    on_day = parse_tool(
        check_feasibility.invoke(
            {"pieces": 2000, "due_date": data["earliest_date"], "product": "scarves"}
        )
    )
    assert on_day["data"]["verdict"] == data["verdict"]
    assert on_day["data"]["verdict"] != "NOT_FEASIBLE"
    day_before = chosen - timedelta(days=1)
    if day_before >= date(2026, 4, 1):
        earlier = parse_tool(
            check_feasibility.invoke(
                {"pieces": 2000, "due_date": day_before.isoformat(), "product": "scarves"}
            )
        )
        assert earlier["data"]["verdict"] == "NOT_FEASIBLE"


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
    assert len(payload["data"]["limitations"]) >= 3
    assert any("IN_PROGRESS" in item for item in payload["data"]["limitations"])
    assert any("pipeline" in item.lower() for item in payload["data"]["limitations"])
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


def test_check_feasibility_beanies_plural_maps_to_accessories(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 200, "due_date": "2026-04-03", "product": "beanies"}
        )
    )
    assert payload["ok"] is True
    assert payload["data"]["category"] == "ACCESSORIES"
    assert payload["data"]["matched_product"] == "Beanie"
    assert payload["data"]["limitations"]


def test_check_feasibility_hoodies_plural_maps_to_tops(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 800, "due_date": "2026-08-25", "product": "hoodies"}
        )
    )
    assert payload["ok"] is True
    assert payload["data"]["category"] == "TOPS"
    assert payload["data"]["matched_product"] == "Hoodie"


def test_check_feasibility_unknown_product(db):
    payload = parse_tool(
        check_feasibility.invoke(
            {"pieces": 10, "due_date": "2026-08-25", "product": "Spaceship"}
        )
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "UNKNOWN_PRODUCT"
