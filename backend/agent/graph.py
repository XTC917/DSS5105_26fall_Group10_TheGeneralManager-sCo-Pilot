"""LangGraph ReAct agent: choose tools, read results, then answer."""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from backend.agent.prompts import build_system_prompt, format_retrieved_templates
from backend.agent.routing import route_query
from backend.services.question_templates import retrieve_answer_templates
from backend.tools.registry import MVP_TOOLS

load_dotenv()
logger = logging.getLogger(__name__)

_AGENT = None
_CHECKPOINTER = MemorySaver()
_TEMPLATE_QUERY: ContextVar[str] = ContextVar("template_query", default="")

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
        return bool(os.getenv("GOOGLE_API_KEY"))
    return bool(os.getenv("OPENAI_API_KEY"))


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
    }
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _react_prompt(state: dict[str, Any]):
    """Add answer templates only after this turn has produced tool JSON."""
    system = build_system_prompt()
    messages = state.get("messages") or []
    turn = _latest_turn(messages)
    if any(isinstance(msg, ToolMessage) for msg in turn):
        hits = retrieve_answer_templates(_TEMPLATE_QUERY.get())
        extra = format_retrieved_templates(hits)
        if extra:
            system = system + "\n\n" + extra
    return [SystemMessage(content=system), *messages]


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


def run_agent(message: str, conversation_id: str) -> dict[str, Any]:
    """Entry point used by /api/chat.

    Unsupported / not-implemented questions are answered here without an LLM
    call, so no unrelated tool can fire.
    """
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
            "limitation": decision.reason,
            "routing_intent": decision.intent,
        }
        _audit_turn(message, conversation_id, parsed, short_circuit=True)
        return parsed

    token = _TEMPLATE_QUERY.set(message)
    try:
        agent = get_agent()
        result = agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": conversation_id}},
        )
    finally:
        _TEMPLATE_QUERY.reset(token)
    parsed = parse_agent_result(result, conversation_id)
    parsed["routing_intent"] = decision.intent
    _audit_turn(message, conversation_id, parsed, short_circuit=False)
    return parsed


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


def parse_agent_result(result: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    messages: list[BaseMessage] = result.get("messages") or []
    # MemorySaver returns the whole thread. The UI must only show tools from
    # the latest manager question, otherwise a feasibility answer will look
    # like it also called get_order_status / get_orders_at_risk / trace_order.
    turn = _latest_turn(messages)
    tools_used: list[str] = []
    traces: list[dict[str, Any]] = []
    proposed_actions: list[dict[str, Any]] = []
    limitation = None

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
            error = payload.get("error") or {}
            if error.get("code") in {"UNSUPPORTED", "NOT_IMPLEMENTED"}:
                limitation = error.get("message")

    answer = ""
    for msg in reversed(turn):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            answer = _content_to_text(msg.content)
            break
    if not answer and turn:
        answer = _content_to_text(getattr(turn[-1], "content", ""))

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
