"""SQLite data access. CSV files are the source of truth; the DB is a query cache.

We use SQLite (stdlib) rather than DuckDB because the three files are small,
clean, and need only simple filters. Teammates can inspect data/factory.db
with any SQLite viewer.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from backend.config import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)

_ORDERS_COLUMNS = [
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
]

_PRODUCTION_COLUMNS = ["date", "stage", "pieces_completed"]

_WORKSHOP_COLUMNS = [
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
]


class FactoryDB:
    def __init__(self, db_path: Path | None = None, data_dir: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Load the three CSVs into SQLite. Safe to call on every startup."""
        orders = pd.read_csv(self.data_dir / "orders.csv")
        production = pd.read_csv(self.data_dir / "production_log.csv")
        workshops = pd.read_csv(self.data_dir / "workshops.csv")

        self._validate_columns(orders, _ORDERS_COLUMNS, "orders.csv")
        self._validate_columns(production, _PRODUCTION_COLUMNS, "production_log.csv")
        self._validate_columns(workshops, _WORKSHOP_COLUMNS, "workshops.csv")

        orders = self._normalise_orders(orders)
        production = self._normalise_production(production)
        workshops = self._normalise_workshops(workshops)

        if self.db_path.exists():
            self.db_path.unlink()

        with self.connect() as conn:
            orders.to_sql("orders", conn, index=False)
            production.to_sql("production_log", conn, index=False)
            workshops.to_sql("workshops", conn, index=False)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_prod_stage ON production_log(stage)"
            )

        logger.info(
            "Loaded factory DB from CSV: %s orders, %s production rows, %s workshops",
            len(orders),
            len(production),
            len(workshops),
        )

    @staticmethod
    def _validate_columns(frame: pd.DataFrame, expected: list[str], filename: str) -> None:
        missing = [c for c in expected if c not in frame.columns]
        if missing:
            raise ValueError(f"{filename} is missing columns: {missing}")

    @staticmethod
    def _normalise_orders(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        for col in ("order_date", "due_date", "last_activity_date", "completed_date"):
            parsed = pd.to_datetime(out[col], errors="coerce")
            out[col] = parsed.dt.strftime("%Y-%m-%d")
        # Blank completed_date / days_late must be SQL NULL, not empty string.
        out["days_late"] = pd.to_numeric(out["days_late"], errors="coerce")
        out["pieces"] = pd.to_numeric(out["pieces"], errors="coerce").astype("int64")
        return out[_ORDERS_COLUMNS]

    @staticmethod
    def _normalise_production(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["date"] = out["date"].astype("string")
        out["pieces_completed"] = pd.to_numeric(out["pieces_completed"], errors="coerce").astype(
            "int64"
        )
        return out[_PRODUCTION_COLUMNS]

    @staticmethod
    def _normalise_workshops(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["max_batch_pieces"] = pd.to_numeric(out["max_batch_pieces"], errors="coerce")
        out["current_queue_days"] = pd.to_numeric(out["current_queue_days"], errors="coerce")
        return out[_WORKSHOP_COLUMNS]

    def _fetch(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            "SELECT * FROM orders WHERE order_id = ? COLLATE NOCASE",
            (order_id.strip(),),
        )
        return rows[0] if rows else None

    def find_orders(
        self,
        *,
        order_id: str | None = None,
        customer: str | None = None,
        product: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if order_id:
            clauses.append("order_id = ? COLLATE NOCASE")
            params.append(order_id.strip())
        if customer:
            clauses.append("LOWER(customer) = LOWER(?)")
            params.append(customer.strip())
        if product:
            clauses.append("LOWER(product) = LOWER(?)")
            params.append(product.strip())
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._fetch(
            f"SELECT * FROM orders{where} ORDER BY order_id",
            tuple(params),
        )

    def in_progress_orders(self) -> list[dict[str, Any]]:
        return self.find_orders(status="IN_PROGRESS")

    def list_products(self) -> list[dict[str, Any]]:
        return self._fetch(
            "SELECT DISTINCT product, category FROM orders ORDER BY product"
        )

    def production_log(self, stage: str | None = None) -> list[dict[str, Any]]:
        if stage:
            return self._fetch(
                "SELECT * FROM production_log WHERE stage = ? ORDER BY date",
                (stage,),
            )
        return self._fetch("SELECT * FROM production_log ORDER BY date, stage")

    def workshops(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            # makes is TOPS, ACCESSORIES, or TOPS+ACCESSORIES
            clauses.append("(makes = ? OR makes = 'TOPS+ACCESSORIES')")
            params.append(category)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return self._fetch(
            f"SELECT * FROM workshops{where} ORDER BY workshop_id",
            tuple(params),
        )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    # pandas writes NaN as NULL; expose as None in JSON.
    return {k: (None if _is_nan(v) else v) for k, v in data.items()}


def _is_nan(value: Any) -> bool:
    try:
        return isinstance(value, float) and value != value
    except Exception:
        return False


_DB: FactoryDB | None = None


def init_db(db_path: Path | None = None, data_dir: Path | None = None) -> FactoryDB:
    global _DB
    _DB = FactoryDB(db_path=db_path, data_dir=data_dir)
    _DB.initialize()
    return _DB


def get_db() -> FactoryDB:
    if _DB is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")
    return _DB
