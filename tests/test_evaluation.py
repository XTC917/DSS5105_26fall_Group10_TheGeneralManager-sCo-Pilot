"""Evaluation dataset contract + deterministic gold checks."""

from __future__ import annotations

from evaluation.schema import MIN_QUESTIONS
from evaluation.verify import check_question, load_dataset, validate_dataset


def test_dataset_meets_course_minimums():
    errors = validate_dataset()
    assert errors == [], errors
    data = load_dataset()
    assert len(data["questions"]) >= MIN_QUESTIONS
    assert data["meta"]["usage"] == "development"


def test_required_course_questions_present():
    data = load_dataset()
    by_id = {q["id"]: q for q in data["questions"]}
    assert by_id["Q001"]["question"] == "How is ORD-120 doing?"
    assert by_id["Q002"]["question"] == "How is the TrendCart order doing?"
    assert by_id["Q003"]["question"] == "Which orders are at risk?"
    assert by_id["Q004"]["question"] == "Can we take 800 hoodies by August 25?"
    assert by_id["Q005"]["question"] == "How much revenue did we make from TrendCart?"


def test_all_deterministic_cases(db):
    data = load_dataset()
    failed = []
    for question in data["questions"]:
        result = check_question(question)
        if not result["ok"]:
            failed.append(result)
    assert failed == [], failed
