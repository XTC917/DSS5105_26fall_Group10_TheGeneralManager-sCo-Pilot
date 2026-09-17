"""Canonical PostgreSQL data access for factory operational tables."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from psycopg import sql

from backend.pg_config import PG_SCHEMA
from backend.services.pg_database import connect


class FactoryDB:
    def __init__(self, data_dir: Any = None) -> None:
        self.data_dir = data_dir

    def connect(self):
        return connect(admin=False)

    def admin_connect(self):
        return connect(admin=True)

    def initialize(self, force: bool = False) -> str:
        with self.admin_connect() as conn:
            tables = conn.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s AND table_name IN ('orders','production_log','workshops','snapshot')
                """ , (PG_SCHEMA,)
            ).fetchall()
        if len(tables) < 4:
            raise RuntimeError("PostgreSQL baseline is not installed. Run alembic upgrade head first.")
        return "reused"

    def _fetch(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def get_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        rows = self._fetch(
            f"SELECT * FROM {PG_SCHEMA}.orders WHERE order_id = %s",
            (order_id.strip(),),
        )
        return rows[0] if rows else None

    def find_orders(self, *, order_id=None, customer=None, product=None, products=None,
                    status=None, category=None, current_stage=None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if order_id:
            clauses.append("order_id = %s")
            params.append(order_id.strip())
        if customer:
            clauses.append("LOWER(customer) = LOWER(%s)")
            params.append(customer.strip())
        names = []
        for raw in list(products or []) + ([product] if product else []):
            name = raw.strip()
            if name and name.lower() not in [n.lower() for n in names]:
                names.append(name)
        if names:
            clauses.append("LOWER(product) = ANY(%s)")
            params.append([n.lower() for n in names])
        for field, value in (("status", status), ("category", category), ("current_stage", current_stage)):
            if value:
                clauses.append(f"{field} = %s")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self._fetch(f"SELECT * FROM {PG_SCHEMA}.orders{where} ORDER BY order_id", tuple(params))

    def in_progress_orders(self):
        return self.find_orders(status="IN_PROGRESS")

    def order_snapshot_history(self, order_id: str) -> list[dict[str, Any]]:
        """Observed stage-entry dates from app.snapshot (not production_log)."""
        rows = self._fetch(
            f"""
            SELECT order_id, status, stage, date
            FROM {PG_SCHEMA}.snapshot
            WHERE order_id = %s
            ORDER BY date, stage
            """,
            (order_id.strip(),),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            d = item.get("date")
            if hasattr(d, "isoformat"):
                item["date"] = d.isoformat()
            out.append(item)
        return out


    def list_products(self):
        return self._fetch(f"SELECT DISTINCT product, category FROM {PG_SCHEMA}.orders ORDER BY product")

    def production_log(self, stage: str | None = None):
        if stage:
            return self._fetch(f"SELECT production_date AS date, stage, pieces_completed FROM {PG_SCHEMA}.production_log WHERE stage = %s ORDER BY production_date", (stage,))
        return self._fetch(f"SELECT production_date AS date, stage, pieces_completed FROM {PG_SCHEMA}.production_log ORDER BY production_date, stage")

    def workshops(self, *, status: str | None = None, category: str | None = None):
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = %s")
            params.append(status)
        if category:
            clauses.append("makes = %s")
            params.append(category)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return self._fetch(f"SELECT * FROM {PG_SCHEMA}.workshops{where} ORDER BY workshop_id, makes", tuple(params))


_DB: FactoryDB | None = None


def init_db(*, data_dir=None, **_kwargs) -> FactoryDB:
    global _DB
    _DB = FactoryDB(data_dir=data_dir)
    _DB.initialize()
    return _DB


def get_db() -> FactoryDB:
    if _DB is None:
        raise RuntimeError("Database is not initialised. Call init_db() first.")
    return _DB
