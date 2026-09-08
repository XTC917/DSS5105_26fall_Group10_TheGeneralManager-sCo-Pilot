"""Final-answer quality checks. No LLM required."""

from __future__ import annotations

from evaluation.answer_quality import evaluate_final_answer
from evaluation.verify import load_dataset


def _q(qid: str) -> dict:
    data = load_dataset()
    return next(q for q in data["questions"] if q["id"] == qid)


def test_risk_wrong_count_fails_even_if_tools_were_right():
    question = _q("Q003")
    good = (
        "10 orders need attention. Categories: overdue 8, stalled 2, "
        "tight deadline 1. Orders: ORD-002, ORD-005, ORD-020, ORD-029, "
        "ORD-055, ORD-083, ORD-093, ORD-107, ORD-114, ORD-120."
    )
    bad = "There are 8 orders at risk."
    assert evaluate_final_answer(question, good)["ok"] is True
    failed = evaluate_final_answer(question, bad)
    assert failed["ok"] is False
    assert "10" in failed["missing_facts"] or failed["missing_ids"]


def test_ord120_requires_core_facts():
    question = _q("Q001")
    good = (
        "ORD-120 is a TrendCart Vest, 1,500 pieces, IN_PROGRESS in ASSEMBLY, "
        "due 2026-03-17, last activity 2026-03-30. It is overdue."
    )
    missing_stage = (
        "ORD-120 TrendCart Vest 1500 pieces due 2026-03-17 last activity 2026-03-30 overdue"
    )
    assert evaluate_final_answer(question, good)["ok"] is True
    bad = evaluate_final_answer(question, missing_stage)
    assert bad["ok"] is False
    assert "ASSEMBLY" in bad["missing_facts"]


def test_revenue_answer_rejects_invented_money():
    question = _q("Q005")
    good = (
        "I cannot answer that from the available factory data because no "
        "selling-price or revenue field is provided."
    )
    bad = "TrendCart revenue was $12000 this quarter."
    assert evaluate_final_answer(question, good)["ok"] is True
    assert evaluate_final_answer(question, bad)["ok"] is False


def test_declared_answer_criteria_override():
    question = {
        "id": "QX",
        "expected_behavior": "answer",
        "category": "normal_lookup",
        "expected_result": {"order_id": "ORD-001"},
        "answer_criteria": {
            "must_contain": ["hello"],
            "must_indicate": [],
            "must_not_contain": [],
            "must_include_ids": [],
        },
    }
    assert evaluate_final_answer(question, "hello there")["ok"] is True
    assert evaluate_final_answer(question, "ORD-001 is fine")["ok"] is False
