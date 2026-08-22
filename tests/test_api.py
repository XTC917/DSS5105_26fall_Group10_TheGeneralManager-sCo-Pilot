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


def test_chat_without_key_is_503(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import backend.main as main_mod

    monkeypatch.setattr(main_mod, "llm_is_configured", lambda: False)
    with TestClient(app) as client:
        res = client.post("/api/chat", json={"message": "How is ORD-120?"})
        assert res.status_code == 503
