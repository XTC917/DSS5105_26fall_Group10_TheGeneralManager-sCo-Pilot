"""Integrated Data Management API (PostgreSQL app + admin_meta).

Covers the migrated upload / datasource / query routers:
- datasources seeded and listed from PostgreSQL
- upload preview validates columns without touching the DB
- import into workshops + status polling
- baseline check requires the alembic PostgreSQL baseline
- read-only SQL gateway still blocks writes and multi-statements
"""

from __future__ import annotations

import io
import time

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.database import get_db


def _wait_for_status(client: TestClient, upload_id: int, timeout: float = 15.0, headers: dict | None = None) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        res = client.get(f"/api/admin/upload/status/{upload_id}", headers=headers)
        assert res.status_code == 200, res.text
        last = res.json()
        if last.get("status") in {"success", "failed", "partial"}:
            return last
        time.sleep(0.3)
    raise AssertionError(f"import did not finish in time: {last}")


def test_admin_datasources_seeded(db, admin_auth_headers):
    with TestClient(app) as client:
        res = client.get("/api/admin/datasources/", headers=admin_auth_headers)
        assert res.status_code == 200, res.text
        body = res.json()
        tables = {row["table_name"] for row in body}
        assert {"orders", "production_log", "workshops"} <= tables
        assert all(row["row_count"] and row["row_count"] > 0 for row in body)


def test_admin_upload_preview_and_import_workshops(db, admin_auth_headers):
    assert db is not None
    before = db.workshops()
    assert before, "seed workshops must exist"

    frame = pd.DataFrame(before)
    buf = io.BytesIO()
    frame.to_csv(buf, index=False)
    content = buf.getvalue()

    with TestClient(app) as client:
        preview = client.post(
            "/api/admin/upload/preview",
            files={"file": ("workshops.csv", content, "text/csv")},
            headers=admin_auth_headers,
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["success"] is True

        started = client.post(
            "/api/admin/upload/import",
            files={"file": ("workshops.csv", content, "text/csv")},
            data={"table_name": "workshops", "if_exists": "replace"},
            headers=admin_auth_headers,
        )
        assert started.status_code == 200, started.text
        upload_id = started.json()["upload_id"]

        final = _wait_for_status(client, upload_id, headers=admin_auth_headers)
        assert final["status"] == "success", final

    after = db.workshops()
    assert len(after) == len(before)
    assert {w["workshop_id"] for w in after} == {w["workshop_id"] for w in before}


def test_admin_reject_unknown_table(db, admin_auth_headers):
    buf = io.BytesIO(b"a,b\n1,2\n")
    with TestClient(app) as client:
        res = client.post(
            "/api/admin/upload/import",
            files={"file": ("evil.csv", buf.getvalue(), "text/csv")},
            data={"table_name": "sqlite_master", "if_exists": "replace"},
            headers=admin_auth_headers,
        )
        assert res.status_code == 400


def test_admin_baseline_requires_postgres_tables(db):
    from backend.pg_config import PG_SCHEMA
    from backend.services.pg_database import connect

    with connect(admin=True) as conn:
        rows = conn.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name IN ('orders', 'production_log', 'workshops', 'snapshot')
            """,
            (PG_SCHEMA,),
        ).fetchall()
    assert {row["table_name"] for row in rows} == {
        "orders",
        "production_log",
        "workshops",
        "snapshot",
    }


def test_query_execute_read_only(db, admin_auth_headers):
    with TestClient(app) as client:
        ok = client.post(
            "/api/query/execute", json={"sql": "SELECT COUNT(*) AS c FROM orders"},
            headers=admin_auth_headers,
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["success"] is True
        assert body["data"][0]["c"] > 0

        blocked = client.post(
            "/api/query/execute", json={"sql": "DELETE FROM orders"},
            headers=admin_auth_headers,
        )
        assert blocked.status_code == 200
        assert blocked.json()["success"] is False

        schema = client.get("/api/query/schema", headers=admin_auth_headers)
        assert schema.status_code == 200
        assert schema.json()["success"] is True
        assert "orders" in schema.json()["schema"]
