"""Authenticated API routes for Manager conversation history."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.models.schemas import ConversationHistory, ConversationSummary
from backend.services.auth import CurrentUser, get_current_user
from backend.services.conversation_history import (
    ConversationNotFoundError,
    create_conversation,
    list_conversations,
    read_history_window,
)


router = APIRouter(
    prefix="/api/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_endpoint(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    return create_conversation(user.id)


@router.get(
    "",
    response_model=list[ConversationSummary],
)
def list_conversations_endpoint(
    limit: int = Query(default=50, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    return list_conversations(user.id, limit=limit)


@router.get(
    "/{conversation_id}",
    response_model=ConversationHistory,
)
def get_conversation_history_endpoint(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=50),
    before_turn_id: int | None = Query(default=None, ge=1),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        return read_history_window(
            user.id,
            conversation_id,
            limit=limit,
            before_turn_id=before_turn_id,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc