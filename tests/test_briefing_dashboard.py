"""Dashboard boundary coverage without a PostgreSQL connection."""
from datetime import date

from backend.services import briefing


def order(key, due, activity="2026-03-31", **extra):
    return dict(order_id=key, customer="Customer", product="Hoodie", pieces=100,
                due_date=due, last_activity_date=activity, current_stage="PACKING",
                status="IN_PROGRESS", **extra)


class Records:
    def __init__(self, active, completed=()):
        self.active, self.completed = active, completed

    def in_progress_orders(self):
        return self.active

    def find_orders(self, **kwargs):
        assert kwargs == {"status": "COMPLETE"}
        return self.completed


def test_dashboard_deadline_boundaries_and_overlapping_flags(monkeypatch):
    monkeypatch.setattr(briefing, "stage_medians", lambda db: {"PACKING": 1000})
    active = [order(str(i), due) for i, due in enumerate([
        "2026-03-31", "2026-04-01", "2026-04-03", "2026-04-04",
        "2026-04-08", "2026-04-09", None])]
    active[0]["last_activity_date"] = "2026-03-27"
    board = briefing.build_dashboard(Records(active))
    assert board["deadline_buckets"] == dict(OVERDUE=1, TODAY=1, TWO_DAYS=1, WEEK=2, LATER=1, UNKNOWN=1)
    assert sum(board["deadline_buckets"].values()) == board["metrics"]["active"] == 7
    assert board["metrics"]["due_soon"] == 2
    assert board["metrics"]["overdue"] == 1
    assert board["metrics"]["stalled"] == 1
    assert {"OVERDUE", "STALLED"}.issubset(board["orders"][0]["flags"])
    assert board["orders"][-1]["bucket"] == "UNKNOWN"


def test_completed_window_skips_sunday_and_derives_lateness(monkeypatch):
    monkeypatch.setattr(briefing, "FACTORY_TODAY", date(2026, 4, 6))
    monkeypatch.setattr(briefing, "stage_medians", lambda db: {})
    completed = [
        order("late", "2026-04-03", completed_date="2026-04-04"),
        order("on-time", "2026-04-05", completed_date=date(2026, 4, 4)),
        order("excluded", "2026-04-05", completed_date="2026-04-05"),
    ]
    board = briefing.build_dashboard(Records([], completed))
    assert board["completion_date"] == "2026-04-04"
    assert {row["order_id"]: row["days_late"] for row in board["completed_orders"]} == {"late": 1, "on-time": -1}
    assert board["metrics"]["active"] == 0
