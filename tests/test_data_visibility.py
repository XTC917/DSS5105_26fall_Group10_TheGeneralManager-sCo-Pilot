"""Factory date n can read only through n-1. Later rows stay in the database."""

from __future__ import annotations

from datetime import timedelta

from backend.config import using_factory_date
from backend.pg_config import PG_SCHEMA
from backend.services.database import visible_through


def test_production_log_stops_at_yesterday(db):
    raw = db._fetch(f"SELECT MAX(production_date) AS latest FROM {PG_SCHEMA}.production_log")
    latest = raw[0]["latest"]
    assert latest is not None
    with using_factory_date(latest):
        assert visible_through() == latest - timedelta(days=1)
        dates = {row["date"] for row in db.production_log()}
        assert latest not in dates
        assert dates
        assert max(dates) <= latest - timedelta(days=1)


def test_order_state_after_yesterday_is_rewound(db):
    raw = db._fetch(
        f"SELECT order_id, last_activity_date FROM {PG_SCHEMA}.orders ORDER BY last_activity_date DESC LIMIT 1"
    )
    order_id = raw[0]["order_id"]
    moved = raw[0]["last_activity_date"]
    with using_factory_date(moved):
        row = db.get_order_by_id(order_id)
        assert row is not None
        assert row["last_activity_date"] < moved
        history = db.order_snapshot_history(order_id)
        assert history
        assert all(item["date"] < moved.isoformat() for item in history)
