"""HTTP layer. Chat is skipped unless an API key is present."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["factory_today"] == "2026-04-01"
        assert "get_order_status" in body["tools"]
        assert "check_feasibility" in body["tools"]
        assert "get_morning_briefing" in body["tools"]
        assert "find_orders" in body["tools"]
        assert "discover_factory_issues" in body["tools"]
        assert "get_today_priority" in body["tools"]
        assert "draw" in body["tools"]
        assert "render_table" in body["tools"]


def test_chat_requires_login():
    with TestClient(app) as client:
        res = client.post("/api/chat", json={"message": "How is ORD-120?"})
        assert res.status_code == 401


def test_briefing_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/briefing")
        assert res.status_code == 200
        body = res.json()
        assert body["factory_today"] == "2026-04-01"
        assert body["at_risk"]["count"] == 3


def test_discovery_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/discovery?limit=5")
        assert res.status_code == 200
        body = res.json()
        assert body["factory_today"] == "2026-04-01"
        assert body["returned_count"] == 1
        assert body["total_found"] == 1
        assert body["issues"][0]["issue_id"] == "stage:ASSEMBLY"
        assert "today_priority" not in body


def test_audit_endpoint(employee_auth_headers):
    admin_auth_headers = employee_auth_headers
    with TestClient(app) as client:
        res = client.get("/api/audit", headers=admin_auth_headers)
        assert res.status_code == 200
        assert "items" in res.json()
