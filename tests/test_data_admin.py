"""Integrated Data Management API (shares data/factory.db).

Covers the migrated upload / datasource / query routers:
- datasources seeded and listed from the shared DB
- upload preview validates columns without touching the DB
- import into workshops + status polling
- restart preserves imports (no CSV reseed over existing tables)
- read-only SQL authorizer still blocks writes and non-allowlisted tables
"""

from __future__ import annotations

import io
import time

import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.database import get_db


def _wait_for_status(client: TestClient, upload_id: int, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        res = client.get(f"/api/admin/upload/status/{upload_id}")
        assert res.status_code == 200, res.text
        last = res.json()
        if last.get("status") in {"success", "failed", "partial"}:
            return last
        time.sleep(0.3)
    raise AssertionError(f"import did not finish in time: {last}")


def test_admin_datasources_seeded(db):
    with TestClient(app) as client:
        res = client.get("/api/admin/datasources/")
        assert res.status_code == 200, res.text
        body = res.json()
        tables = {row["table_name"] for row in body}
        assert {"orders", "production_log", "workshops"} <= tables
        assert all(row["row_count"] and row["row_count"] > 0 for row in body)


def test_admin_upload_preview_and_import_workshops(db):
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
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["success"] is True

        started = client.post(
            "/api/admin/upload/import",
            files={"file": ("workshops.csv", content, "text/csv")},
            data={"table_name": "workshops", "if_exists": "replace"},
        )
        assert started.status_code == 200, started.text
        upload_id = started.json()["upload_id"]

        final = _wait_for_status(client, upload_id)
        assert final["status"] == "success", final

    after = db.workshops()
    assert len(after) == len(before)
    assert {w["workshop_id"] for w in after} == {w["workshop_id"] for w in before}


def test_admin_reject_unknown_table(db):
    buf = io.BytesIO(b"a,b\n1,2\n")
    with TestClient(app) as client:
        res = client.post(
            "/api/admin/upload/import",
            files={"file": ("evil.csv", buf.getvalue(), "text/csv")},
            data={"table_name": "sqlite_master", "if_exists": "replace"},
        )
        assert res.status_code == 400


def test_admin_restart_preserves_imports(tmp_path):
    from backend.services.database import FactoryDB

    probe = FactoryDB(db_path=tmp_path / "probe.db")
    assert probe.initialize() == "seeded"
    with probe.connect() as conn:
        conn.execute("INSERT INTO workshops (workshop_id, name) VALUES ('WS-PROBE', 'probe')")
        conn.commit()
    with probe.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM workshops WHERE workshop_id = 'WS-PROBE'"
        ).fetchone()["c"] == 1
    assert probe.initialize() == "reused"
    with probe.connect() as conn:
        kept = conn.execute(
            "SELECT COUNT(*) AS c FROM workshops WHERE workshop_id = 'WS-PROBE'"
        ).fetchone()["c"]
    assert kept == 1, "reuse must not reseed probe rows away"
    probe2 = FactoryDB(db_path=tmp_path / "probe2.db")
    assert probe2.initialize() == "seeded"
    assert probe2.initialize(force=True) == "reseeded"
    with probe2.connect() as conn:
        restored = conn.execute("SELECT COUNT(*) AS c FROM workshops").fetchone()["c"]
    assert restored > 0


def test_query_execute_read_only(db):
    with TestClient(app) as client:
        ok = client.post(
            "/api/query/execute", json={"sql": "SELECT COUNT(*) AS c FROM orders"}
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["success"] is True
        assert body["data"][0]["c"] > 0

        blocked = client.post(
            "/api/query/execute", json={"sql": "DELETE FROM orders"}
        )
        assert blocked.status_code == 200
        assert blocked.json()["success"] is False

        schema = client.get("/api/query/schema")
        assert schema.status_code == 200
        assert schema.json()["success"] is True
        assert "orders" in schema.json()["schema"]
