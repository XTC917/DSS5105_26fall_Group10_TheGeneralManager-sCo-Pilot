"""Authenticated API routes for Manager conversation history."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Error as DatabaseError

from backend.models.schemas import ConversationHistory, ConversationMessages, ConversationSummary
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


@contextmanager
def history_errors():
    try:
        yield
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except DatabaseError as exc:
        logging.getLogger(__name__).exception("conversation history unavailable")
        raise HTTPException(status_code=503, detail="Conversation history is unavailable. Please try again.") from exc


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_endpoint(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    with history_errors():
        return create_conversation(user.id)


@router.get(
    "",
    response_model=list[ConversationSummary],
)
def list_conversations_endpoint(
    limit: int = Query(default=50, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    with history_errors():
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
    with history_errors():
        return read_history_window(
            user.id,
            conversation_id,
            limit=limit,
            before_turn_id=before_turn_id,
        )


@router.get("/{conversation_id}/messages", response_model=ConversationMessages)
def get_conversation_messages_endpoint(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=50),
    before_turn_id: int | None = Query(default=None, ge=1),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Expose both message roles without duplicating the existing chat_turns store."""
    with history_errors():
        history = read_history_window(user.id, conversation_id, limit=limit, before_turn_id=before_turn_id)
        messages = []
        for turn in history["turns"]:
            for role, content in (("user", turn["question"]), ("assistant", turn["answer"])):
                messages.append({
                    "id": f"{turn['id']}:{role}",
                    "conversation_id": turn["conversation_id"],
                    "role": role,
                    "content": content,
                    "created_at": turn["created_at"],
                    "metadata": turn["response_json"] if role == "assistant" else {},
                })
        return {"conversation": history["conversation"], "messages": messages,
                "next_before_turn_id": history["next_before_turn_id"]}
