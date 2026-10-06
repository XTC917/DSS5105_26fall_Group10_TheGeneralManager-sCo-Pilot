"""LangGraph ReAct agent: choose tools, read results, then answer."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.routing import route_query
from backend.tools.registry import MVP_TOOLS

load_dotenv()
logger = logging.getLogger(__name__)

_AGENT = None
_CHECKPOINTER = MemorySaver()

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
            prompt=SYSTEM_PROMPT,
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
            "presentations": [],
        }
        _audit_turn(message, conversation_id, parsed, short_circuit=True)
        return parsed

    agent = get_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": conversation_id}},
    )
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
    tool_results: list[dict[str, Any]] = []
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
            if payload.get("ok") and tool_name and isinstance(data, dict):
                tool_results.append({"tool": tool_name, "data": data})
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

    answer, llm_intents = _extract_llm_intents(answer)
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
        "presentations": _build_presentations(messages, tool_results, llm_intents),
    }


_INTENT_FENCE_RE = None


def _intent_fence_re():
    global _INTENT_FENCE_RE
    if _INTENT_FENCE_RE is None:
        import re
        _INTENT_FENCE_RE = re.compile(
            r"```(?:presentation-intents|json)?\s*\n?\s*(\{\s*\"presentation_intents\".*?\})\s*```",
            re.DOTALL | re.IGNORECASE,
        )
    return _INTENT_FENCE_RE


def _extract_llm_intents(answer: str) -> tuple[str, list[dict[str, Any]]]:
    """Split the fenced presentation-intents block off the narrative.

    The block references (intent, source_tool, source_path, title) only — no
    business data — so this is plan extraction, not prose data-mining. Any
    parse/validation failure yields [] and the narrative still renders.
    """
    if "presentation_intents" not in (answer or ""):
        return answer, []
    try:
        m = _intent_fence_re().search(answer)
        if not m:
            return answer, []
        raw = json.loads(m.group(1))
        intents = raw.get("presentation_intents") if isinstance(raw, dict) else None
        if not isinstance(intents, list):
            return answer, []
        from backend.presentation.engine import CANON
        valid: list[dict[str, Any]] = []
        for item in intents[:4]:
            if not isinstance(item, dict):
                continue
            intent = CANON.get(str(item.get("intent", "")).lower(), "")
            src_tool = str(item.get("source_tool", "") or "")
            if not intent or not src_tool or len(src_tool) > 64:
                continue
            valid.append({
                "intent": intent,
                "source_tool": src_tool,
                "source_path": str(item.get("source_path", "") or "")[:128],
                "title": str(item.get("title", "") or "")[:120],
                "emphasis": str(item.get("emphasis", "") or "")[:64] or None,
            })
        stripped = (answer[:m.start()] + answer[m.end():]).rstrip()
        return stripped, valid
    except Exception:  # noqa: BLE001
        logger.exception("LLM intent extraction failed; falling back")
        return answer, []


def _build_presentations(messages: list[Any], tool_results: list[dict[str, Any]], llm_intents: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """LLM plan first; deterministic heuristic only as conservative fallback.

    A valid LLM plan (builds >=1 spec via the deterministic engine) always
    wins. The heuristic never overrides it. If the LLM emitted nothing usable,
    fall back to the heuristic planner; if that also yields nothing, []."""
    try:
        from backend.presentation.engine import build_presentations, plan_intents
        if llm_intents:
            specs = build_presentations(tool_results, llm_intents)
            if specs:
                logger.info("presentations from LLM plan n=%d", len(specs))
                return specs
            logger.info("LLM plan built 0 specs; trying heuristic fallback")
        question = ""
        for msg in reversed(messages):
            if _is_human(msg):
                c = getattr(msg, "content", "")
                question = c if isinstance(c, str) else str(c)
                break
        intents = plan_intents(question, tool_results)
        return build_presentations(tool_results, intents)
    except Exception:  # noqa: BLE001
        logger.exception("presentation build failed; falling back to []")
        return []


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
