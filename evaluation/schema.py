"""Contract for evaluation/questions.json."""

from __future__ import annotations

REQUIRED_QUESTION_FIELDS = (
    "id",
    "question",
    "category",
    "expected_behavior",
    "expected_answer",
    "verification_method",
    "relevant_tool",
    "notes",
)

CATEGORIES = {
    "normal_lookup",
    "risk_retrieval",
    "judgement",
    "traceability",
    "ambiguous",
    "unanswerable",
    "hallucination_bait",
    "feasibility",
    "action",
}

BEHAVIORS = {
    "answer",
    "ask_clarification",
    "decline",
    "not_implemented",
}

ANSWER_CRITERIA_KEYS = {
    "must_contain",
    "must_indicate",
    "must_not_contain",
    "must_include_ids",
    "max_chars",
}

# Optional per-question: answer_criteria (object). expected_answer may stay a
# prose string for humans. Held-out files use the same schema with
# meta.usage = "held-out".


MIN_QUESTIONS = 30
MIN_AMBIGUOUS_UNANSWERABLE_BAIT = 5
MIN_FEASIBILITY_ACTION = 5

AMBIGUOUS_UNANSWERABLE_BAIT = {"ambiguous", "unanswerable", "hallucination_bait"}
FEASIBILITY_ACTION = {"feasibility", "action"}
