"""Canonical PostgreSQL data access for factory operational tables."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from psycopg import sql

from backend.config import factory_date
from backend.pg_config import PG_SCHEMA
from backend.services.calculations import parse_iso_date
from backend.services.pg_database import connect


def visible_through() -> date:
    """Last date the database may return. Factory today is n, and n itself is included."""
    return factory_date()


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    return parse_iso_date(value)


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
            f"SELECT * FROM {PG_SCHEMA}.orders WHERE UPPER(order_id) = UPPER(%s)",
            (order_id.strip(),),
        )
        projected = self._visible_orders(rows)
        return projected[0] if projected else None

    def find_orders(self, *, order_id=None, customer=None, product=None, products=None,
                    status=None, category=None, current_stage=None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if order_id:
            clauses.append("UPPER(order_id) = UPPER(%s)")
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
        if category:
            clauses.append("category = %s")
            params.append(category)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._fetch(f"SELECT * FROM {PG_SCHEMA}.orders{where} ORDER BY order_id", tuple(params))
        visible = self._visible_orders(rows)
        if status:
            visible = [row for row in visible if row.get("status") == status]
        if current_stage:
            visible = [row for row in visible if row.get("current_stage") == current_stage]
        return visible

    def in_progress_orders(self):
        return self.find_orders(status="IN_PROGRESS")

    def order_snapshot_history(self, order_id: str) -> list[dict[str, Any]]:
        """Observed stage-entry dates from app.snapshot (not production_log)."""
        rows = self._fetch(
            f"""
            SELECT order_id, status, stage, date
            FROM {PG_SCHEMA}.snapshot
            WHERE UPPER(order_id) = UPPER(%s)
              AND date <= %s
            ORDER BY date, stage
            """,
            (order_id.strip(), visible_through()),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            d = item.get("date")
            if hasattr(d, "isoformat"):
                item["date"] = d.isoformat()
            out.append(item)
        return out


    def csv_latest_updates(self) -> dict[str, date]:
        """Newest observed date in each dated CSV. A planned due date is not an update."""
        row = self._fetch(
            f"""
            SELECT
                GREATEST(
                    MAX(order_date),
                    MAX(last_activity_date),
                    MAX(completed_date)
                ) AS orders_csv,
                (SELECT MAX(production_date) FROM {PG_SCHEMA}.production_log) AS production_log_csv
            FROM {PG_SCHEMA}.orders
            """
        )
        latest: dict[str, date] = {}
        if not row:
            return latest
        mapping = {
            "orders.csv": row[0].get("orders_csv"),
            "production_log.csv": row[0].get("production_log_csv"),
        }
        for name, value in mapping.items():
            parsed = value if isinstance(value, date) else parse_iso_date(value)
            if isinstance(parsed, date):
                latest[name] = parsed
        return latest

    def latest_record_date(self) -> date | None:
        """Latest observed factory date. Planned due dates and the visibility cutoff are not included."""
        row = self._fetch(
            f"""
            SELECT MAX(d) AS latest FROM (
                SELECT MAX(production_date) AS d FROM {PG_SCHEMA}.production_log
                UNION ALL
                SELECT MAX(date) FROM {PG_SCHEMA}.snapshot
                UNION ALL
                SELECT MAX(order_date) FROM {PG_SCHEMA}.orders
                UNION ALL
                SELECT MAX(last_activity_date) FROM {PG_SCHEMA}.orders
                UNION ALL
                SELECT MAX(completed_date) FROM {PG_SCHEMA}.orders
            ) dates
            """
        )
        latest = row[0]["latest"] if row else None
        if hasattr(latest, "isoformat"):
            return latest
        return parse_iso_date(latest) if latest else None

    def list_products(self):
        return self._fetch(
            f"SELECT DISTINCT product, category FROM {PG_SCHEMA}.orders WHERE order_date <= %s ORDER BY product",
            (visible_through(),),
        )

    def production_log(self, stage: str | None = None):
        cutoff = visible_through()
        if stage:
            return self._fetch(
                f"SELECT production_date AS date, stage, pieces_completed FROM {PG_SCHEMA}.production_log WHERE stage = %s AND production_date <= %s ORDER BY production_date",
                (stage, cutoff),
            )
        return self._fetch(
            f"SELECT production_date AS date, stage, pieces_completed FROM {PG_SCHEMA}.production_log WHERE production_date <= %s ORDER BY production_date, stage",
            (cutoff,),
        )

    def _visible_orders(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop orders that do not exist yet, and rewind state that happened after the cutoff."""
        cutoff = visible_through()
        rewind_ids: list[str] = []
        pending: list[dict[str, Any]] = []
        for row in rows:
            opened = _as_date(row.get("order_date"))
            if opened is not None and opened > cutoff:
                continue
            moved = _as_date(row.get("last_activity_date"))
            done = _as_date(row.get("completed_date"))
            if (moved is not None and moved > cutoff) or (done is not None and done > cutoff):
                rewind_ids.append(row["order_id"])
                pending.append({**row, "_rewind": True})
            else:
                pending.append(row)
        snaps = self._latest_visible_snapshots(rewind_ids, cutoff) if rewind_ids else {}
        out: list[dict[str, Any]] = []
        for row in pending:
            if not row.get("_rewind"):
                out.append(row)
                continue
            projected = self._rewind_order(row, snaps.get(row["order_id"]), cutoff)
            if projected is not None:
                out.append(projected)
        return out

    def _latest_visible_snapshots(self, order_ids: list[str], cutoff: date) -> dict[str, dict[str, Any]]:
        rows = self._fetch(
            f"""
            SELECT DISTINCT ON (order_id) order_id, status, stage, date
            FROM {PG_SCHEMA}.snapshot
            WHERE order_id = ANY(%s) AND date <= %s
            ORDER BY order_id, date DESC,
                CASE stage
                    WHEN 'COMPLETE' THEN 6
                    WHEN 'PACKING' THEN 5
                    WHEN 'WASHING' THEN 4
                    WHEN 'ASSEMBLY' THEN 3
                    WHEN 'KNITTING' THEN 2
                    ELSE 1
                END DESC
            """,
            (order_ids, cutoff),
        )
        return {row["order_id"]: row for row in rows}

    def _rewind_order(self, row: dict[str, Any], snap: dict[str, Any] | None, cutoff: date) -> dict[str, Any] | None:
        item = {key: value for key, value in row.items() if key != "_rewind"}
        if snap is None:
            opened = _as_date(item.get("order_date"))
            if opened is None or opened > cutoff:
                return None
            item["status"] = "IN_PROGRESS"
            item["current_stage"] = "ORDERED"
            item["last_activity_date"] = opened
            item["completed_date"] = None
            item["days_late"] = None
            return item
        item["status"] = snap["status"]
        item["current_stage"] = snap["stage"]
        item["last_activity_date"] = snap["date"]
        if snap["status"] == "COMPLETE":
            done = _as_date(snap["date"])
            due = _as_date(item.get("due_date"))
            item["completed_date"] = done
            item["days_late"] = (done - due).days if done is not None and due is not None else None
        else:
            item["completed_date"] = None
            item["days_late"] = None
        return item

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
