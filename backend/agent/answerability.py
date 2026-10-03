"""Clarification, then two gated LLM steps.

Clarification only asks whether the question has more than one answer.
It does not check stored columns and it does not intercept.
If the question has one answer, stored-data then tool-coverage may still stop it.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from backend.agent.prompts import TOOL_LOOKUP_TABLE
from backend.services.semantic import load_semantic_layer, render_semantic_prompt

logger = logging.getLogger(__name__)

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

_DATA_SYSTEM = """You only decide whether the manager's question needs a stored factory field.

Reply with one JSON object, no markdown:
{"kind":"fact"|"action"|"follow_up","stored":true|false,"table":string|null,"column":string|null,"reason":string}

kind=action: email, note, reminder, watch, or audit. Then stored=true, table=null, column=null.
kind=follow_up: the question asks how a figure already present in Previous tool JSON was calculated. Then stored=true, table=null, column=null. If there is no Previous tool JSON, do not use follow_up.
If Previous tool JSON listed rows and the new question asks a further fact about those same rows, kind=fact and stored=true. Name the column for the new fact. Do not use follow_up.
kind=fact: pick table and column from the semantic layer only.
A question about an order, a customer, or a product already in the tables is stored=true.
Use orders.order_id, orders.customer, orders.product, or orders.status. "How is it doing" is that row's status.
stored=true only if that column exists (or an equivalent stored column).
stored=false only when no table holds the fact (revenue, selling price, and terms marked not a stored column).
reason: one or two sentences in the same language as the manager.
Do not invent numbers. Do not add names the manager did not write.
"""

_AMBIGUITY_SYSTEM = """You only decide whether the manager's question has one answer or several.

Do not decide whether a field is stored. Do not refuse, and do not say data is missing.

Reply with one JSON object, no markdown:
{"ambiguous":true|false,"readings":[{"tool":string,"label":string,"message":string}],"reason":string}

ambiguous=false when one answer method fits. readings has that one object.
ambiguous=true when more than one answer method fits. readings has one object per method.
One row and the list of those same rows are one method: name only one tool.
A further fact about rows already in Previous tool JSON is one method when the question asks that fact.
label: a short button about the subject they actually named.
message: the full next question, asking only that answer about the same subject.
Do not swap in a generic customer, product, stage, or example question.
reason: one or two sentences.
Do not invent numbers. Do not add names the manager did not write.
The language rule in the user message overrides every other language. Do not translate into French or Spanish.
"""

_TOOL_SYSTEM = """You only decide whether this question needs a tool, then whether that tool exists.

Reply with one JSON object, no markdown:
{"needs_tool":true|false,"has_tool":true|false,"tool":string|null,"reason":string}

needs_tool=false when Previous tool JSON already has the facts and this question only changes how to say them, such as language or a shorter wording. Then has_tool=false and tool=null.
needs_tool=true when a new fact must be looked up or computed.
When needs_tool is true, has_tool=true only if a registered tool returns that fact. Otherwise has_tool=false and tool=null.
A tool that merely mentions another table as a side effect does not count.
If kind is action, needs_tool=true and pick the matching action tool.
reason: one or two sentences in the manager's language. Do not translate.
Do not invent numbers. Do not add names the manager did not write.
"""


@dataclass
class DataVerdict:
    kind: str = "fact"
    stored: bool = False
    table: str | None = None
    column: str | None = None
    reason: str = ""


@dataclass
class ToolVerdict:
    has_tool: bool = False
    tool: str | None = None
    reason: str = ""
    needs_tool: bool = True
    readings: list[str] = field(default_factory=list)
    options: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AnswerabilityGate:
    proceed: bool
    data: DataVerdict
    tools: ToolVerdict
    answer: str | None = None
    limitation: str | None = None
    traces: list[dict[str, Any]] = field(default_factory=list)
    clarification: dict[str, Any] | None = None
    explain_prior: bool = False
    reuse_prior: bool = False


_HAN = re.compile(r"[\u4e00-\u9fff]")

SCOPE_OPTIONS = {
    "zh": (
        {"label": "订单", "message": "订单的状态和交期怎么样？"},
        {"label": "产量", "message": "各阶段完成件数怎么样？"},
        {"label": "车间产能", "message": "车间每天的产能怎么样？"},
    ),
    "en": (
        {"label": "Orders", "message": "How are order status and due dates?"},
        {"label": "Output", "message": "How many pieces were completed at each stage?"},
        {"label": "Workshop capacity", "message": "What is each workshop's daily capacity?"},
    ),
}

_OTHER_UI = {
    "zh": {"other_placeholder": "其他", "other_submit": "发送"},
    "en": {"other_placeholder": "Other", "other_submit": "Send"},
}

_SCOPE_PROMPT = {
    "zh": "这句话对不上工厂表里的字段。要查哪一块？",
    "en": "That is not in the factory tables. Which of these should I look at?",
}

# Tools that describe the same fact. One row versus the list of those rows is one answer.
_ONE_ANSWER = (frozenset({"get_order_status", "find_orders"}),)


def language_rule(question: str) -> str:
    """Name the language. 'Same language as the manager' is not enough; models drift."""
    if reply_language(question) == "zh":
        return "Manager language: Chinese. label, message, and reason must be Chinese."
    return (
        "Manager language: English. label, message, and reason must be English. "
        "Do not reply in French, Spanish, or any other language."
    )


def reply_language(text: str) -> str:
    """Chinese when the manager wrote Han characters; otherwise English."""
    return "zh" if _HAN.search(text or "") else "en"


def attach_other(card: dict[str, Any], text: str) -> dict[str, Any]:
    """Every clarification card has a free-text box. Language follows the manager."""
    lang = reply_language(text)
    card["other_placeholder"] = _OTHER_UI[lang]["other_placeholder"]
    card["other_submit"] = _OTHER_UI[lang]["other_submit"]
    return card


def _answer_key(tool: str) -> str:
    for group in _ONE_ANSWER:
        if tool in group:
            return min(group)
    return tool


def interpretation_clarification(
    question: str,
    options: list[dict[str, str]] | tuple[dict[str, str], ...],
    ask: str = "",
) -> dict[str, Any] | None:
    """Show the model's own wording for each different answer.

    Several matching rows are not an interpretation. One order and the list of
    those same rows stay one option. Button text is not replaced with a template.
    """
    kept: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in options:
        tool = str(row.get("tool") or "").strip()
        label = str(row.get("label") or "").strip()
        message = str(row.get("message") or "").strip()
        if not tool or not label or not message:
            continue
        key = _answer_key(tool)
        if key in seen:
            continue
        seen.add(key)
        kept.append({"label": label, "message": message})
    if len(kept) < 2:
        return None
    return attach_other(
        {"prompt": (ask or "").strip() or "Which of these did you mean?", "options": kept},
        question,
    )


def scope_clarification(reason: str, question: str = "") -> dict[str, Any]:
    """Out-of-table questions: ask which real scope to use, in the question's language.

    The three options are the fixed factory scopes, not labels inferred from the question.
    """
    lang = reply_language(question or reason)
    card = {
        "prompt": _SCOPE_PROMPT[lang],
        "options": [dict(row) for row in SCOPE_OPTIONS[lang]],
    }
    return attach_other(card, question or reason)


def _tables_and_terms() -> tuple[dict[str, set[str]], dict[str, bool]]:
    layer = load_semantic_layer()
    tables: dict[str, set[str]] = {}
    for name, table in (layer.get("data_definition") or {}).get("tables", {}).items():
        tables[str(name)] = set((table.get("columns") or {}).keys())
    terms: dict[str, bool] = {}
    for name, term in (layer.get("term_definition") or {}).get("terms", {}).items():
        terms[str(name)] = term.get("in_dataset") is not False
    return tables, terms


def resolve_column(table: str | None, column: str | None) -> tuple[str, str] | None:
    """Return (table, column) if that stored column exists."""
    if not column:
        return None
    tables, _terms = _tables_and_terms()
    col = column.strip()
    tbl = (table or "").strip()
    if tbl in tables and col in tables[tbl]:
        return tbl, col
    for name, cols in tables.items():
        if col in cols:
            return name, col
    return None


def continues_prior_rows(question: str, prior_tool_json: str) -> bool:
    """True when this question names no new order, customer, or product, and the last tool listed orders."""
    if "order_id" not in (prior_tool_json or ""):
        return False
    return named_order_field(question) is None


def named_order_field(question: str) -> tuple[str, str] | None:
    """Return orders.order_id, orders.customer, or orders.product when the question names one."""
    text = question or ""
    if not text.strip():
        return None
    try:
        from backend.services.database import get_db

        rows = get_db().find_orders()
    except Exception:  # noqa: BLE001 — a down database must not invent a match
        logger.exception("named order field lookup failed")
        return None
    for match in re.finditer(r"ORD-\d+", text, re.I):
        oid = match.group(0).upper()
        if any(str(row.get("order_id") or "").upper() == oid for row in rows):
            return "orders", "order_id"
    for column in ("customer", "product"):
        names = sorted(
            {str(row.get(column) or "").strip() for row in rows},
            key=len,
            reverse=True,
        )
        for name in names:
            if not name:
                continue
            if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.I):
                return "orders", column
    return None


def apply_catalog(data: DataVerdict, tools: ToolVerdict) -> tuple[DataVerdict, ToolVerdict]:
    """Keep step-2 has_tool. Only clamp whether the named column is stored."""
    tables, terms = _tables_and_terms()
    if data.kind == "action":
        data.stored = True
        return data, tools

    resolved = resolve_column(data.table, data.column)
    term_key = (data.column or "").strip()
    if resolved:
        data.stored = True
        data.table, data.column = resolved
    elif term_key in terms and not terms[term_key]:
        data.stored = False
        data.table = None
    elif data.table in tables and not resolved:
        data.stored = False

    if not data.stored:
        tools.has_tool = False
        tools.tool = None
    return data, tools


def _parse_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    match = _JSON_OBJECT.search(raw)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content or "")


def _ask_json(model: Any, system: str, user: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    result = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _parse_json_object(_content_text(getattr(result, "content", result)))


def _data_from_payload(payload: dict[str, Any]) -> DataVerdict:
    kind = str(payload.get("kind") or "fact").strip().lower()
    if kind not in {"fact", "action", "follow_up"}:
        kind = "fact"
    return DataVerdict(
        kind=kind,
        stored=bool(payload.get("stored")),
        table=(str(payload["table"]) if payload.get("table") else None),
        column=(str(payload["column"]) if payload.get("column") else None),
        reason=str(payload.get("reason") or "").strip(),
    )


def _tools_from_payload(payload: dict[str, Any]) -> ToolVerdict:
    readings: list[str] = []
    options: list[dict[str, str]] = []
    for item in payload.get("readings") or []:
        if isinstance(item, str):
            name = item.strip()
            if name and name not in readings:
                readings.append(name)
            continue
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool") or "").strip()
        label = str(item.get("label") or "").strip()
        message = str(item.get("message") or "").strip()
        if not tool_name or tool_name in readings:
            continue
        readings.append(tool_name)
        if label and message:
            options.append({"tool": tool_name, "label": label, "message": message})
    tool = str(payload["tool"]).strip() if payload.get("tool") else None
    if tool and tool not in readings:
        readings.insert(0, tool)
    has_tool = bool(payload.get("has_tool")) or bool(payload.get("ambiguous") is False and tool)
    needs_tool = True if "needs_tool" not in payload else bool(payload.get("needs_tool"))
    if payload.get("ambiguous") is True or not needs_tool:
        has_tool = False
        tool = None
    return ToolVerdict(
        has_tool=has_tool,
        tool=tool,
        reason=str(payload.get("reason") or "").strip(),
        needs_tool=needs_tool,
        readings=readings,
        options=options,
    )


_ACTION_TOOLS = {
    "draft_chase_email",
    "send_email",
    "add_order_note",
    "create_reminder",
    "create_watch",
    "cancel_watch",
    "get_recent_actions",
    "list_watches",
}


def _ask_tool_coverage(model: Any, data: DataVerdict, question: str) -> ToolVerdict:
    from backend.tools.registry import MVP_TOOLS

    tool_names = ", ".join(getattr(t, "name", str(t)) for t in MVP_TOOLS)
    tool_user = (
        "Step 1 JSON:\n"
        + json.dumps(data.__dict__, ensure_ascii=False)
        + "\n\nRegistered tools:\n"
        + tool_names
        + "\n\nWhat each tool looks up:\n"
        + TOOL_LOOKUP_TABLE
        + "\n\nFirst decide needs_tool. False only when Previous tool JSON already "
        "holds the facts and this question only changes the wording. "
        "If needs_tool is true, has_tool=true only if one registered tool returns "
        "the step-1 field. A list tool that filters on that column counts. "
        "If none do, has_tool=false and tool=null.\n\n"
        "Manager question:\n"
        + (question or "")
    )
    tools = _tools_from_payload(_ask_json(model, _TOOL_SYSTEM, tool_user))
    if not tools.has_tool and data.reason:
        tools.reason = data.reason
    return tools


def _compose_answer(data: DataVerdict, tools: ToolVerdict) -> tuple[str, str]:
    if data.kind != "action" and not data.stored:
        text = data.reason or (
            "That fact is not in the factory tables, so the data is missing."
        )
        return text, "missing_data"
    loc = f"{data.table}.{data.column}" if data.table and data.column else "the tables"
    text = tools.reason or (
        f"The fact is stored in {loc}, but no registered tool returns that field, "
        "so I cannot fetch it."
    )
    if data.table and data.column and loc not in text:
        text = f"{loc} exists in the data. {text}"
    return text, "no_tool"


def _trace(name: str, payload: dict[str, Any], basis: str) -> dict[str, Any]:
    return {
        "tool": name,
        "source_file": "semantic_layer.yaml",
        "filter": payload,
        "rows": [],
        "calculations": [],
        "basis": basis,
    }


def assess_answerability(
    question: str,
    model: Any | None = None,
    *,
    prior_tool_json: str = "",
    clarification_reply: bool = False,
) -> AnswerabilityGate:
    """Clarify first, without a stored-field check. Then stored-data and tool coverage."""
    if model is None:
        from backend.agent.graph import build_model

        model = build_model()

    prior = (prior_tool_json or "").strip()
    if not clarification_reply:
        ambiguity_user = (
            language_rule(question)
            + "\n\nWhat each tool answers:\n"
            + TOOL_LOOKUP_TABLE
            + "\nPrevious tool JSON:\n"
            + (prior or "(none)")
            + "\nManager question:\n"
            + (question or "")
        )
        ambiguity = _tools_from_payload(
            _ask_json(model, _AMBIGUITY_SYSTEM, ambiguity_user)
        )
        card = interpretation_clarification(question, ambiguity.options, ambiguity.reason)
        if card is not None:
            logger.info("answerability clarify readings=%s", ambiguity.readings)
            return AnswerabilityGate(
                proceed=False,
                data=DataVerdict(reason=ambiguity.reason),
                tools=ambiguity,
                answer=card["prompt"],
                limitation="needs_clarification",
                traces=[
                    _trace(
                        "assess_ambiguity",
                        {"ambiguous": True, "readings": ambiguity.readings},
                        ambiguity.reason,
                    )
                ],
                clarification=card,
            )

    data_user = (
        "Semantic layer:\n"
        + render_semantic_prompt()
        + "\nPrevious tool JSON:\n"
        + (prior or "(none)")
        + "\nManager question:\n"
        + (question or "")
    )
    data = _data_from_payload(_ask_json(model, _DATA_SYSTEM, data_user))
    if data.kind == "follow_up" and prior:
        traces = [
            _trace(
                "assess_stored_data",
                {"kind": "follow_up", "stored": True, "table": None, "column": None},
                data.reason or "Explain the previous tool formula. Do not look up a new fact.",
            )
        ]
        logger.info("answerability proceed kind=follow_up")
        return AnswerabilityGate(
            proceed=True,
            data=data,
            tools=ToolVerdict(has_tool=True, tool=None),
            traces=traces,
            explain_prior=True,
        )
    if data.kind == "follow_up":
        data = _data_from_payload(
            _ask_json(
                model,
                _DATA_SYSTEM
                + "\nPrevious tool JSON is empty. kind must be fact or action, not follow_up.",
                data_user,
            )
        )
        if data.kind == "follow_up":
            data.kind = "fact"
            data.stored = False

    tools = _ask_tool_coverage(model, data, question)
    if data.kind == "action" and (tools.tool or "") not in _ACTION_TOOLS:
        data = _data_from_payload(
            _ask_json(
                model,
                _DATA_SYSTEM
                + "\nThis is not an email, note, reminder, watch, or audit. "
                "kind must be fact. Name the stored table and column.",
                data_user,
            )
        )
        if data.kind == "action":
            data.kind = "fact"
            if not data.column:
                data.stored = False
        tools = _ask_tool_coverage(model, data, question)
    data, tools = apply_catalog(data, tools)
    if data.kind != "action" and not data.stored:
        named = named_order_field(question)
        if named:
            data.stored = True
            data.table, data.column = named
            data.kind = "fact"
            if not tools.has_tool:
                tools.has_tool = True
                tools.tool = "get_order_status"
                tools.reason = data.reason or tools.reason
    if (
        data.kind != "action"
        and not data.stored
        and not clarification_reply
        and continues_prior_rows(question, prior)
    ):
        data = _data_from_payload(
            _ask_json(
                model,
                _DATA_SYSTEM
                + "\nPrevious tool JSON already listed the rows. This question asks a "
                "further fact about those rows. If that fact is in the tables, "
                "kind=fact and stored=true. Do not use follow_up. "
                "stored=false only when the fact is not in any table.",
                data_user,
            )
        )
        if data.kind == "follow_up":
            data.kind = "fact"
            data.stored = True
        tools = _ask_tool_coverage(model, data, question)
        data, tools = apply_catalog(data, tools)

    traces = [
        _trace(
            "assess_stored_data",
            {
                "kind": data.kind,
                "stored": data.stored,
                "table": data.table,
                "column": data.column,
            },
            data.reason,
        ),
        _trace(
            "assess_tool_coverage",
            {"needs_tool": tools.needs_tool, "has_tool": tools.has_tool, "tool": tools.tool},
            tools.reason,
        ),
    ]

    covered = (not tools.needs_tool) or tools.has_tool
    if (data.kind == "action" or data.stored) and covered:
        logger.info(
            "answerability proceed kind=%s stored=%s needs_tool=%s table=%s column=%s tool=%s",
            data.kind,
            data.stored,
            tools.needs_tool,
            data.table,
            data.column,
            tools.tool,
        )
        return AnswerabilityGate(
            proceed=True,
            data=data,
            tools=tools,
            traces=traces,
            reuse_prior=not tools.needs_tool,
        )

    answer, limitation = _compose_answer(data, tools)
    logger.info("answerability stop limitation=%s", limitation)
    return AnswerabilityGate(
        proceed=False,
        data=data,
        tools=tools,
        answer=answer,
        limitation=limitation,
        traces=traces,
    )
