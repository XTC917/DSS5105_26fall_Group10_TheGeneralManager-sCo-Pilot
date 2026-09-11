"""SQLite data access.

CSVs are seed data for first-time init only. After that the shared
data/factory.db is the source of truth, so restarting the backend must
NOT delete Data Management imports. Use reseed_from_csv() explicitly
for manual recovery.
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

    def initialize(self, force: bool = False) -> str:
        """Prepare the shared factory.db without destroying admin imports.

        - Missing file or missing business tables: seed from the CSVs,
          then create admin metadata tables.
        - force=True: explicit reseed (used by tests / manual recovery).
        - Otherwise: keep the existing DB untouched; only ensure the admin
          metadata tables and indexes exist.

        Returns "seeded" | "reused" | "reseeded".
        """
        if force or not self._has_business_tables():
            self._seed_from_csv()
            self.ensure_admin_tables()
            return "reseeded" if force else "seeded"
        self.ensure_admin_tables()
        return "reused"

    def _has_business_tables(self) -> bool:
        if not self.db_path.exists():
            return False
        expected: dict[str, set[str]] = {
            "orders": set(_ORDERS_COLUMNS),
            "production_log": set(_PRODUCTION_COLUMNS),
            "workshops": set(_WORKSHOP_COLUMNS),
        }
        try:
            with self.connect() as conn:
                names = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                for table, cols in expected.items():
                    if table not in names:
                        return False
                    pragma = conn.execute(f"PRAGMA table_info({table})").fetchall()
                    existing = {row["name"] for row in pragma}
                    if not cols.issubset(existing):
                        return False
        except Exception:
            return False
        return True

    def ensure_admin_tables(self) -> None:
        """Create Data Management metadata tables if missing (idempotent)."""
        from backend.services.data_admin import DATA_SOURCES_META

        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS upload_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_type TEXT,
                    total_rows INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    uploaded_by TEXT DEFAULT 'admin',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS import_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    total_rows INTEGER DEFAULT 0,
                    success_rows INTEGER DEFAULT 0,
                    failed_rows INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    FOREIGN KEY (upload_id) REFERENCES upload_history(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS data_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL,
                    table_name TEXT UNIQUE NOT NULL,
                    original_file TEXT,
                    description TEXT,
                    row_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_orders_customer
                    ON orders(customer);
                CREATE INDEX IF NOT EXISTS idx_orders_status
                    ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_prod_stage
                    ON production_log(stage);
                """
            )
            for table, meta in DATA_SOURCES_META.items():
                count_row = conn.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table}"
                ).fetchone()
                row_count = int(count_row["cnt"]) if count_row else 0
                conn.execute(
                    """
                    INSERT INTO data_sources
                        (source_name, table_name, original_file, description,
                         row_count, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(table_name) DO NOTHING
                    """,
                    (
                        meta["source_name"],
                        table,
                        meta["original_file"],
                        meta["description"],
                        row_count,
                    ),
                )
                # Backfill the count for fresh seeds (row_count 0/NULL only);
                # never overwrite a count that an import already set.
                conn.execute(
                    """
                    UPDATE data_sources
                    SET row_count = ?, is_active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE table_name = ?
                      AND (row_count IS NULL OR row_count = 0)
                    """,
                    (row_count, table),
                )
            conn.commit()

    def reseed_from_csv(self) -> None:
        """Explicit recovery path: delete factory.db and rebuild from CSVs."""
        self.initialize(force=True)

    def _seed_from_csv(self) -> None:
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
        products: list[str] | None = None,
        status: str | None = None,
        category: str | None = None,
        current_stage: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if order_id:
            clauses.append("order_id = ? COLLATE NOCASE")
            params.append(order_id.strip())
        if customer:
            clauses.append("LOWER(customer) = LOWER(?)")
            params.append(customer.strip())
        names: list[str] = []
        for raw in list(products or []) + ([product] if product else []):
            name = raw.strip()
            if name and name not in names:
                names.append(name)
        if names:
            placeholders = ", ".join("?" for _ in names)
            clauses.append(f"LOWER(product) IN ({placeholders})")
            params.extend(name.lower() for name in names)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if current_stage:
            clauses.append("current_stage = ?")
            params.append(current_stage)
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


def init_db(
    db_path: Path | None = None,
    data_dir: Path | None = None,
    state_db_path: Path | None = None,
) -> FactoryDB:
    global _DB
    _DB = FactoryDB(db_path=db_path, data_dir=data_dir)
    _DB.initialize()
    from backend.services.audit import init_state_db

    init_state_db(state_db_path)
    return _DB


def get_db() -> FactoryDB:
    if _DB is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")
    return _DB
