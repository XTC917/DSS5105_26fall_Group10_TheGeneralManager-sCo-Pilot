"""LangGraph agent state.

create_react_agent already uses a messages list. This module documents the
fields we care about if we later replace the prebuilt agent with a custom graph.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    # Populated after the run for the API / UI — not required by LangGraph itself.
    tools_used: list[str]
    traces: list[dict[str, Any]]
