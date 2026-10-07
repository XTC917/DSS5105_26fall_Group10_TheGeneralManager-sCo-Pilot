"""LangGraph ReAct agent: choose tools, read results, then answer."""

from __future__ import annotations

import json
import logging
import os
import re
from contextvars import ContextVar
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from backend.config import PROJECT_ROOT
from backend.agent.answerability import (
    ambiguous_clarification,
    assess_answerability,
    continues_prior_rows,
    reply_language,
)
from backend.agent.language import align_visible_payload
from backend.agent.prompts import build_system_prompt, format_retrieved_templates
from backend.agent.routing import route_query
from backend.services.question_templates import (
    retrieve_answer_templates,
    supplement_templates_for_tools,
    without_foreign_order_templates,
)
from backend.tools.common import reset_manager_text, set_manager_text
from backend.tools.draw import bind_frontend_charts, take_frontend_charts
from backend.tools.render_table import bind_frontend_tables, take_frontend_tables
from backend.tools.registry import MVP_TOOLS

load_dotenv(PROJECT_ROOT / ".env", override=True)
logger = logging.getLogger(__name__)

_AGENT = None
_CHECKPOINTER = MemorySaver()


def set_checkpointer(checkpointer: Any | None) -> None:
    """Swap the stored thread. Tests keep MemorySaver; the API uses Postgres."""
    global _AGENT, _CHECKPOINTER
    _AGENT = None
    _CHECKPOINTER = checkpointer if checkpointer is not None else MemorySaver()
_TEMPLATE_QUERY: ContextVar[str] = ContextVar("template_query", default="")
_EXPLAIN_PRIOR: ContextVar[bool] = ContextVar("explain_prior", default=False)
_REUSE_PRIOR: ContextVar[bool] = ContextVar("reuse_prior", default=False)
_PRIOR_ORDER_IDS: ContextVar[str] = ContextVar("prior_order_ids", default="")

# ---------------------------------------------------------------------------
# LLM provider switch.
#
#   Development (Gemini, default when GOOGLE_API_KEY is set):
#       LLM_PROVIDER=gemini
#       LLM_MODEL=gemini-3.6-flash        (current API default; use the exact
#                                        name shown in AI Studio if it changes)
#       GOOGLE_API_KEY=AIza...           (from https://aistudio.google.com/app/apikey)
#
#   Switch back to GPT (OpenAI-compatible):
#       LLM_PROVIDER=openai
#       LLM_MODEL=gpt-4o-mini            (or gpt-5.x once your key supports it)
#       OPENAI_API_KEY=sk-...
#       OPENAI_BASE_URL=                 (leave empty for api.openai.com)
# ---------------------------------------------------------------------------


def _get_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if provider in ("gemini", "google"):
        return "gemini"
    if provider == "openai":
        return "openai"
    # Auto-detect: prefer gemini when a Google key exists.
    if os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "openai"


def active_provider() -> str:
    return _get_provider()


def active_model() -> str:
    if _get_provider() == "gemini":
        return os.getenv("LLM_MODEL", "gemini-3.6-flash")
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def llm_is_configured() -> bool:
    if _get_provider() == "gemini":
        return bool((os.getenv("GOOGLE_API_KEY") or "").strip())
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def build_model():
    """Native provider client.

    Gemini goes through langchain-google-genai (NOT the OpenAI-compat layer),
    which is what preserves thought signatures for tool calls on thinking
    models. OpenAI stays on langchain-openai.
    """
    if _get_provider() == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("LLM_MODEL", "gemini-3.6-flash"),
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        # gpt-5.6 rejects function tools on /v1/chat/completions when reasoning
        # is on. /v1/responses accepts that combination.
        "use_responses_api": True,
    }
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _react_prompt(state: dict[str, Any]):
    """Add answer templates only after this turn has produced tool JSON."""
    system = build_system_prompt()
    if _EXPLAIN_PRIOR.get():
        system += (
            "\n\nThe manager is asking how a figure already in the previous tool "
            "result was calculated. Explain that formula from the previous tool "
            "JSON in this conversation. Do not call any tool."
        )
    if _REUSE_PRIOR.get():
        system += (
            "\n\nThe previous tool JSON already has the facts. "
            "Restate that result as the manager asked. Do not call any tool."
        )
    prior_ids = _PRIOR_ORDER_IDS.get()
    if prior_ids:
        system += (
            "\n\nThis question continues the previous result. "
            "The subject is only these order ids: "
            + prior_ids
            + ". Call a tool when the new fact is not already in that result. "
            "Mention only these ids in the reply."
        )
    messages = state.get("messages") or []
    turn = _latest_turn(messages)
    if any(isinstance(msg, ToolMessage) for msg in turn):
        called = set(_tools_from_turn(turn))
        charted = bool(called & {"draw", "render_table"})
        hold_for_chart = not charted and not _EXPLAIN_PRIOR.get() and not _REUSE_PRIOR.get()
        if hold_for_chart:
            system += (
                "\n\nA retrieval tool already returned the data. "
                "Your next message MUST be exactly one tool call, draw or render_table, not prose. "
                "Prefer draw when the values compare, compose, or trend. "
                "Prefer render_table when the result is a list of rows. "
                "Copy only values already in that JSON. Do not calculate. "
                "Do not answer in text on this step."
            )
        else:
            query = _TEMPLATE_QUERY.get()
            hits = retrieve_answer_templates(query)
            hits = supplement_templates_for_tools(query, hits, _tools_from_turn(turn))
            hits = without_foreign_order_templates(query, hits)
            extra = format_retrieved_templates(hits)
            if extra:
                system = system + "\n\n" + extra
            if charted:
                system += (
                    "\n\nA chart or table tool already ran this turn. "
                    "Write the reply from the tool JSON now. Do not call another tool. "
                    "The chart or table is already shown. Do not write it again, "
                    "and do not write a plotting program, an image, or a data:image URL."
                )
    return [SystemMessage(content=system), *messages]


def _tools_from_turn(turn: list[BaseMessage]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for msg in turn:
        if not isinstance(msg, ToolMessage):
            continue
        payload = _parse_json(getattr(msg, "content", ""))
        tool = ""
        if isinstance(payload, dict):
            tool = str(payload.get("tool") or "").strip()
        if not tool:
            tool = str(getattr(msg, "name", None) or "").strip()
        if tool and tool not in seen:
            seen.add(tool)
            names.append(tool)
    return names


def get_agent():
    """Build the agent once. Provider selected by LLM_PROVIDER / keys."""
    global _AGENT
    if _AGENT is None:
        if not llm_is_configured():
            raise RuntimeError(
                "LLM key is not set. For Gemini set GOOGLE_API_KEY; "
                "for GPT set OPENAI_API_KEY. Copy .env.example to .env. "
                "Tools can still be tested with pytest without a key."
            )
        model = build_model()
        _AGENT = create_react_agent(
            model,
            MVP_TOOLS,
            prompt=_react_prompt,
            checkpointer=_CHECKPOINTER,
        )
        logger.info(
            "LangGraph agent initialised with %s tools provider=%s model=%s",
            len(MVP_TOOLS),
            _get_provider(),
            active_model(),
        )
    return _AGENT


def _manager_text(conversation_id: str, message: str) -> str:
    """Human wording only. Templates and tool rows are not a source of order ids."""
    parts = [message or ""]
    if llm_is_configured():
        try:
            state = get_agent().get_state({"configurable": {"thread_id": conversation_id}})
        except Exception:  # noqa: BLE001
            logger.exception("manager text state unavailable")
            state = None
        messages = (getattr(state, "values", None) or {}).get("messages") or []
        for msg in messages:
            if _is_human(msg):
                parts.append(_content_to_text(getattr(msg, "content", "")))
    return "\n".join(part for part in parts if part)


def _previous_turn_order_ids(conversation_id: str) -> list[str]:
    """Order ids returned by tools after the previous manager question."""
    if not llm_is_configured():
        return []
    try:
        state = get_agent().get_state({"configurable": {"thread_id": conversation_id}})
    except Exception:  # noqa: BLE001
        logger.exception("previous order ids unavailable")
        return []
    messages = (getattr(state, "values", None) or {}).get("messages") or []
    start = 0
    for i, msg in enumerate(messages):
        if _is_human(msg):
            start = i
    found: list[str] = []
    for msg in messages[start:]:
        if not isinstance(msg, ToolMessage):
            continue
        for match in re.finditer(r"ORD-\d+", _content_to_text(getattr(msg, "content", "")), re.I):
            oid = match.group(0).upper()
            if oid not in found:
                found.append(oid)
    return found


def _prior_tool_json(conversation_id: str) -> str:
    """Tool payloads already in this thread, for follow-up explanations."""
    if not llm_is_configured():
        return ""
    try:
        state = get_agent().get_state({"configurable": {"thread_id": conversation_id}})
    except Exception:  # noqa: BLE001
        logger.exception("prior tool state unavailable")
        return ""
    messages = (getattr(state, "values", None) or {}).get("messages") or []
    chunks: list[str] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        text = _content_to_text(getattr(msg, "content", ""))
        if text:
            chunks.append(text[:1500])
    return "\n\n".join(chunks[-2:])


def _model_turn(message: str, *, clarification_reply: bool) -> str:
    """The answering model sees a chosen clarification as a lookup, not a new offer."""
    if not clarification_reply:
        return message
    if reply_language(message) == "zh":
        lead = "这是经理在澄清里已经选好的读法。按这句话去查，不要把它当成经理要自己提供数据。"
    else:
        lead = (
            "This is the reading the manager already chose. Look that up. "
            "Do not treat it as the manager offering to supply the data."
        )
    return f"{lead}\n{message}"


def run_agent(
    message: str,
    conversation_id: str,
    *,
    clarification_reply: bool = False,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Entry point used by /api/chat.

    Unsupported / not-implemented questions are answered here without an LLM
    call, so no unrelated tool can fire.
    """
    memory_thread = thread_id or conversation_id
    decision = route_query(message)
    if decision.short_circuit:
        logger.info(
            "route short-circuit conversation=%s intent=%s",
            conversation_id,
            decision.intent,
        )
        parsed = {
            "answer": decision.answer or "",
            "conversation_id": conversation_id,
            "tools_used": [],
            "traces": [],
            "proposed_actions": [],
            "clarification": None,
            "limitation": decision.reason,
            "routing_intent": decision.intent,
        }
        align_visible_payload(parsed, message)
        _audit_turn(message, conversation_id, parsed, short_circuit=True)
        return parsed

    gate = assess_answerability(
        message,
        prior_tool_json=_prior_tool_json(memory_thread),
        clarification_reply=clarification_reply,
    )
    if not gate.proceed:
        parsed = {
            "answer": gate.answer or "",
            "conversation_id": conversation_id,
            "tools_used": [
                trace.get("tool")
                for trace in gate.traces
                if isinstance(trace, dict) and trace.get("tool")
            ]
            or ["assess_stored_data", "assess_tool_coverage"],
            "traces": gate.traces,
            "proposed_actions": [],
            "clarification": gate.clarification,
            "limitation": gate.limitation,
            "routing_intent": decision.intent,
        }
        align_visible_payload(parsed, message)
        _audit_turn(message, conversation_id, parsed, short_circuit=False)
        return parsed

    token = _TEMPLATE_QUERY.set(message)
    explain = _EXPLAIN_PRIOR.set(gate.explain_prior)
    reuse = _REUSE_PRIOR.set(gate.reuse_prior)
    prior_ids = ""
    if (
        gate.proceed
        and not gate.explain_prior
        and not gate.reuse_prior
        and continues_prior_rows(message, _prior_tool_json(memory_thread))
    ):
        prior_ids = " ".join(_previous_turn_order_ids(memory_thread))
    held_ids = _PRIOR_ORDER_IDS.set(prior_ids)
    spoken = _manager_text(memory_thread, message)
    if prior_ids:
        spoken = spoken + "\n" + prior_ids
    manager = set_manager_text(spoken)
    held_charts = bind_frontend_charts()
    held_tables = bind_frontend_tables()
    try:
        agent = get_agent()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": _model_turn(message, clarification_reply=clarification_reply)}]},
            config={"configurable": {"thread_id": memory_thread}},
        )
    finally:
        charts = take_frontend_charts(held_charts)
        tables = take_frontend_tables(held_tables)
        _TEMPLATE_QUERY.reset(token)
        _EXPLAIN_PRIOR.reset(explain)
        _REUSE_PRIOR.reset(reuse)
        _PRIOR_ORDER_IDS.reset(held_ids)
        reset_manager_text(manager)
    parsed = parse_agent_result(result, conversation_id)
    if charts:
        parsed["charts"] = list(parsed.get("charts") or []) + charts
    if tables:
        parsed["tables"] = list(parsed.get("tables") or []) + tables
    parsed["tables"] = _drop_superseded_error_tables(
        parsed.get("tables") or [], parsed.get("charts") or []
    )
    parsed["routing_intent"] = decision.intent
    parsed["traces"] = list(gate.traces) + list(parsed.get("traces") or [])
    align_visible_payload(parsed, message)
    _audit_turn(message, conversation_id, parsed, short_circuit=False)
    return parsed


def _error_echo_table(table: dict[str, Any]) -> bool:
    """A table whose only cells are a failed tool's code and message."""
    keys = [str((column or {}).get("key") or "") for column in table.get("columns") or []]
    if not keys or any(key not in {"code", "message"} for key in keys):
        return False
    if "code" not in keys or "message" not in keys:
        return False
    return any(str((row or {}).get("code") or "").strip() for row in table.get("rows") or [])


def _drop_superseded_error_tables(
    tables: list[dict[str, Any]], charts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Hide a failed call once a later call produced the chart or table."""
    if not any(_error_echo_table(table) for table in tables):
        return tables
    if not charts and all(_error_echo_table(table) for table in tables):
        return tables
    return [table for table in tables if not _error_echo_table(table)]


def _is_human(msg: Any) -> bool:
    if isinstance(msg, HumanMessage):
        return True
    return getattr(msg, "type", None) == "human"


def _latest_turn(messages: list[Any]) -> list[Any]:
    """Keep messages from the latest user question onward."""
    last_human = 0
    for i, msg in enumerate(messages):
        if _is_human(msg):
            last_human = i
    return messages[last_human:]


_DISPLAY_TOOLS = frozenset({"draw", "render_table"})


def _ambiguous_tool_payload(turn: list[Any]) -> dict[str, Any] | None:
    """The latest lookup that stopped on several rows, if a later lookup did not resolve it."""
    found: dict[str, Any] | None = None
    for msg in turn:
        if not isinstance(msg, ToolMessage):
            continue
        payload = _parse_json(msg.content)
        if not payload:
            continue
        tool_name = str(payload.get("tool") or getattr(msg, "name", "") or "")
        error = payload.get("error") or {}
        if error.get("code") == "AMBIGUOUS":
            found = payload
            continue
        if payload.get("ok") and tool_name not in _DISPLAY_TOOLS:
            found = None
    return found


def parse_agent_result(result: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    messages: list[BaseMessage] = result.get("messages") or []
    # MemorySaver returns the whole thread. The UI must only show tools from
    # the latest manager question, otherwise a feasibility answer will look
    # like it also called get_order_status / get_orders_at_risk / trace_order.
    turn = _latest_turn(messages)
    tools_used: list[str] = []
    traces: list[dict[str, Any]] = []
    proposed_actions: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    limitation = None
    ungrounded_message = None

    for msg in turn:
        if isinstance(msg, ToolMessage):
            payload = _parse_json(msg.content)
            if not payload:
                continue
            tool_name = payload.get("tool") or getattr(msg, "name", None)
            if tool_name:
                tools_used.append(tool_name)
            if payload.get("trace"):
                traces.append(payload["trace"])
            data = payload.get("data") or {}
            proposal = data.get("proposed_action")
            if isinstance(proposal, dict):
                proposed_actions.append(proposal)
            chart = data.get("chart")
            if isinstance(chart, dict):
                charts.append(chart)
            table = data.get("table")
            if isinstance(table, dict):
                tables.append(table)
            error = payload.get("error") or {}
            if error.get("code") in {"UNSUPPORTED", "NOT_IMPLEMENTED"}:
                limitation = error.get("message")
            if error.get("code") == "UNGROUNDED_ID":
                ungrounded_message = error.get("message")

    answer = ""
    if ungrounded_message:
        answer = str(ungrounded_message)
        limitation = limitation or "ungrounded_id"
    else:
        for msg in reversed(turn):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                answer = _content_to_text(msg.content)
                break
        if not answer and turn:
            answer = _content_to_text(getattr(turn[-1], "content", ""))

    question = ""
    for msg in turn:
        if _is_human(msg):
            question = _content_to_text(getattr(msg, "content", ""))
            break
    ambiguous = _ambiguous_tool_payload(turn)
    card = ambiguous_clarification(question, (ambiguous or {}).get("error") or {}) if ambiguous else None
    if card:
        tool_name = str(ambiguous.get("tool") or "") if ambiguous else ""
        logger.info(
            "agent done conversation=%s tools=%s clarification=ambiguous",
            conversation_id,
            [tool_name] if tool_name else tools_used,
        )
        return {
            "answer": card["prompt"],
            "conversation_id": conversation_id,
            "tools_used": [tool_name] if tool_name else tools_used,
            "traces": traces,
            "proposed_actions": [],
            "charts": [],
            "tables": [],
            "clarification": card,
            "limitation": "needs_clarification",
            "routing_intent": "proceed",
        }

    logger.info(
        "agent done conversation=%s tools=%s",
        conversation_id,
        tools_used,
    )
    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "tools_used": tools_used,
        "traces": traces,
        "proposed_actions": proposed_actions,
        "charts": charts,
        "tables": tables,
        "clarification": None,
        "limitation": limitation,
        "routing_intent": "proceed",
    }


def _audit_turn(
    message: str,
    conversation_id: str,
    parsed: dict[str, Any],
    *,
    short_circuit: bool,
) -> None:
    try:
        from backend.services.audit import record_event

        tools = parsed.get("tools_used") or []
        record_event(
            event_type="short_circuit" if short_circuit else "agent_turn",
            conversation_id=conversation_id,
            user_query=message,
            tool=",".join(tools) or None,
            inputs={
                "routing_intent": parsed.get("routing_intent"),
                "tools_used": tools,
            },
            result_ok=True,
            result_summary=(parsed.get("answer") or "")[:500],
            execution_status="no_tool" if short_circuit else "answered",
        )
        for trace in parsed.get("traces") or []:
            record_event(
                event_type="tool_result",
                conversation_id=conversation_id,
                user_query=message,
                tool=trace.get("tool"),
                inputs=trace.get("filter") if isinstance(trace.get("filter"), dict) else None,
                result_ok=True,
                result_summary=(trace.get("basis") or "")[:500],
                target=None,
            )
    except Exception:  # noqa: BLE001 — audit must not break answers
        logger.exception("audit write failed")


def _parse_json(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p for p in parts if p)
    return str(content or "")
