#!/usr/bin/env python
"""Create the SQLite schema for the factory data admin API."""

from __future__ import annotations

import argparse
import sys

from config import Config
from db import get_connection


def init_db(overwrite: bool = False) -> None:
    db_path = Config.DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        if not overwrite:
            print(f"Database '{db_path}' already exists. Pass --force to overwrite.")
            return
        db_path.unlink()

    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE orders (
                order_id TEXT PRIMARY KEY,
                customer TEXT,
                product TEXT,
                category TEXT,
                pieces INTEGER,
                order_date TEXT,
                due_date TEXT,
                status TEXT,
                current_stage TEXT,
                last_activity_date TEXT,
                completed_date TEXT,
                days_late INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE production_log (
                date TEXT NOT NULL,
                stage TEXT NOT NULL,
                pieces_completed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (date, stage)
            );

            CREATE TABLE workshops (
                workshop_id TEXT PRIMARY KEY,
                name TEXT,
                capacity_pieces_per_day INTEGER,
                pickup_lead_days INTEGER,
                defect_rate REAL,
                cost_per_piece REAL,
                makes TEXT,
                status TEXT,
                max_batch_pieces INTEGER,
                current_queue_days REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE upload_history (
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

            CREATE TABLE import_details (
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
                FOREIGN KEY (upload_id) REFERENCES upload_history(id) ON DELETE CASCADE
            );

            CREATE TABLE data_sources (
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

            CREATE INDEX idx_orders_customer ON orders(customer);
            CREATE INDEX idx_orders_status ON orders(status);
            CREATE INDEX idx_prod_stage ON production_log(stage);
            """
        )

        conn.executemany(
            """
            INSERT INTO data_sources (source_name, table_name, original_file, description)
            VALUES (:source_name, :table_name, :original_file, :description)
            """,
            [
                {"table_name": table, **meta}
                for table, meta in Config.DATA_SOURCES.items()
            ],
        )
        conn.commit()
    finally:
        conn.close()

    print(f"SQLite database created: {db_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete an existing database file and recreate it",
    )
    args = parser.parse_args()
    try:
        init_db(overwrite=args.force)
    except Exception as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
