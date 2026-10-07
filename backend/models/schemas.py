"""Pydantic request/response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    turn_count: int = 0


class ChatTurn(BaseModel):
    id: int
    conversation_id: UUID
    turn_number: int
    question: str
    answer: str
    response_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationHistory(BaseModel):
    conversation: ConversationSummary
    turns: list[ChatTurn] = Field(default_factory=list)
    next_before_turn_id: int | None = None


class ConversationMessage(BaseModel):
    id: str
    conversation_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessages(BaseModel):
    conversation: ConversationSummary
    messages: list[ConversationMessage]
    next_before_turn_id: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Manager's natural-language question")
    conversation_id: UUID = Field(
        ...,
        description="Server-created conversation owned by the authenticated user",
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
