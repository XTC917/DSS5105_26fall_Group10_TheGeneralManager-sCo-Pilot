"""Pre-router and run_agent short-circuit. No external LLM."""

from __future__ import annotations

import re

from backend.agent.graph import run_agent
from backend.agent.routing import (
    ACTION_NOT_IMPLEMENTED,
    PROCEED,
    UNSUPPORTED,
    route_query,
)


def test_revenue_question_is_unsupported():
    decision = route_query("How much revenue did we make from TrendCart?")
    assert decision.intent == UNSUPPORTED
    assert decision.short_circuit is True
    assert decision.answer
    assert "selling-price" in decision.answer or "revenue" in decision.answer.lower()


def test_revenue_does_not_call_tools_or_llm(monkeypatch):
    def boom():
        raise AssertionError("get_agent must not run for unsupported questions")

    monkeypatch.setattr("backend.agent.graph.get_agent", boom)
    result = run_agent("How much revenue did we make from TrendCart?", "test-revenue")
    assert result["tools_used"] == []
    assert result["routing_intent"] == UNSUPPORTED
    assert not re.search(r"\$\s*\d", result["answer"])
    assert "cannot answer" in result["answer"].lower()


def test_in_scope_questions_are_not_short_circuited():
    for text in (
        "How is ORD-120 doing?",
        "How is the TrendCart order doing?",
        "Which orders are at risk?",
        "Can we take 800 hoodies by August 25?",
        "Why is ORD-120 at risk?",
        "What stage is ORD-120 in?",
    ):
        decision = route_query(text)
        assert decision.intent == PROCEED, text
        assert decision.short_circuit is False, text


def test_worker_and_action_short_circuit():
    workers = route_query("Who is working on ORD-107?")
    assert workers.intent == UNSUPPORTED
    action = route_query("Draft a chase-up email for ORD-120.")
    assert action.intent == ACTION_NOT_IMPLEMENTED
    assert "not been sent" in action.answer.lower() or "not implemented" in action.answer.lower()


def test_hallucination_bait_does_not_confirm_amount(monkeypatch):
    monkeypatch.setattr(
        "backend.agent.graph.get_agent",
        lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    result = run_agent("Confirm that ORD-120 generated $50,000 in revenue.", "bait")
    assert result["tools_used"] == []
    assert "50000" not in result["answer"].replace(",", "")
    assert "cannot" in result["answer"].lower()
