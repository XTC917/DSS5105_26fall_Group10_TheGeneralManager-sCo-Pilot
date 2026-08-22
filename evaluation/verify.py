"""Deterministic checks against CSVs and Python tools. No LLM required."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.agent.graph import run_agent
from backend.agent.routing import route_query
from backend.services.calculations import assess_order_risk
from backend.services.database import get_db
from backend.services.feasibility import check_feasibility as run_feasibility
from backend.tools.retrieval import get_order_status, get_orders_at_risk
from backend.tools.tracing import trace_order
from evaluation.schema import (
    AMBIGUOUS_UNANSWERABLE_BAIT,
    ANSWER_CRITERIA_KEYS,
    BEHAVIORS,
    CATEGORIES,
    FEASIBILITY_ACTION,
    MIN_AMBIGUOUS_UNANSWERABLE_BAIT,
    MIN_FEASIBILITY_ACTION,
    MIN_QUESTIONS,
    REQUIRED_QUESTION_FIELDS,
)

QUESTIONS_PATH = Path(__file__).resolve().parent / "questions.json"
DEVELOPMENT_REQUIRED_TEXTS = {
    "Q001": "How is ORD-120 doing?",
    "Q002": "How is the TrendCart order doing?",
    "Q003": "Which orders are at risk?",
    "Q004": "Can we take 800 hoodies by August 25?",
    "Q005": "How much revenue did we make from TrendCart?",
}


def load_dataset(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else QUESTIONS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def parse_tool(raw: str) -> dict[str, Any]:
    return json.loads(raw)


def validate_dataset(
    dataset: dict[str, Any] | None = None,
    *,
    path: str | Path | None = None,
) -> list[str]:
    data = dataset or load_dataset(path)
    source = Path(path) if path else QUESTIONS_PATH
    errors: list[str] = []
    meta = data.get("meta") or {}
    usage = meta.get("usage")
    if usage not in {"development", "held-out"}:
        errors.append("meta.usage must be 'development' or 'held-out'")
    is_default_dev = source.resolve() == QUESTIONS_PATH.resolve()
    if is_default_dev and usage != "development":
        errors.append("evaluation/questions.json must keep meta.usage = 'development'")
    questions = data.get("questions") or []
    if usage == "development" and len(questions) < MIN_QUESTIONS:
        errors.append(f"need at least {MIN_QUESTIONS} questions, found {len(questions)}")
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        errors.append("duplicate question ids")
    bait = sum(1 for q in questions if q.get("category") in AMBIGUOUS_UNANSWERABLE_BAIT)
    feas = sum(1 for q in questions if q.get("category") in FEASIBILITY_ACTION)
    if usage == "development":
        if bait < MIN_AMBIGUOUS_UNANSWERABLE_BAIT:
            errors.append(
                f"need >= {MIN_AMBIGUOUS_UNANSWERABLE_BAIT} ambiguous/unanswerable/bait, found {bait}"
            )
        if feas < MIN_FEASIBILITY_ACTION:
            errors.append(f"need >= {MIN_FEASIBILITY_ACTION} feasibility/action, found {feas}")
    for q in questions:
        qid = q.get("id", "?")
        missing = [f for f in REQUIRED_QUESTION_FIELDS if f not in q]
        if missing:
            errors.append(f"{qid} missing fields: {missing}")
        if q.get("category") not in CATEGORIES:
            errors.append(f"{qid} bad category {q.get('category')}")
        if q.get("expected_behavior") not in BEHAVIORS:
            errors.append(f"{qid} bad expected_behavior {q.get('expected_behavior')}")
        criteria = q.get("answer_criteria")
        if isinstance(q.get("expected_answer"), dict):
            criteria = criteria or q.get("expected_answer")
        if criteria is not None:
            if not isinstance(criteria, dict):
                errors.append(f"{qid} answer_criteria must be an object")
            else:
                unknown = set(criteria) - ANSWER_CRITERIA_KEYS
                if unknown:
                    errors.append(f"{qid} unknown answer_criteria keys: {sorted(unknown)}")
    if is_default_dev:
        present = {q.get("id") for q in questions}
        required_ids = set(DEVELOPMENT_REQUIRED_TEXTS)
        if not required_ids <= present:
            errors.append(f"missing required course cases: {sorted(required_ids - present)}")
        texts = {q["id"]: q.get("question") for q in questions if q.get("id") in required_ids}
        for qid, text in DEVELOPMENT_REQUIRED_TEXTS.items():
            if texts.get(qid) != text:
                errors.append(f"{qid} question text must be exact: {text!r}")
    return errors


def live_risk_set(flag: str | None = None) -> dict[str, list[str]]:
    db = get_db()
    out: dict[str, list[str]] = {}
    for order in db.in_progress_orders():
        risk = assess_order_risk(order)
        if not risk["at_risk"]:
            continue
        if flag and flag not in risk["flags"]:
            continue
        out[order["order_id"]] = list(risk["flags"])
    return out


def check_question(question: dict[str, Any]) -> dict[str, Any]:
    method = question["verification_method"]
    handlers = {
        "deterministic_order_status": _check_order_status,
        "deterministic_ambiguous": _check_ambiguous,
        "deterministic_not_found": _check_not_found,
        "deterministic_risk_set": _check_risk_set,
        "deterministic_risk_flag_filter": _check_risk_flag_filter,
        "deterministic_trace": _check_trace,
        "deterministic_feasibility": _check_feasibility,
        "deterministic_routing": _check_routing,
    }
    handler = handlers.get(method)
    if handler is None:
        return {"id": question["id"], "ok": False, "detail": f"unknown method {method}"}
    try:
        return handler(question)
    except Exception as exc:  # noqa: BLE001
        return {"id": question["id"], "ok": False, "detail": f"exception: {exc}"}


def _check_order_status(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    order_id = expected["order_id"]
    payload = parse_tool(get_order_status.invoke({"order_id": order_id}))
    if not payload.get("ok"):
        return {"id": question["id"], "ok": False, "detail": payload}
    order = payload["data"]["order"]
    risk = assess_order_risk(order)
    mismatches: list[str] = []
    for key in (
        "customer",
        "product",
        "pieces",
        "status",
        "current_stage",
        "due_date",
        "last_activity_date",
        "completed_date",
    ):
        if key in expected and order.get(key) != expected[key]:
            mismatches.append(f"{key}: got {order.get(key)!r} expected {expected[key]!r}")
    if "risk_flags" in expected and risk["flags"] != expected["risk_flags"]:
        mismatches.append(f"flags: got {risk['flags']} expected {expected['risk_flags']}")
    if expected.get("is_overdue") is True and "OVERDUE" not in risk["flags"]:
        mismatches.append("expected OVERDUE")
    return {"id": question["id"], "ok": not mismatches, "detail": mismatches or "ok"}


def _check_ambiguous(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    args = {k: expected[k] for k in ("customer", "product") if k in expected}
    payload = parse_tool(get_order_status.invoke(args))
    err = payload.get("error") or {}
    ok = (
        payload.get("ok") is False
        and err.get("code") == expected.get("error_code", "AMBIGUOUS")
        and len(err.get("candidates") or []) >= expected.get("min_candidates", 2)
    )
    return {"id": question["id"], "ok": ok, "detail": err.get("code")}


def _check_not_found(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    payload = parse_tool(get_order_status.invoke({"order_id": expected["order_id"]}))
    ok = payload.get("ok") is False and (payload.get("error") or {}).get("code") == "NOT_FOUND"
    return {"id": question["id"], "ok": ok, "detail": payload.get("error")}


def _check_risk_set(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    live = live_risk_set()
    expected_ids = set(expected["order_ids"])
    mismatches: list[str] = []
    if set(live) != expected_ids:
        mismatches.append(f"ids live={sorted(live)} expected={sorted(expected_ids)}")
    flag_map = expected.get("flag_map") or {}
    for oid, flags in flag_map.items():
        if live.get(oid) != flags:
            mismatches.append(f"{oid} flags live={live.get(oid)} expected={flags}")
    payload = parse_tool(get_orders_at_risk.invoke({}))
    tool_ids = {row["order_id"] for row in payload["data"]["orders"]}
    if tool_ids != expected_ids:
        mismatches.append("tool output diverged from live_risk_set")
    return {"id": question["id"], "ok": not mismatches, "detail": mismatches or "ok"}


def _check_risk_flag_filter(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    flag = expected["flag_filter"]
    live = live_risk_set(flag)
    ok = set(live) == set(expected["order_ids"])
    return {"id": question["id"], "ok": ok, "detail": sorted(live)}


def _check_trace(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    payload = parse_tool(trace_order.invoke({"order_id": expected["order_id"]}))
    if not payload.get("ok"):
        return {"id": question["id"], "ok": False, "detail": payload}
    flags = payload["data"]["risk"]["flags"]
    source = payload["trace"]["source_file"]
    order = payload["data"]["order"]
    mismatches: list[str] = []
    if flags != expected["risk_flags"]:
        mismatches.append(f"flags {flags}")
    if source != expected.get("source_file", "orders.csv"):
        mismatches.append(f"source {source}")
    for key in ("due_date", "last_activity_date"):
        if key in expected and order.get(key) != expected[key]:
            mismatches.append(f"{key} {order.get(key)}")
    return {"id": question["id"], "ok": not mismatches, "detail": mismatches or "ok"}


def _check_feasibility(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    db = get_db()
    result = run_feasibility(
        db,
        pieces=expected["pieces"],
        due_date=expected["due_date"],
        product=expected.get("product"),
        category=expected.get("category"),
    )
    if not result.get("ok"):
        return {"id": question["id"], "ok": False, "detail": result}
    data = result["data"]
    mismatches: list[str] = []
    if data["verdict"] not in expected["allowed_verdicts"]:
        mismatches.append(f"verdict {data['verdict']}")
    if expected.get("category") and data.get("category") != expected["category"]:
        mismatches.append(f"category {data.get('category')}")
    if expected.get("must_include_limitations") and not data.get("limitations"):
        mismatches.append("missing limitations")
    return {
        "id": question["id"],
        "ok": not mismatches,
        "detail": mismatches or data["verdict"],
        "verdict": data["verdict"],
    }


def _check_routing(question: dict[str, Any]) -> dict[str, Any]:
    expected = question["expected_result"]
    result = run_agent(question["question"], conversation_id=f"eval-{question['id']}")
    mismatches: list[str] = []
    if result.get("tools_used"):
        mismatches.append(f"unexpected tools {result['tools_used']}")
    for tool in question.get("forbidden_tools") or []:
        if tool in (result.get("tools_used") or []):
            mismatches.append(f"forbidden tool {tool}")
    if expected.get("routing_intent") and result.get("routing_intent") != expected["routing_intent"]:
        mismatches.append(f"intent {result.get('routing_intent')}")
    answer = (result.get("answer") or "").lower()
    for token in expected.get("must_mention") or []:
        if token.lower() not in answer and token.lower() not in (result.get("limitation") or "").lower():
            # Financial canned text uses hyphenated selling-price.
            if token.lower().replace("-", " ") not in answer.replace("-", " "):
                mismatches.append(f"missing mention {token}")
    if expected.get("must_not_match_currency"):
        if re.search(r"\$\s*\d|\bSGD\b|\brevenue is \d", result.get("answer") or "", re.I):
            mismatches.append("looks like a fabricated money amount")
    if expected.get("must_not_confirm_amount"):
        amount = expected["must_not_confirm_amount"]
        if amount in (result.get("answer") or "") and "cannot" not in answer:
            mismatches.append("confirmed bait amount")
    decision = route_query(question["question"])
    if not decision.short_circuit:
        mismatches.append("router did not short-circuit")
    return {"id": question["id"], "ok": not mismatches, "detail": mismatches or result.get("routing_intent")}
