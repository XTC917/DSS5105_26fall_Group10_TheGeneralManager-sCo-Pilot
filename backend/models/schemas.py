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
    clarification_reply: bool = Field(
        default=False,
        description="True when this message is the manager's answer to a clarification card.",
    )


class ToolTrace(BaseModel):
    """Enough metadata for the UI 'Why?' panel. Tools attach this to their result."""

    tool: str
    source_file: str | None = None
    filter: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    basis: str | None = None


class ConfirmActionRequest(BaseModel):
    action: dict[str, Any] = Field(..., description="proposed_action object from a chat turn")


class ConfirmActionResponse(BaseModel):
    ok: bool
    type: str | None = None
    tool: str | None = None
    summary: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    trace: dict[str, Any] | None = None
    declined: bool | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    tools_used: list[str] = Field(default_factory=list)
    traces: list[dict[str, Any]] = Field(default_factory=list)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    clarification: dict[str, Any] | None = None
    limitation: str | None = None
    routing_intent: str | None = None
