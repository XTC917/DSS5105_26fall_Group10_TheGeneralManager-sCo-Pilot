"""Separate scores for tool/data accuracy vs final-answer quality."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evaluation.answer_quality import ACTION_CATEGORIES, UNSUPPORTED_CATEGORIES


def empty_report() -> dict[str, Any]:
    return {
        "n": 0,
        "tool_data": {
            "factual_tool_pass": 0,
            "factual_tool_n": 0,
            "tool_selection_pass": 0,
            "tool_selection_n": 0,
            "unsupported_handling_pass": 0,
            "unsupported_handling_n": 0,
        },
        "final_answer": {
            "pass": 0,
            "n": 0,
            "factual_coverage_pass": 0,
            "completeness_pass": 0,
        },
        "by_category": {},
    }


def add_case(
    report: dict[str, Any],
    question: dict[str, Any],
    *,
    tool_factual_ok: bool | None = None,
    tool_selection_ok: bool | None = None,
    answer_eval: dict[str, Any] | None = None,
) -> None:
    report["n"] += 1
    td = report["tool_data"]
    fa = report["final_answer"]
    category = question.get("category") or "unknown"
    bucket = report["by_category"].setdefault(
        category,
        {"n": 0, "tool_pass": 0, "tool_n": 0, "answer_pass": 0, "answer_n": 0},
    )
    bucket["n"] += 1

    if tool_factual_ok is not None:
        td["factual_tool_n"] += 1
        bucket["tool_n"] += 1
        if tool_factual_ok:
            td["factual_tool_pass"] += 1
            bucket["tool_pass"] += 1

    if tool_selection_ok is not None:
        td["tool_selection_n"] += 1
        if tool_selection_ok:
            td["tool_selection_pass"] += 1
        if question.get("category") in UNSUPPORTED_CATEGORIES | ACTION_CATEGORIES:
            td["unsupported_handling_n"] += 1
            if tool_selection_ok:
                td["unsupported_handling_pass"] += 1

    if answer_eval is not None:
        fa["n"] += 1
        bucket["answer_n"] += 1
        if answer_eval.get("ok"):
            fa["pass"] += 1
            bucket["answer_pass"] += 1
        if answer_eval.get("factual_ok"):
            fa["factual_coverage_pass"] += 1
        if answer_eval.get("completeness_ok"):
            fa["completeness_pass"] += 1


def _pct(passed: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{passed}/{total} ({100.0 * passed / total:.1f}%)"


def format_report(report: dict[str, Any], *, usage: str) -> str:
    td = report["tool_data"]
    fa = report["final_answer"]
    lines = [
        "=== Evaluation scores (separate dimensions) ===",
        f"Set usage: {usage}  — not an unbiased held-out official score."
        if usage == "development"
        else f"Set usage: {usage}",
        "",
        "1. Data / Tool Accuracy",
        f"   Factual tool result:     {_pct(td['factual_tool_pass'], td['factual_tool_n'])}",
        f"   Tool selection:          {_pct(td['tool_selection_pass'], td['tool_selection_n'])}",
        f"   Unsupported / no-tool:   {_pct(td['unsupported_handling_pass'], td['unsupported_handling_n'])}",
        "",
        "2. Final Answer / Summary Quality",
        f"   Answer pass:             {_pct(fa['pass'], fa['n'])}",
        f"   Required-fact coverage:  {_pct(fa['factual_coverage_pass'], fa['n'])}",
        f"   Completeness (ids/list): {_pct(fa['completeness_pass'], fa['n'])}",
        "",
        "These two dimensions are not averaged into one official score.",
        "",
        "By category:",
    ]
    for name, bucket in sorted(report["by_category"].items()):
        lines.append(
            f"   {name}: n={bucket['n']} "
            f"tool={bucket['tool_pass']}/{bucket['tool_n']} "
            f"answer={bucket['answer_pass']}/{bucket['answer_n']}"
        )
    return "\n".join(lines)


def category_counts(questions: list[dict[str, Any]]) -> Counter:
    return Counter(q.get("category") for q in questions)
