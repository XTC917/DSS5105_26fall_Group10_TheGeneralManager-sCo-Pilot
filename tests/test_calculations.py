"""Date and risk arithmetic must be deterministic and Sunday-aware."""

from __future__ import annotations

from datetime import date

from backend.config import FACTORY_TODAY, STALL_WORKING_DAYS
from backend.services.calculations import (
    assess_order_risk,
    count_working_days,
    is_working_day,
    remaining_stages,
    working_days_since_activity,
    working_days_until_due,
)


def test_sunday_is_closed():
    assert is_working_day(date(2026, 3, 28)) is True  # Saturday
    assert is_working_day(date(2026, 3, 29)) is False  # Sunday
    assert is_working_day(date(2026, 4, 1)) is True  # Wednesday


def test_count_working_days_skips_sunday():
    # 28 Sat, 29 Sun, 30 Mon, 31 Tue, 1 Wed → 4 open days
    assert count_working_days(date(2026, 3, 28), date(2026, 4, 1)) == 4


def test_working_days_until_due_overdue_is_zero():
    assert working_days_until_due(date(2026, 3, 17), FACTORY_TODAY) == 0


def test_working_days_until_due_today_is_one():
    assert working_days_until_due(FACTORY_TODAY, FACTORY_TODAY) == 1


def test_stall_threshold_example():
    # last activity Sat 28 Mar → idle Sun(skip)+Mon+Tue+Wed = 3 working days
    idle = working_days_since_activity(date(2026, 3, 28), FACTORY_TODAY)
    assert idle == 3
    assert idle >= STALL_WORKING_DAYS


def test_remaining_stages():
    assert remaining_stages("KNITTING") == ["KNITTING", "ASSEMBLY", "WASHING", "PACKING"]
    assert remaining_stages("PACKING") == ["PACKING"]
    assert remaining_stages("COMPLETE") == []
    assert remaining_stages("UNKNOWN") == []


def test_overdue_order_is_at_risk():
    order = {
        "status": "IN_PROGRESS",
        "current_stage": "ASSEMBLY",
        "due_date": "2026-03-17",
        "last_activity_date": "2026-03-30",
        "completed_date": None,
    }
    risk = assess_order_risk(order)
    assert risk["at_risk"] is True
    assert "OVERDUE" in risk["flags"]


def test_complete_order_is_never_at_risk():
    order = {
        "status": "COMPLETE",
        "current_stage": "COMPLETE",
        "due_date": "2026-01-27",
        "last_activity_date": "2026-02-08",
        "completed_date": "2026-02-08",
    }
    risk = assess_order_risk(order)
    assert risk["at_risk"] is False
    assert risk["flags"] == []
