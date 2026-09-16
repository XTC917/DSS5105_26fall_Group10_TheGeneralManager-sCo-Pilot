"""Guard the CSV schemas so teammates do not invent column names."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.config import DATA_DIR, FACTORY_TODAY
from backend.services.database import FactoryDB


def test_csv_columns_match_data_dictionary(db):
    assert db.find_orders()
    order = db.get_order_by_id("ORD-057")
    assert order is not None
    assert set(order) == {
        "order_id",
        "customer",
        "product",
        "category",
        "pieces",
        "order_date",
        "due_date",
        "status",
        "current_stage",
        "last_activity_date",
        "completed_date",
        "days_late",
    }

    prod = db.production_log()[0]
    assert set(prod) == {"date", "stage", "pieces_completed"}

    shop = db.workshops()[0]
    assert {
        "workshop_id",
        "name",
        "capacity_pieces_per_day",
        "pickup_lead_days",
        "defect_rate",
        "cost_per_piece",
        "makes",
        "status",
        "max_batch_pieces",
        "current_queue_days",
        "notes",
    } <= set(shop)


def test_row_counts_match_data_dictionary(db):
    assert len(db.find_orders()) == 120
    assert len(db.production_log()) == 360
    assert len({row["workshop_id"] for row in db.workshops()}) == 8


def test_factory_today_is_dataset_clock():
    assert FACTORY_TODAY.isoformat() == "2026-04-01"
    assert (DATA_DIR / "orders.csv").exists()


def test_blank_completed_date_is_null(db):
    row = db.get_order_by_id("ORD-120")
    assert row is not None
    assert row["status"] == "IN_PROGRESS"
    assert row["completed_date"] is None
    assert row["days_late"] is None


def test_rejected_unknown_columns(tmp_path):
    from backend.services.file_importer import FileImporter

    bad = tmp_path / "orders.csv"
    pd.DataFrame({"foo": [1]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        FileImporter()._prepare_frame(pd.read_csv(bad), "orders")
