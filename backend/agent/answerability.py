"""Two gated LLM steps: is the fact stored, then does a tool return it.

Python only checks that the named table.column exists in the semantic layer.
It does not map tables onto tools. ReAct picks the tool if both gates pass.
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
{"kind":"fact"|"action","stored":true|false,"table":string|null,"column":string|null,"reason":string}

kind=action: email, note, reminder, watch, or audit. Then stored=true, table=null, column=null.
kind=fact: pick table and column from the semantic layer only.
stored=true only if that column exists (or an equivalent stored column).
stored=false if the fact is not a stored column (including terms marked not a stored column).
reason: one or two sentences in the same language as the manager.
Do not invent numbers. Do not name example customers or shops.
"""

_TOOL_SYSTEM = """You only decide whether a registered tool's JSON can return the field from step 1.

Reply with one JSON object, no markdown:
{"has_tool":true|false,"tool":string|null,"reason":string}

has_tool=true only if that tool is meant to look up this field.
A tool that merely mentions another table as a side effect of a different question
does not count as a lookup tool for that table.
If kind is action, pick the matching action tool.
reason: copy the manager's language. Do not translate step 1. If unsure, use ENGLISH.
Do not invent numbers. Do not name example customers or shops.
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


@dataclass
class AnswerabilityGate:
    proceed: bool
    data: DataVerdict
    tools: ToolVerdict
    answer: str | None = None
    limitation: str | None = None
    traces: list[dict[str, Any]] = field(default_factory=list)


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
    if kind not in {"fact", "action"}:
        kind = "fact"
    return DataVerdict(
        kind=kind,
        stored=bool(payload.get("stored")),
        table=(str(payload["table"]) if payload.get("table") else None),
        column=(str(payload["column"]) if payload.get("column") else None),
        reason=str(payload.get("reason") or "").strip(),
    )


def _tools_from_payload(payload: dict[str, Any]) -> ToolVerdict:
    return ToolVerdict(
        has_tool=bool(payload.get("has_tool")),
        tool=(str(payload["tool"]) if payload.get("tool") else None),
        reason=str(payload.get("reason") or "").strip(),
    )


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


def assess_answerability(question: str, model: Any | None = None) -> AnswerabilityGate:
    """Run stored-data then tool-coverage. proceed=False means skip ReAct/few-shot."""
    if model is None:
        from backend.agent.graph import build_model

        model = build_model()

    data_user = (
        "Semantic layer:\n"
        + render_semantic_prompt()
        + "\nManager question:\n"
        + (question or "")
    )
    data = _data_from_payload(_ask_json(model, _DATA_SYSTEM, data_user))
    from backend.tools.registry import MVP_TOOLS

    tool_names = ", ".join(getattr(t, "name", str(t)) for t in MVP_TOOLS)
    tool_user = (
        "Step 1 JSON:\n"
        + json.dumps(data.__dict__, ensure_ascii=False)
        + "\n\nRegistered tools:\n"
        + tool_names
        + "\n\nWhat each tool looks up:\n"
        + TOOL_LOOKUP_TABLE
        + "\n\nhas_tool=true only if one of those tools returns the step-1 field "
        "for this question. A list tool that filters on that column counts "
        "(including an empty list). Do not treat a side-effect mention of another "
        "table as coverage. If none do, has_tool=false and tool=null.\n\n"
        "Manager question:\n"
        + (question or "")
    )
    tools = _tools_from_payload(_ask_json(model, _TOOL_SYSTEM, tool_user))
    if not tools.has_tool and data.reason:
        tools.reason = data.reason
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
            {"has_tool": tools.has_tool, "tool": tools.tool},
            tools.reason,
        ),
    ]

    if (data.kind == "action" or data.stored) and tools.has_tool:
        logger.info(
            "answerability proceed kind=%s stored=%s table=%s column=%s tool=%s",
            data.kind,
            data.stored,
            data.table,
            data.column,
            tools.tool,
        )
        return AnswerabilityGate(
            proceed=True, data=data, tools=tools, traces=traces
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
