"""Build a local SQLite preview of the PostgreSQL mid-platform schema.

DBeaver can open this file if Postgres superuser password is not available.
Table/column shapes follow postgresql_database on
feat/postgresql-data-admin-integration (workshop rows split; production_date).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SNAPSHOT_CSV = DATA / "examples3.0" / "altogether_summary.csv"
OUT = DATA / "factory_copilot_preview.db"


def parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def load_orders() -> pd.DataFrame:
    df = pd.read_csv(DATA / "orders.csv")
    for col in ("order_date", "due_date", "last_activity_date", "completed_date"):
        df[col] = parse_dates(df[col])
    df["days_late"] = pd.to_numeric(df["days_late"], errors="coerce")
    df["pieces"] = pd.to_numeric(df["pieces"], errors="coerce").astype("int64")
    return df


def load_production() -> pd.DataFrame:
    df = pd.read_csv(DATA / "production_log.csv")
    df["production_date"] = parse_dates(df["date"])
    df["pieces_completed"] = pd.to_numeric(df["pieces_completed"], errors="coerce").astype(
        "int64"
    )
    return df[["production_date", "stage", "pieces_completed"]]


def load_workshops() -> pd.DataFrame:
    df = pd.read_csv(DATA / "workshops.csv")
    rows = []
    for rec in df.to_dict(orient="records"):
        makes = str(rec["makes"]).strip()
        parts = ["TOPS", "ACCESSORIES"] if makes == "TOPS+ACCESSORIES" else [makes]
        for part in parts:
            row = dict(rec)
            row["makes"] = part
            notes = rec.get("notes")
            row["notes"] = "" if notes is None or (isinstance(notes, float) and pd.isna(notes)) else str(notes)
            if pd.isna(row.get("max_batch_pieces")):
                row["max_batch_pieces"] = None
            rows.append(row)
    out = pd.DataFrame(rows)
    return out[
        [
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
    ]


def load_snapshot() -> pd.DataFrame:
    df = pd.read_csv(SNAPSHOT_CSV)
    df["date"] = parse_dates(df["date"])
    return df[["order_id", "status", "stage", "date"]]


DDL = """
DROP TABLE IF EXISTS snapshot;
DROP TABLE IF EXISTS workshops;
DROP TABLE IF EXISTS production_log;
DROP TABLE IF EXISTS orders;

CREATE TABLE orders (
  order_id TEXT NOT NULL PRIMARY KEY,
  customer TEXT NOT NULL,
  product TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('TOPS', 'ACCESSORIES')),
  pieces INTEGER NOT NULL CHECK (pieces > 0),
  order_date TEXT NOT NULL,
  due_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
  current_stage TEXT NOT NULL CHECK (current_stage IN (
    'ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE'
  )),
  last_activity_date TEXT NOT NULL,
  completed_date TEXT,
  days_late INTEGER
);

CREATE TABLE production_log (
  production_date TEXT NOT NULL,
  stage TEXT NOT NULL CHECK (stage IN ('KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')),
  pieces_completed INTEGER NOT NULL CHECK (pieces_completed >= 0),
  PRIMARY KEY (production_date, stage)
);

CREATE TABLE workshops (
  workshop_id TEXT NOT NULL,
  name TEXT NOT NULL,
  capacity_pieces_per_day INTEGER NOT NULL,
  pickup_lead_days INTEGER NOT NULL,
  defect_rate REAL NOT NULL,
  cost_per_piece REAL NOT NULL,
  makes TEXT NOT NULL CHECK (makes IN ('TOPS', 'ACCESSORIES')),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED')),
  max_batch_pieces INTEGER,
  current_queue_days REAL NOT NULL,
  notes TEXT NOT NULL,
  PRIMARY KEY (workshop_id, makes)
);

CREATE TABLE snapshot (
  order_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
  stage TEXT NOT NULL CHECK (stage IN (
    'ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE'
  )),
  date TEXT NOT NULL,
  PRIMARY KEY (order_id, status, stage, date)
);
"""


def main() -> None:
    orders = load_orders()
    production = load_production()
    shops = load_workshops()
    snap = load_snapshot()

    if OUT.exists():
        OUT.unlink()
    conn = sqlite3.connect(OUT)
    try:
        conn.executescript(DDL)
        orders.to_sql("orders", conn, if_exists="append", index=False)
        production.to_sql("production_log", conn, if_exists="append", index=False)
        shops.to_sql("workshops", conn, if_exists="append", index=False)
        snap.to_sql("snapshot", conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()

    print("wrote", OUT)
    print("orders", len(orders), "production_log", len(production))
    print("workshops", len(shops), "distinct shops", shops["workshop_id"].nunique())
    print("snapshot", len(snap))


if __name__ == "__main__":
    main()
