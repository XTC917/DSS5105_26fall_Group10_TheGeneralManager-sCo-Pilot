"""Persistence operations for user-owned Manager conversations."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


DEFAULT_TITLE = "New conversation"
MAX_HISTORY_LIMIT = 50


class ConversationNotFoundError(LookupError):
    """The conversation does not exist or is not owned by this user."""


class ActionDecisionError(ValueError):
    """The proposed action does not belong to the selected chat turn."""


def _public_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in action.items()
        if key != "_turn_id"
    }


def _validated_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_HISTORY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")
    return limit


def _title_from_question(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:80] or DEFAULT_TITLE


def create_conversation(user_id: int) -> dict[str, Any]:
    conversation_id = uuid4()

    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"""
            INSERT INTO {COPILOT_SCHEMA}.conversations (id, user_id)
            VALUES (%s, %s)
            RETURNING id, user_id, title, created_at, updated_at
            """,
            (conversation_id, user_id),
        ).fetchone()

    return dict(row)


def list_conversations(
    user_id: int,
    *,
    limit: int = MAX_HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    limit = _validated_limit(limit)

    with connect(admin=True) as conn:
        rows = conn.execute(
            f"""
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                (
                    SELECT COUNT(*)::INTEGER
                    FROM {COPILOT_SCHEMA}.chat_turns AS t
                    WHERE t.conversation_id = c.id
                ) AS turn_count
            FROM {COPILOT_SCHEMA}.conversations AS c
            WHERE c.user_id = %s
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_owned_conversation(
    user_id: int,
    conversation_id: UUID,
) -> dict[str, Any]:
    with connect(admin=True) as conn:
        row = conn.execute(
            f"""
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                (
                    SELECT COUNT(*)::INTEGER
                    FROM {COPILOT_SCHEMA}.chat_turns AS t
                    WHERE t.conversation_id = c.id
                ) AS turn_count
            FROM {COPILOT_SCHEMA}.conversations AS c
            WHERE c.id = %s AND c.user_id = %s
            """,
            (conversation_id, user_id),
        ).fetchone()

    if row is None:
        raise ConversationNotFoundError

    return dict(row)


def read_history_window(
    user_id: int,
    conversation_id: UUID,
    *,
    limit: int = MAX_HISTORY_LIMIT,
    before_turn_id: int | None = None,
) -> dict[str, Any]:
    limit = _validated_limit(limit)

    if before_turn_id is not None and before_turn_id < 1:
        raise ValueError("before_turn_id must be positive")

    with connect(admin=True) as conn, conn.transaction():
        conversation = conn.execute(
            f"""
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                (
                    SELECT COUNT(*)::INTEGER
                    FROM {COPILOT_SCHEMA}.chat_turns AS counted
                    WHERE counted.conversation_id = c.id
                ) AS turn_count
            FROM {COPILOT_SCHEMA}.conversations AS c
            WHERE c.id = %s AND c.user_id = %s
            """,
            (conversation_id, user_id),
        ).fetchone()

        if conversation is None:
            raise ConversationNotFoundError

        cursor_clause = ""
        params: list[Any] = [conversation_id]

        if before_turn_id is not None:
            cursor_clause = "AND t.id < %s"
            params.append(before_turn_id)

        params.append(limit + 1)

        rows = conn.execute(
            f"""
            SELECT
                t.id,
                t.conversation_id,
                t.turn_number,
                t.question,
                t.answer,
                t.response_json,
                t.created_at
            FROM {COPILOT_SCHEMA}.chat_turns AS t
            WHERE t.conversation_id = %s
              {cursor_clause}
            ORDER BY t.id DESC
            LIMIT %s
            """,
            tuple(params),
        ).fetchall()

    has_more = len(rows) > limit
    selected = rows[:limit]

    next_before_turn_id = None
    if has_more and selected:
        next_before_turn_id = int(selected[-1]["id"])

    turns = [dict(row) for row in reversed(selected)]
    _close_clarification_except_latest(turns, keep_latest=before_turn_id is None)

    return {
        "conversation": dict(conversation),
        "turns": turns,
        "next_before_turn_id": next_before_turn_id,
    }


def _close_clarification_except_latest(turns: list[dict[str, Any]], *, keep_latest: bool) -> None:
    """A clarification stays open only on the newest turn."""
    last = len(turns) - 1
    for index, turn in enumerate(turns):
        if keep_latest and index == last:
            continue
        payload = dict(turn.get("response_json") or {})
        if not payload.get("clarification"):
            continue
        payload["clarification"] = None
        turn["response_json"] = payload


def save_turn(
    user_id: int,
    conversation_id: UUID,
    *,
    question: str,
    answer: str,
    response_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    question = question.strip()
    answer = answer.strip()

    if not question:
        raise ValueError("question must not be empty")
    if not answer:
        raise ValueError("answer must not be empty")

    with connect(admin=True) as conn, conn.transaction():
        owner = conn.execute(
            f"""
            SELECT id
            FROM {COPILOT_SCHEMA}.conversations
            WHERE id = %s AND user_id = %s
            FOR UPDATE
            """,
            (conversation_id, user_id),
        ).fetchone()

        if owner is None:
            raise ConversationNotFoundError

        turn_number = conn.execute(
            f"""
            SELECT COALESCE(MAX(turn_number), 0) + 1 AS next_turn_number
            FROM {COPILOT_SCHEMA}.chat_turns
            WHERE conversation_id = %s
            """,
            (conversation_id,),
        ).fetchone()["next_turn_number"]

        row = conn.execute(
            f"""
            INSERT INTO {COPILOT_SCHEMA}.chat_turns (
                conversation_id,
                turn_number,
                question,
                answer,
                response_json
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING
                id,
                conversation_id,
                turn_number,
                question,
                answer,
                response_json,
                created_at
            """,
            (
                conversation_id,
                turn_number,
                question,
                answer,
                Jsonb(response_json or {}),
            ),
        ).fetchone()

        conn.execute(
            f"""
            UPDATE {COPILOT_SCHEMA}.chat_turns
            SET response_json = response_json - 'clarification'
            WHERE conversation_id = %s
              AND id <> %s
              AND response_json ? 'clarification'
            """,
            (conversation_id, row["id"]),
        )

        conn.execute(
            f"""
            UPDATE {COPILOT_SCHEMA}.conversations
            SET
                title = CASE
                    WHEN %s = 1 THEN %s
                    ELSE title
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                turn_number,
                _title_from_question(question),
                conversation_id,
            ),
        )

    return dict(row)


def validate_turn_action(
    user_id: int,
    turn_id: int,
    *,
    action: dict[str, Any],
) -> dict[str, Any]:
    public_action = _public_action(action)

    with connect(admin=True) as conn:
        row = conn.execute(
            f"""
            SELECT t.response_json
            FROM {COPILOT_SCHEMA}.chat_turns AS t
            JOIN {COPILOT_SCHEMA}.conversations AS c
              ON c.id = t.conversation_id
            WHERE t.id = %s
              AND c.user_id = %s
            """,
            (
                turn_id,
                user_id,
            ),
        ).fetchone()

    if row is None:
        raise ConversationNotFoundError

    response_json = dict(row["response_json"] or {})
    proposed_actions = response_json.get("proposed_actions") or []

    if public_action not in proposed_actions:
        raise ActionDecisionError(
            "The proposed action does not belong to this chat turn"
        )

    return public_action


def record_turn_action_decision(
    user_id: int,
    turn_id: int,
    *,
    action: dict[str, Any],
    status: str,
    summary: str,
) -> dict[str, Any]:
    if status not in {"confirmed", "dismissed"}:
        raise ValueError("status must be confirmed or dismissed")

    public_action = _public_action(action)

    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"""
            SELECT
                t.id,
                t.response_json
            FROM {COPILOT_SCHEMA}.chat_turns AS t
            JOIN {COPILOT_SCHEMA}.conversations AS c
              ON c.id = t.conversation_id
            WHERE t.id = %s
              AND c.user_id = %s
            FOR UPDATE OF t
            """,
            (turn_id, user_id),
        ).fetchone()

        if row is None:
            raise ConversationNotFoundError

        response_json = dict(row["response_json"] or {})
        proposed_actions = response_json.get("proposed_actions") or []

        if public_action not in proposed_actions:
            raise ActionDecisionError(
                "The proposed action does not belong to this chat turn"
            )

        response_json["proposed_actions"] = []
        response_json["decision"] = {
            "status": status,
            "summary": summary,
            "action": public_action,
        }

        updated = conn.execute(
            f"""
            UPDATE {COPILOT_SCHEMA}.chat_turns
            SET response_json = %s
            WHERE id = %s
            RETURNING
                id,
                conversation_id,
                turn_number,
                question,
                answer,
                response_json,
                created_at
            """,
            (
                Jsonb(response_json),
                turn_id,
            ),
        ).fetchone()

    return dict(updated)