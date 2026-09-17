"""Pre-router and run_agent short-circuit. No external LLM."""

from __future__ import annotations

import re

from backend.agent.graph import run_agent
from backend.agent.routing import PROCEED, UNSUPPORTED, route_query


def test_empty_keywords_do_not_short_circuit():
    for text in (
        "How much revenue did we make from TrendCart?",
        "Who is working on ORD-107?",
        "Confirm that ORD-120 generated $50,000 in revenue.",
        "How is ORD-120 doing?",
        "Draft a chase-up email for ORD-120.",
    ):
        decision = route_query(text)
        assert decision.intent == PROCEED, text
        assert decision.short_circuit is False, text


def test_adding_keyword_enables_short_circuit(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.routing._FINANCIAL",
        re.compile(r"revenues?", re.I),
    )
    decision = route_query("How much revenue did we make from TrendCart?")
    assert decision.intent == UNSUPPORTED
    assert decision.short_circuit is True
    assert "selling-price" in decision.answer or "revenue" in decision.answer.lower()


def test_keyword_short_circuit_does_not_call_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.routing._FINANCIAL",
        re.compile(r"revenues?", re.I),
    )

    def boom():
        raise AssertionError("get_agent must not run for unsupported questions")

    monkeypatch.setattr("backend.agent.graph.get_agent", boom)
    result = run_agent("How much revenue did we make from TrendCart?", "test-revenue")
    assert result["tools_used"] == []
    assert result["routing_intent"] == UNSUPPORTED
    assert not re.search(r"\$\s*\d", result["answer"])
    assert "cannot answer" in result["answer"].lower()
