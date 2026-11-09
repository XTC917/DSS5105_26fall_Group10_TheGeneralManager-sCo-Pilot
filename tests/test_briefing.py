"""Morning briefing tool. No LLM required."""

from __future__ import annotations

from backend.tools.briefing import get_morning_briefing
from backend.tools.retrieval import get_orders_at_risk
from tests.conftest import parse_tool


def test_briefing_reuses_at_risk_set(db):
    briefing = parse_tool(get_morning_briefing.invoke({}))
    risk = parse_tool(get_orders_at_risk.invoke({}))
    assert briefing["ok"] is True
    data = briefing["data"]
    assert data["factory_today"] == "2026-04-01"
    briefing_ids = {row["order_id"] for row in data["at_risk"]["orders"]}
    risk_ids = {row["order_id"] for row in risk["data"]["orders"]}
    assert briefing_ids == risk_ids
    assert data["at_risk"]["count"] == 3
    assert data["in_progress_order_count"] == 34
    assert set(data["in_progress_by_stage"]) == {
        "ORDERED",
        "KNITTING",
        "ASSEMBLY",
        "WASHING",
        "PACKING",
    }
    assert data["yesterday_output"]["date"] == "2026-03-31"
    assert data["data_note"] == (
        "Some of the data used here was last updated through 2026-03-31 (production_log)."
    )


def test_briefing_includes_suspended_workshop_from_csv(db):
    payload = parse_tool(get_morning_briefing.invoke({}))
    suspended = payload["data"]["suspended_workshops"]
    assert any(row["workshop_id"] == "W7" and row["name"] == "OldMill" for row in suspended)


def test_briefing_stage_drop_rule_is_inspectable(db):
    payload = parse_tool(get_morning_briefing.invoke({}))
    unusual = payload["data"]["unusual_stage_output"]
    assert unusual
    assembly = next(row for row in unusual if row["stage"] == "ASSEMBLY")
    assert "0.7" in assembly["rule"]
    assert assembly["last_working_date"] == "2026-03-31"
    expected_flag = assembly["last_day_pieces"] < 0.70 * assembly["lookback_median"]
    assert assembly["flagged"] is expected_flag
    days = {row["date"]: row["pieces"] for row in assembly["working_days"]}
    assert days["2026-03-25"] == 394
    assert days["2026-03-31"] == assembly["last_day_pieces"]
    assert "2026-03-29" not in days
    assert len(assembly["working_days"]) == 30


def test_last_week_tracks_every_factory_week(db):
    data = parse_tool(get_morning_briefing.invoke({}))["data"]["last_week"]
    assert data["start"] == "2026-03-23"
    assert data["end"] == "2026-03-28"
    weeks = data["weeks"]
    assert weeks
    assert weeks[0]["start"] == "2026-01-05"
    assert weeks[0]["end"] == "2026-01-10"
    assert weeks[0]["partial"] is False
    assert weeks[-1]["partial"] is False
    assert weeks[-1]["start"] == "2026-03-23"
    assert weeks[-1]["end"] == "2026-03-28"
    assert [row["week"] for row in weeks] == list(range(1, len(weeks) + 1))
    last_complete = weeks[-1]
    assert last_complete["completed"] == last_complete["on_time"] + last_complete["overdue"]
    assert set(data["customers"]) == {row["customer"] for row in data["products"]}
    assert all(stage in last_complete for stage in ("KNITTING", "ASSEMBLY", "WASHING", "PACKING"))
    assert "revenue" not in data


def test_briefing_does_not_invent_revenue_or_workers(db):
    data = parse_tool(get_morning_briefing.invoke({}))["data"]
    assert "revenue" not in data
    assert "selling_price" not in data
    assert "worker_name" not in data
    assert all("revenue" not in row for row in data["at_risk"]["orders"])
