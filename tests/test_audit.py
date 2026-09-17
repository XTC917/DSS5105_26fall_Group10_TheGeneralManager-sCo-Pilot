"""Lightweight audit log. No LLM required."""

from __future__ import annotations

from backend.agent.graph import run_agent
from backend.services.audit import list_audit


def test_short_circuit_writes_audit_row(db, clean_state, monkeypatch):
    import re

    monkeypatch.setattr(
        "backend.agent.routing._FINANCIAL",
        re.compile(r"revenues?", re.I),
    )
    result = run_agent("How much revenue did we make from TrendCart?", "audit-rev")
    assert result["tools_used"] == []
    rows = list_audit(limit=10)
    assert rows
    latest = rows[0]
    assert latest["event_type"] == "short_circuit"
    assert "revenue" in (latest["user_query"] or "").lower()
    assert latest["execution_status"] == "no_tool"
    assert str(latest["factory_today"]) == "2026-04-01"
