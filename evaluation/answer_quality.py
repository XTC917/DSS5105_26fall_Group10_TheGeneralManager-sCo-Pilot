"""Deterministic final-answer checks. No LLM-as-judge.

Natural-language answers may be phrased differently, so we use:
  * case-insensitive / comma-stripped substring facts (must_contain)
  * synonym groups (must_indicate)
  * forbidden facts (must_not_contain)
  * required order ids (must_include_ids)

Criteria may be declared on the question as `answer_criteria`, or derived
from expected_result / expected_behavior so the development question file
does not have to be rewritten.
"""

from __future__ import annotations

import re
from typing import Any

INDICATORS: dict[str, tuple[str, ...]] = {
    "overdue": (r"overdue", r"past\s+due", r"past its due", r"behind (the )?due"),
    "stalled": (r"stalled", r"\bidle\b", r"no activity", r"stuck"),
    "tight_deadline": (
        r"tight\s+(deadline|delivery)",
        r"due today",
        r"insufficient (working )?days",
        r"too few (working )?days",
    ),
    "clarification": (
        r"order[_\s-]?id",
        r"which order",
        r"specify",
        r"several",
        r"multiple",
        r"more than one",
        r"ambiguous",
        r"which one",
    ),
    "limitation": (
        r"cannot answer",
        r"can't answer",
        r"not (in|present in|provided|available)",
        r"no selling[- ]price",
        r"no revenue",
        r"no worker",
        r"dataset does not",
        r"available factory data",
        r"will not invent",
    ),
    "not_implemented": (
        r"not implemented",
        r"cannot do that yet",
        r"not (wired|available) yet",
        r"nothing has been sent",
    ),
    "heuristic": (
        r"heuristic",
        r"under this model",
        r"\bestimate",
        r"not a (guarantee|promise)",
        r"planning estimate",
        r"capacity check",
    ),
    "not_found": (r"not (in|found)", r"no order matches", r"does not exist", r"unknown order"),
    "not_at_risk": (r"not at risk", r"no risk flag", r"not overdue", r"not flagged", r"\bno\b.*\brisk"),
    "feasible_in_house": (r"feasible in[- ]house", r"in-house"),
    "feasible_with_workshops": (r"with workshops?", r"workshop overflow", r"outside workshop"),
    "not_feasible": (r"not feasible", r"cannot take", r"before factory today", r"due date is already"),
}

UNSUPPORTED_CATEGORIES = {"unanswerable", "hallucination_bait"}
ACTION_CATEGORIES = {"action"}


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", (text or "").lower()).strip()
    return collapsed.replace(",", "")


def contains_fact(answer: str, fact: str) -> bool:
    """True if the fact appears, allowing 1,500 vs 1500 and extra spaces."""
    hay = normalize_text(answer)
    needle = normalize_text(fact)
    if not needle:
        return True

    def _hit(h: str, n: str) -> bool:
        if " " in n:
            return all(tok in h for tok in n.split() if tok)
        if n.isdigit():
            return re.search(rf"(?<!\d){re.escape(n)}(?!\d)", h) is not None
        return n in h

    if _hit(hay, needle):
        return True
    return _hit(hay.replace("-", " "), needle.replace("-", " "))


def indicates(answer: str, label: str) -> bool:
    patterns = INDICATORS.get(label)
    if not patterns:
        return contains_fact(answer, label)
    text = answer or ""
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def derive_criteria(question: dict[str, Any]) -> dict[str, Any]:
    """Build lightweight answer checks from the existing gold fields."""
    expected = question.get("expected_result") or {}
    behavior = question.get("expected_behavior")
    category = question.get("category")
    must_contain: list[str] = []
    must_indicate: list[str] = []
    must_not_contain: list[str] = []
    must_include_ids: list[str] = []

    for key in ("order_id", "customer", "product", "current_stage", "due_date", "last_activity_date"):
        value = expected.get(key)
        if value:
            must_contain.append(str(value))
    if expected.get("pieces") is not None:
        must_contain.append(str(expected["pieces"]))

    for flag, label in (
        ("OVERDUE", "overdue"),
        ("STALLED", "stalled"),
        ("TIGHT_DEADLINE", "tight_deadline"),
    ):
        if flag in (expected.get("risk_flags") or []):
            must_indicate.append(label)

    order_ids = expected.get("order_ids") or []
    if order_ids:
        must_contain.append(str(len(order_ids)))
        must_include_ids = list(order_ids)
        kinds = set()
        for flags in (expected.get("flag_map") or {}).values():
            kinds.update(flags)
        if "OVERDUE" in kinds:
            must_indicate.append("overdue")
        if "STALLED" in kinds:
            must_indicate.append("stalled")
        if "TIGHT_DEADLINE" in kinds:
            must_indicate.append("tight_deadline")

    if expected.get("is_overdue"):
        must_indicate.append("overdue")
    if expected.get("risk_flags") == []:
        must_indicate.append("not_at_risk")

    if behavior == "ask_clarification":
        must_indicate.append("clarification")
    if behavior == "decline":
        must_indicate.append("limitation")
    if behavior == "not_implemented":
        must_indicate.append("not_implemented")
    if expected.get("error_code") == "NOT_FOUND":
        must_indicate.append("not_found")
    if category == "feasibility":
        must_indicate.append("heuristic")
    if expected.get("must_include_limitations"):
        must_indicate.append("heuristic")

    for token in expected.get("must_mention") or []:
        must_contain.append(str(token))

    amount = expected.get("must_not_confirm_amount")
    if amount:
        must_not_contain.append(str(amount))
    if expected.get("must_not_match_currency"):
        must_not_contain.extend(["$", "SGD"])

    # Unique, keep order.
    def _uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out

    return {
        "must_contain": _uniq(must_contain),
        "must_indicate": _uniq(must_indicate),
        "must_not_contain": _uniq(must_not_contain),
        "must_include_ids": must_include_ids,
        "max_chars": 4000,
        "derived": True,
    }


def merge_criteria(question: dict[str, Any]) -> dict[str, Any]:
    derived = derive_criteria(question)
    declared = question.get("answer_criteria")
    if isinstance(question.get("expected_answer"), dict) and not declared:
        declared = question["expected_answer"]
    if not declared:
        return derived
    merged = dict(derived)
    merged["derived"] = False
    for key in ("must_contain", "must_indicate", "must_not_contain", "must_include_ids"):
        if key in declared and declared[key] is not None:
            merged[key] = list(declared[key])
    if declared.get("max_chars"):
        merged["max_chars"] = declared["max_chars"]
    return merged


def evaluate_final_answer(
    question: dict[str, Any],
    answer: str,
    *,
    extra_indicate: list[str] | None = None,
) -> dict[str, Any]:
    """Score one natural-language answer. Extra indicators come from live tools."""
    criteria = merge_criteria(question)
    if extra_indicate:
        for label in extra_indicate:
            if label not in criteria["must_indicate"]:
                criteria["must_indicate"].append(label)

    missing_facts: list[str] = []
    missing_indicators: list[str] = []
    forbidden_hits: list[str] = []
    missing_ids: list[str] = []

    for fact in criteria.get("must_contain") or []:
        if not contains_fact(answer, fact):
            missing_facts.append(fact)
    for label in criteria.get("must_indicate") or []:
        if not indicates(answer, label):
            missing_indicators.append(label)
    for fact in criteria.get("must_not_contain") or []:
        if fact == "$":
            if re.search(r"\$\s*\d", answer or ""):
                forbidden_hits.append(fact)
            continue
        if contains_fact(answer, fact) and not indicates(answer, "limitation"):
            forbidden_hits.append(fact)
    for order_id in criteria.get("must_include_ids") or []:
        if not contains_fact(answer, order_id):
            missing_ids.append(order_id)

    too_long = False
    max_chars = criteria.get("max_chars")
    if max_chars and len(answer or "") > int(max_chars):
        too_long = True

    completeness_ok = not missing_ids
    factual_ok = not missing_facts and not missing_indicators and not forbidden_hits
    ok = factual_ok and completeness_ok and not too_long
    return {
        "id": question.get("id"),
        "ok": ok,
        "factual_ok": factual_ok,
        "completeness_ok": completeness_ok,
        "too_long": too_long,
        "missing_facts": missing_facts,
        "missing_indicators": missing_indicators,
        "forbidden_hits": forbidden_hits,
        "missing_ids": missing_ids,
        "criteria": {k: criteria[k] for k in ("must_contain", "must_indicate", "must_not_contain", "must_include_ids")},
    }
