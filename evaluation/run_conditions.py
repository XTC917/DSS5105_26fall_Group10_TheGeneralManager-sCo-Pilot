"""Three-condition SweaterCo evaluation.

Does nothing unless --confirm is passed. A normal invocation prints the plan
and exits before any model call, tool call, or factory-clock change.

Conditions, answering model GPT-5.6, business tools unchanged:

- baseline: semantic layer off, response templates off, few-shot off.
  Two repeats. Summary target is not set.
- exclude_exact: semantic layer on, templates on, few-shot on, the exact
  question is left out of the retrieved examples. One repeat.
  Summary >= 90% and above baseline.
- full: semantic layer on, templates on, few-shot including the exact question.
  One repeat. Summary >= 98% and above baseline.

Tool accuracy compares the agent's tool data with the data the same tool
returns in code. The target for every condition is >95%.
Each finished round is written under evaluation/results before the next round
starts. The file keeps the reply, tables, charts, tool payloads, traces, the
reference tool data, and the summary packet. --resume continues any round that
was not marked complete. --rescore reapplies the summary and tool rules to
saved rounds and does not call the model. A clarification choice is part of
the saved round; changing that choice means deleting those round files.
Shutting down this computer stops the run.

Question file default is evaluation/questions.json (106 templates). The slide's
147 reviewed questions are not a separate file in this repo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FACTORY_DAY = date(2026, 4, 1)
REPEATS = 2
TOOL_TARGET = 0.95
CONDITIONS = (
    {
        "name": "baseline",
        "env": {
            "EVAL_SEMANTIC_LAYER": "0",
            "EVAL_RESPONSE_TEMPLATES": "0",
            "EVAL_FEW_SHOT": "off",
        },
        "summary_min": None,
        "must_beat": None,
        "repeats": 2,
    },
    {
        "name": "exclude_exact",
        "env": {
            "EVAL_SEMANTIC_LAYER": "1",
            "EVAL_RESPONSE_TEMPLATES": "1",
            "EVAL_FEW_SHOT": "exclude_exact",
        },
        "summary_min": 0.90,
        "must_beat": "baseline",
        "repeats": 1,
    },
    {
        "name": "full",
        "env": {
            "EVAL_SEMANTIC_LAYER": "1",
            "EVAL_RESPONSE_TEMPLATES": "1",
            "EVAL_FEW_SHOT": "full",
        },
        "summary_min": 0.98,
        "must_beat": "baseline",
        "repeats": 1,
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the three evaluation conditions.")
    parser.add_argument("--confirm", action="store_true", help="Required. Without it, this exits.")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation" / "questions.json")
    parser.add_argument("--repeats", type=int, default=0, help="Override every condition. 0 keeps each condition's own count.")
    parser.add_argument("--workers", type=int, default=1, help="Parallel processes. 1 keeps one question at a time.")
    parser.add_argument("--only", default="", help="Comma-separated condition names. The run stops after these.")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap, for a later checked sample.")
    parser.add_argument("--minutes", type=float, default=0, help="Stop before the next round once this many minutes have passed.")
    parser.add_argument("--resume", type=Path, default=None, help="Continue a saved results directory.")
    parser.add_argument("--rescore", type=Path, default=None, help="Reapply rules to saved rounds. No model calls.")
    args = parser.parse_args()
    if args.rescore:
        return _rescore(args.rescore)
    cases = _load_cases(args.questions)
    if args.limit > 0:
        cases = cases[: args.limit]
    selected = _selected_conditions(args.only)
    if not args.confirm:
        _print_plan(cases, args.questions, selected, args.repeats)
        return 0
    answer_model = _require_answer_model()
    from backend.config import using_factory_date

    if args.resume:
        out_dir = args.resume
        if not out_dir.is_dir():
            raise SystemExit(f"No saved run at {out_dir}")
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = ROOT / "evaluation" / "results" / stamp
        out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        out_dir / "manifest.json",
        {
            "factory_date": FACTORY_DAY.isoformat(),
            "questions": [row.get("id") for row in cases],
            "repeats_by_condition": {
                item["name"]: _repeats_for(item, args.repeats) for item in selected
            },
            "conditions": [item["name"] for item in selected],
            "answering_model": answer_model,
        },
    )
    print(f"Results directory: {out_dir}")
    deadline = time.monotonic() + args.minutes * 60 if args.minutes > 0 else None
    if args.minutes > 0:
        print(f"Time budget: {args.minutes:g} minutes. Finished rounds stay in this directory.")
    total_rounds = len(cases) * sum(_repeats_for(item, args.repeats) for item in selected)
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1.")
    try:
        from backend.services.database import init_db

        init_db()
        with using_factory_date(FACTORY_DAY):
            if args.workers == 1:
                reports = [
                    _run_condition(
                        condition,
                        cases,
                        _repeats_for(condition, args.repeats),
                        out_dir,
                        deadline,
                        total_rounds,
                        tuple(item["name"] for item in selected),
                    )
                    for condition in selected
                ]
            else:
                reports = _run_parallel(
                    selected,
                    cases,
                    args.repeats,
                    out_dir,
                    args.workers,
                    deadline,
                    total_rounds,
                )
    except Exception as exc:
        _append_error(out_dir, "run", {}, 0, exc)
        print(f"Stopped: {type(exc).__name__}: {str(exc)[:300]}")
        print(f"Resume after the API is usable: .\\.venv\\Scripts\\python.exe evaluation\\run_conditions.py --confirm --resume {out_dir}")
        return 2
    summary = _rollup(reports)
    summary["stopped_early"] = any(item.get("stopped_early") for item in reports)
    _write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["stopped_early"]:
        print(f"Resume the same run: .\\.venv\\Scripts\\python.exe evaluation\\run_conditions.py --confirm --resume {out_dir}")
    return 0


def _selected_conditions(only: str) -> tuple[dict[str, Any], ...]:
    names = [item.strip() for item in only.split(",") if item.strip()]
    if not names:
        return CONDITIONS
    known = {item["name"] for item in CONDITIONS}
    missing = [name for name in names if name not in known]
    if missing:
        raise SystemExit(f"Unknown condition: {', '.join(missing)}")
    return tuple(item for item in CONDITIONS if item["name"] in names)


def _repeats_for(condition: dict[str, Any], override: int) -> int:
    if override > 0:
        return override
    return int(condition.get("repeats") or REPEATS)


def _print_plan(
    cases: list[dict[str, Any]],
    path: Path,
    selected: tuple[dict[str, Any], ...],
    override: int,
) -> None:
    print("Evaluation was not started.")
    print(f"Questions: {len(cases)} from {path}")
    rounds = sum(_repeats_for(item, override) for item in selected)
    print(f"Rounds per question in this run: {rounds}")
    print("Each round scores tool data and writes a summary packet.")
    print(f"Factory date for the run: {FACTORY_DAY.isoformat()} (restored afterwards)")
    print(f"Tool target: >{TOOL_TARGET:.0%} by comparing tool data")
    print("Summary judge: Grok subagent grok-4.7-medium-fast, skill summary-evaluation")
    print("A question counts when every saved repeat for that condition is A+ or A.")
    print("A- is recorded and not counted.")
    print("Each finished round is saved immediately. Resume with --resume <results directory>.")
    print("Reapply a changed rubric with --rescore <results directory>. That does not call the model.")
    print("This run stops if the computer shuts down.")
    for condition in selected:
        minimum = condition["summary_min"]
        bar = "no summary threshold" if minimum is None else f">={minimum:.0%} and above baseline"
        repeats = _repeats_for(condition, override)
        print(f"- {condition['name']}: {repeats} repeat(s); {bar}; env {condition['env']}")


def _require_answer_model() -> str:
    from backend.agent.graph import active_model, active_provider

    provider, model = active_provider(), str(active_model())
    allowed = model.startswith("gpt-5.6") or model == "deepseek-chat"
    if provider != "openai" or not allowed:
        raise SystemExit(
            f"Answering model is {provider}/{model}. Expected GPT-5.6 or deepseek-chat. No question was run."
        )
    return f"{provider}/{model}"


def _load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit(f"{path} has no question list.")
    return [row for row in rows if isinstance(row, dict) and str(row.get("question") or "").strip()]


def _run_condition(
    condition: dict[str, Any],
    cases: list[dict[str, Any]],
    repeats: int,
    out_dir: Path,
    deadline: float | None = None,
    total: int = 0,
    count_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    keys = {**condition["env"], "EVAL_CAPTURE_TOOL_ARGS": "1"}
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(keys)
    runs: list[dict[str, Any]] = []
    if total <= 0:
        total = len(cases) * repeats
    stopped = False
    try:
        for case in cases:
            for repeat in range(1, repeats + 1):
                path = _run_path(out_dir, condition["name"], case.get("id"), repeat)
                saved = _read_json(path)
                if saved and saved.get("complete") is True:
                    runs.append(_slim(saved))
                    continue
                if deadline is not None and time.monotonic() >= deadline:
                    print("Time budget reached. Finished rounds are kept.", flush=True)
                    stopped = True
                    break
                record = _one_run(condition["name"], case, repeat)
                if _retryable(record):
                    record["complete"] = False
                    _write_json(path, record)
                    raise RuntimeError("API credit, rate limit, or timeout. This round was not kept as finished.")
                record["complete"] = True
                _write_json(path, record)
                runs.append(_slim(record))
                names = count_names or (condition["name"],)
                saved_count = sum(len(list((out_dir / "runs" / name).glob("*.json"))) for name in names)
                print(f"saved {condition['name']} {case.get('id')} r{repeat} ({saved_count}/{total})", flush=True)
            if stopped:
                break
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    report = _condition_report(condition, runs)
    report["stopped_early"] = stopped
    return report


def _worker_init() -> None:
    from backend.services.database import init_db

    init_db()


def _process_job(job: dict[str, Any]) -> dict[str, Any]:
    os.environ.update(job["env"])
    os.environ["EVAL_CAPTURE_TOOL_ARGS"] = "1"
    from backend.config import using_factory_date

    with using_factory_date(date.fromisoformat(job["factory_date"])):
        return _one_run(job["condition"], job["case"], job["repeat"])


def _run_parallel(
    selected: tuple[dict[str, Any], ...],
    cases: list[dict[str, Any]],
    repeat_override: int,
    out_dir: Path,
    workers: int,
    deadline: float | None,
    total: int,
) -> list[dict[str, Any]]:
    """Run pending rounds in separate processes. Each process has its own agent."""
    names = tuple(item["name"] for item in selected)
    done: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
    jobs: list[dict[str, Any]] = []
    for condition in selected:
        repeats = _repeats_for(condition, repeat_override)
        env = {**condition["env"], "EVAL_CAPTURE_TOOL_ARGS": "1"}
        for case in cases:
            for repeat in range(1, repeats + 1):
                path = _run_path(out_dir, condition["name"], case.get("id"), repeat)
                saved = _read_json(path)
                if saved and saved.get("complete") is True:
                    done[condition["name"]].append(_slim(saved))
                    continue
                jobs.append(
                    {
                        "condition": condition["name"],
                        "env": env,
                        "case": case,
                        "repeat": repeat,
                        "path": str(path),
                        "factory_date": FACTORY_DAY.isoformat(),
                    }
                )
    print(f"Parallel workers: {min(workers, max(len(jobs), 1))}. Pending rounds: {len(jobs)}.", flush=True)
    stopped = False
    failure: BaseException | None = None
    if jobs:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs)), initializer=_worker_init) as pool:
            pending: dict[Any, dict[str, Any]] = {}
            upcoming = iter(jobs)

            def submit_one() -> None:
                if stopped or (deadline is not None and time.monotonic() >= deadline):
                    return
                try:
                    job = next(upcoming)
                except StopIteration:
                    return
                pending[pool.submit(_process_job, job)] = job

            for _ in range(min(workers, len(jobs))):
                submit_one()
            while pending:
                finished, _ = wait(set(pending), return_when=FIRST_COMPLETED)
                for future in finished:
                    job = pending.pop(future)
                    try:
                        record = future.result()
                    except Exception as exc:
                        _append_error(out_dir, job["condition"], job["case"], job["repeat"], exc)
                        failure = exc
                        stopped = True
                        continue
                    path = Path(job["path"])
                    if _retryable(record):
                        record["complete"] = False
                        _write_json(path, record)
                        failure = RuntimeError("API credit, rate limit, or timeout. This round was not kept as finished.")
                        stopped = True
                        continue
                    record["complete"] = True
                    _write_json(path, record)
                    done[job["condition"]].append(_slim(record))
                    saved_count = sum(len(list((out_dir / "runs" / name).glob("*.json"))) for name in names)
                    print(
                        f"saved {job['condition']} {job['case'].get('id')} r{job['repeat']} ({saved_count}/{total})",
                        flush=True,
                    )
                if deadline is not None and time.monotonic() >= deadline:
                    print("Time budget reached. Finished rounds are kept.", flush=True)
                    stopped = True
                for _ in range(len(finished)):
                    submit_one()
    if failure is not None:
        raise failure
    reports = []
    for condition in selected:
        report = _condition_report(condition, done[condition["name"]])
        report["stopped_early"] = stopped
        reports.append(report)
    return reports


def _one_run(condition: str, case: dict[str, Any], repeat: int) -> dict[str, Any]:
    from evaluation.summary_judge import judge_packet
    from evaluation.tool_compare import compare_tool_run

    question = str(case.get("question") or "")
    conversation_id = f"eval-{condition}-{case.get('id') or 'q'}-r{repeat}-{uuid.uuid4().hex[:8]}"
    parsed, body, choices, tool_source = _answer_after_clarification(question, conversation_id, case)
    tool = compare_tool_run(case, tool_source)
    packet = judge_packet(
        question=question,
        answer=body,
        reference_data=tool.get("reference_data"),
        sample_answer=str(case.get("expected_answer") or ""),
        must_include=[str(item) for item in case.get("must_include") or []],
    )
    summary = None if packet["needs_judge"] else packet["summary"]
    judge_input = None
    if packet["needs_judge"]:
        judge_input = {
            "question": packet["question"],
            "answer": packet["answer"],
            "reference_tool_json": packet["reference_tool_json"],
            "sample_answer": packet["sample_answer"],
            "must_include": packet["must_include"],
        }
    return {
        "complete": False,
        "condition": condition,
        "id": case.get("id"),
        "repeat": repeat,
        "answering_model": _require_answer_model(),
        "question": question,
        "case": {
            "relevant_tool": case.get("relevant_tool"),
            "tool_args": case.get("tool_args") if isinstance(case.get("tool_args"), dict) else {},
            "expected_answer": case.get("expected_answer") or "",
            "must_include": case.get("must_include") or [],
            "expected_behavior": case.get("expected_behavior"),
            "clarification": case.get("clarification"),
        },
        "answer": body,
        "response": _snapshot(parsed),
        "tool_response": _snapshot(tool_source),
        "clarification_choices": choices,
        "tools_used": parsed.get("tools_used") or [],
        "limitation": parsed.get("limitation"),
        "tool": tool,
        "summary": summary,
        "judge_input": judge_input,
    }


def _answer_after_clarification(
    question: str,
    conversation_id: str,
    case: dict[str, Any],
) -> tuple[dict[str, Any], str, list[Any], dict[str, Any]]:
    """Use the reply body. On a real clarification, choose the option the standard answer supports."""
    from backend.agent.graph import run_agent
    from evaluation.clarification_choice import card_body, choose_clarification, reply_body, stops_at_card

    parsed = run_agent(question, conversation_id)
    first = parsed
    choices: list[Any] = []
    for _ in range(2):
        card = parsed.get("clarification")
        if not card or stops_at_card(case):
            break
        choice = choose_clarification(card, case)
        if not choice:
            break
        choices.append(choice["picked"])
        parsed = run_agent(
            choice["text"],
            conversation_id,
            clarification_reply=True,
            original_question=question,
        )
    if stops_at_card(case) and first.get("clarification"):
        body = card_body(first["clarification"])
    else:
        body = reply_body(parsed)
    tool_source = first if str(case.get("relevant_tool") or "") == "assess_ambiguity" else parsed
    return parsed, body, choices, tool_source


def _condition_report(condition: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_question: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_question.setdefault(str(run.get("id")), []).append(run)
    counted_cases = 0
    graded_questions = 0
    for group in by_question.values():
        if not group or any(item.get("summary") is None for item in group):
            continue
        graded_questions += 1
        if all(item["summary"]["counted"] for item in group):
            counted_cases += 1
    tool_runs = [run for run in runs if run["tool"].get("scored")]
    tool_hits = sum(1 for run in tool_runs if run["tool"].get("match"))
    summary_accuracy = (
        counted_cases / graded_questions
        if graded_questions and graded_questions == len(by_question)
        else None
    )
    tool_accuracy = (tool_hits / len(tool_runs)) if tool_runs else None
    return {
        "condition": condition["name"],
        "questions": len(by_question),
        "runs": len(runs),
        "summary_accuracy": summary_accuracy,
        "summary_counted_cases": counted_cases,
        "summary_pending": len(runs) - sum(1 for run in runs if run.get("summary")),
        "summary_min": condition["summary_min"],
        "must_beat": condition["must_beat"],
        "tool_accuracy": tool_accuracy,
        "tool_hits": tool_hits,
        "tool_trials": len(tool_runs),
        "tool_target": TOOL_TARGET,
        "grades": _grade_counts(runs),
    }


def _grade_counts(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"A+": 0, "A": 0, "A-": 0, "B+": 0, "C": 0, "pending": 0}
    for run in runs:
        summary = run.get("summary")
        if not summary:
            counts["pending"] += 1
            continue
        grade = str(summary.get("grade") or "")
        if grade in counts:
            counts[grade] += 1
    return counts


def _rollup(reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {item["condition"]: item for item in reports}
    baseline = (by_name.get("baseline") or {}).get("summary_accuracy")
    checks = []
    for item in reports:
        tool = item["tool_accuracy"]
        tool_ok = tool is not None and tool > TOOL_TARGET
        summary_ok = True
        if item["summary_min"] is not None and item["summary_accuracy"] is not None:
            summary_ok = item["summary_accuracy"] >= item["summary_min"]
            if item["must_beat"] == "baseline" and baseline is not None:
                summary_ok = summary_ok and item["summary_accuracy"] > baseline
        elif item["summary_min"] is not None:
            summary_ok = False
        checks.append(
            {
                "condition": item["condition"],
                "tool_accuracy": tool,
                "tool_above_95": tool_ok,
                "summary_accuracy": item["summary_accuracy"],
                "summary_meets_slide": summary_ok,
            }
        )
    rounds = sum((item["runs"] / item["questions"]) if item["questions"] else 0 for item in reports)
    return {
        "factory_date": FACTORY_DAY.isoformat(),
        "rounds_per_question": rounds,
        "conditions": reports,
        "checks": checks,
    }


def _rescore(out_dir: Path) -> int:
    """Reapply the current summary and tool rules to saved rounds. No model calls."""
    from evaluation.clarification_choice import card_body, reply_body, stops_at_card
    from evaluation.summary_judge import judge_packet
    from evaluation.tool_compare import compare_tool_run

    if not out_dir.is_dir():
        raise SystemExit(f"No saved run at {out_dir}")
    grouped: dict[str, list[dict[str, Any]]] = {item["name"]: [] for item in CONDITIONS}
    for path in sorted((out_dir / "runs").glob("*/*.json")):
        saved = _read_json(path)
        if not saved or saved.get("complete") is not True:
            continue
        case = dict(saved.get("case") or {})
        case["question"] = saved.get("question") or ""
        source = saved.get("tool_response") or saved.get("response") or {}
        stored = None
        if (saved.get("tool") or {}).get("mode") == "data":
            stored = (saved.get("tool") or {}).get("reference_data")
        tool = compare_tool_run(case, source, stored_reference=stored)
        response = saved.get("response") or {}
        if stops_at_card(case) and response.get("clarification"):
            body = card_body(response["clarification"])
        else:
            body = reply_body({"answer": saved.get("answer") or response.get("answer") or ""})
        packet = judge_packet(
            question=str(saved.get("question") or ""),
            answer=body,
            reference_data=tool.get("reference_data"),
            sample_answer=str(case.get("expected_answer") or ""),
            must_include=[str(item) for item in case.get("must_include") or []],
        )
        saved["answer"] = body
        saved["tool"] = tool
        saved["summary"] = None if packet["needs_judge"] else packet["summary"]
        saved["judge_input"] = None
        if packet["needs_judge"]:
            saved["judge_input"] = {
                "question": packet["question"],
                "answer": packet["answer"],
                "reference_tool_json": packet["reference_tool_json"],
                "sample_answer": packet["sample_answer"],
                "must_include": packet["must_include"],
            }
        _write_json(path, saved)
        condition = str(saved.get("condition") or path.parent.name)
        if condition in grouped:
            grouped[condition].append(_slim(saved))
    reports = [
        _condition_report(condition, grouped[condition["name"]])
        for condition in CONDITIONS
        if grouped[condition["name"]]
    ]
    summary = _rollup(reports)
    _write_json(out_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _snapshot(parsed: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "answer",
        "charts",
        "tables",
        "tools_used",
        "traces",
        "evidence_results",
        "evidence_limitations",
        "clarification",
        "limitation",
        "proposed_actions",
        "email_drafts",
        "routing_intent",
    )
    return {key: parsed.get(key) for key in keys}


def _slim(record: dict[str, Any]) -> dict[str, Any]:
    tool = dict(record.get("tool") or {})
    tool.pop("reference_data", None)
    return {
        "id": record.get("id"),
        "repeat": record.get("repeat"),
        "question": record.get("question"),
        "answer": record.get("answer"),
        "summary": record.get("summary"),
        "tool": tool,
    }


def _retryable(record: dict[str, Any]) -> bool:
    text = f"{record.get('answer') or ''}\n{record.get('limitation') or ''}".casefold()
    markers = (
        "credit_balance",
        "insufficient_quota",
        "rate limit",
        "rate_limit",
        "too many requests",
        "timed out",
        "timeout",
        "overloaded",
    )
    return any(marker in text for marker in markers)


def _run_path(out_dir: Path, condition: str, case_id: Any, repeat: int) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(case_id or "question"))
    return out_dir / "runs" / condition / f"{safe}-r{repeat}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _append_error(out_dir: Path, condition: str, case: dict[str, Any], repeat: int, exc: BaseException) -> None:
    path = out_dir / "errors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "condition": condition,
            "id": case.get("id"),
            "repeat": repeat,
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        },
        ensure_ascii=False,
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


if __name__ == "__main__":
    raise SystemExit(main())
