"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Manager's natural-language question")
    conversation_id: str = Field(
        default="default",
        description="Stable id so the agent can keep multi-turn context",
    )


class ToolTrace(BaseModel):
    """Enough metadata for the UI 'Why?' panel. Tools attach this to their result."""

    tool: str
    source_file: str | None = None
    filter: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    basis: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    tools_used: list[str] = Field(default_factory=list)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    limitation: str | None = None
    routing_intent: str | None = None
