"""Track 1 evaluation runner.

Two independent dimensions:

  1. Data / Tool Accuracy   (--mode tools, and also during --mode agent)
  2. Final Answer Quality   (router answers in tools mode; LLM answers in agent mode)

    python -m evaluation.run_evaluation --validate
    python -m evaluation.run_evaluation --mode tools
    python -m evaluation.run_evaluation --mode agent
    python -m evaluation.run_evaluation --dataset evaluation/questions.json --mode tools

Do not treat development-set scores as an unbiased held-out result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from backend.agent.graph import llm_is_configured, run_agent
from backend.logging_setup import setup_logging
from backend.services.database import init_db
from evaluation.answer_quality import evaluate_final_answer
from evaluation.scoring import add_case, empty_report, format_report
from evaluation.verify import check_question, load_dataset, validate_dataset

VERDICT_INDICATOR = {
    "FEASIBLE_IN_HOUSE": "feasible_in_house",
    "FEASIBLE_WITH_WORKSHOPS": "feasible_with_workshops",
    "NOT_FEASIBLE": "not_feasible",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SweaterCo Track 1 evaluation runner")
    parser.add_argument("--mode", choices=["validate", "tools", "agent"], default="tools")
    parser.add_argument("--validate", action="store_true", help="Alias for --mode validate")
    parser.add_argument("--ids", help="Comma-separated question ids to run")
    parser.add_argument(
        "--dataset",
        default=None,
        help="JSON file (default: evaluation/questions.json). Use a separate file for held-out.",
    )
    args = parser.parse_args(argv)
    if args.validate:
        args.mode = "validate"

    setup_logging()
    dataset = load_dataset(args.dataset)
    schema_errors = validate_dataset(dataset, path=args.dataset)
    if schema_errors:
        print("DATASET VALIDATION FAILED")
        for err in schema_errors:
            print(f"  - {err}")
        return 2

    questions = dataset["questions"]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        questions = [q for q in questions if q["id"] in wanted]

    usage = (dataset.get("meta") or {}).get("usage", "unknown")
    print(f"Dataset: {(dataset.get('meta') or {}).get('name')} ({usage})")
    print(f"Questions selected: {len(questions)}")
    if usage == "development":
        print("WARNING: this is a development set, not a held-out official score.")
    print()

    if args.mode == "validate":
        from evaluation.scoring import category_counts

        counts = category_counts(dataset["questions"])
        print("Category breakdown:")
        for name, n in sorted(counts.items()):
            print(f"  {name}: {n}")
        print()
        print("Dataset schema OK.")
        return 0

    init_db()

    if args.mode == "tools":
        return _run_tools(questions, usage)

    return _run_agent(questions, usage)


def _run_tools(questions: list[dict[str, Any]], usage: str) -> int:
    report = empty_report()
    rows = []
    for q in questions:
        tool_row = check_question(q)
        answer_eval = None
        if q.get("verification_method") == "deterministic_routing":
            canned = run_agent(q["question"], conversation_id=f"eval-answer-{q['id']}")
            answer_eval = evaluate_final_answer(q, canned.get("answer") or "")
            tool_selection_ok = canned.get("tools_used") == []
        else:
            tool_selection_ok = None
        add_case(
            report,
            q,
            tool_factual_ok=tool_row.get("ok"),
            tool_selection_ok=tool_selection_ok,
            answer_eval=answer_eval,
        )
        rows.append({"tool": tool_row, "answer": answer_eval})
        if not tool_row.get("ok"):
            print(f"  FAIL tool {q['id']}: {tool_row.get('detail')}")
        if answer_eval is not None and not answer_eval.get("ok"):
            print(f"  FAIL answer {q['id']}: {_answer_fail_reason(answer_eval)}")

    tool_n = report["tool_data"]["factual_tool_n"]
    tool_ok = report["tool_data"]["factual_tool_pass"]
    print(f"Deterministic tool checks: {tool_ok}/{tool_n} passed")
    print()
    print(format_report(report, usage=usage))
    _write_report("evaluation/last_tools_report.json", {"usage": usage, "rows": rows, "scores": report})
    return 0 if tool_ok == tool_n else 1


def _run_agent(questions: list[dict[str, Any]], usage: str) -> int:
    if not llm_is_configured():
        print("OPENAI_API_KEY is not set. Agent mode skipped. Tools mode still works.")
        return 3

    report = empty_report()
    rows = []
    for q in questions:
        tool_row = check_question(q)
        agent_out = run_agent(q["question"], conversation_id=f"agent-eval-{q['id']}")
        tools = agent_out.get("tools_used") or []
        tool_selection_ok = _selection_ok(q, tools)
        extras = _verdict_indicators(tool_row)
        answer_eval = evaluate_final_answer(
            q, agent_out.get("answer") or "", extra_indicate=extras
        )
        add_case(
            report,
            q,
            tool_factual_ok=tool_row.get("ok"),
            tool_selection_ok=tool_selection_ok,
            answer_eval=answer_eval,
        )
        rows.append(
            {
                "id": q["id"],
                "category": q["category"],
                "expected_behavior": q["expected_behavior"],
                "tools_used": tools,
                "tool_selection_ok": tool_selection_ok,
                "tool_factual_ok": tool_row.get("ok"),
                "answer_ok": answer_eval.get("ok"),
                "answer_eval": answer_eval,
                "routing_intent": agent_out.get("routing_intent"),
                "answer": agent_out.get("answer"),
            }
        )
        mark = "OK" if tool_selection_ok and answer_eval.get("ok") else "CHECK"
        if not tool_selection_ok:
            mark = "TOOL-MISMATCH"
        elif not answer_eval.get("ok"):
            mark = "ANSWER-FAIL"
        print(f"{mark} {q['id']} tools={tools} answer_ok={answer_eval.get('ok')}")
        print((agent_out.get("answer") or "")[:400])
        if not answer_eval.get("ok"):
            print(f"  reason: {_answer_fail_reason(answer_eval)}")
        print()

    print(format_report(report, usage=usage))
    print("No official accuracy score is claimed unless this is a held-out file and all cases ran.")
    _write_report("evaluation/last_agent_report.json", {"usage": usage, "rows": rows, "scores": report})
    return 0


def _selection_ok(question: dict[str, Any], tools: list[str]) -> bool:
    expected = question.get("expected_tools")
    forbidden = set(question.get("forbidden_tools") or [])
    if forbidden & set(tools):
        return False
    if expected is None:
        return True
    if expected == []:
        return tools == []
    return all(t in tools for t in expected)


def _verdict_indicators(tool_row: dict[str, Any]) -> list[str]:
    verdict = tool_row.get("verdict")
    label = VERDICT_INDICATOR.get(verdict) if verdict else None
    return [label] if label else []


def _answer_fail_reason(answer_eval: dict[str, Any]) -> str:
    parts = []
    for key in ("missing_facts", "missing_indicators", "missing_ids", "forbidden_hits"):
        vals = answer_eval.get(key) or []
        if vals:
            parts.append(f"{key}={vals}")
    if answer_eval.get("too_long"):
        parts.append("too_long")
    return "; ".join(parts) or "failed"


def _write_report(path: str, payload: Any) -> None:
    target = Path(path)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    sys.exit(main())
