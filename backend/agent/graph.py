"""LangGraph ReAct agent: choose tools, read results, then answer."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from backend.agent.prompts import SYSTEM_PROMPT
from backend.tools.registry import MVP_TOOLS

load_dotenv()
logger = logging.getLogger(__name__)

_AGENT = None
_CHECKPOINTER = MemorySaver()


def llm_is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def build_model() -> ChatOpenAI:
    kwargs: dict[str, Any] = {
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "temperature": 0,
    }
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def get_agent():
    """Build the agent once. Requires OPENAI_API_KEY (OpenAI-compatible)."""
    global _AGENT
    if _AGENT is None:
        if not llm_is_configured():
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env. "
                "Tools can still be tested with pytest without a key."
            )
        model = build_model()
        _AGENT = create_react_agent(
            model,
            MVP_TOOLS,
            prompt=SYSTEM_PROMPT,
            checkpointer=_CHECKPOINTER,
        )
        logger.info("LangGraph agent initialised with %s tools", len(MVP_TOOLS))
    return _AGENT


def run_agent(message: str, conversation_id: str) -> dict[str, Any]:
    agent = get_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": conversation_id}},
    )
    return parse_agent_result(result, conversation_id)


def parse_agent_result(result: dict[str, Any], conversation_id: str) -> dict[str, Any]:
    messages: list[BaseMessage] = result.get("messages") or []
    tools_used: list[str] = []
    traces: list[dict[str, Any]] = []
    limitation = None

    for msg in messages:
        if isinstance(msg, ToolMessage):
            payload = _parse_json(msg.content)
            if not payload:
                continue
            tool_name = payload.get("tool") or getattr(msg, "name", None)
            if tool_name:
                tools_used.append(tool_name)
            if payload.get("trace"):
                traces.append(payload["trace"])
            error = payload.get("error") or {}
            if error.get("code") in {"UNSUPPORTED", "NOT_IMPLEMENTED"}:
                limitation = error.get("message")

    answer = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            answer = _content_to_text(msg.content)
            break
    if not answer and messages:
        answer = _content_to_text(getattr(messages[-1], "content", ""))

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
        "proposed_actions": [],
        "limitation": limitation,
    }


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
