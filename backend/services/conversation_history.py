"""Persistence operations for user-owned Manager conversations."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from backend.pg_config import COPILOT_SCHEMA
from backend.services.pg_database import connect


DEFAULT_TITLE = "New conversation"
MAX_HISTORY_LIMIT = 50
_SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

if not _SCHEMA_PATTERN.fullmatch(COPILOT_SCHEMA):
    raise RuntimeError("PG_COPILOT_SCHEMA is not a valid SQL identifier")


class ConversationNotFoundError(LookupError):
    """The conversation does not exist or is not owned by this user."""


class ActionDecisionError(ValueError):
    """The proposed action does not belong to the selected chat turn."""


class ChatAttemptStateError(RuntimeError):
    """The request attempt is missing, foreign-owned, or already completed."""


def _table(name: str) -> str:
    return f"{COPILOT_SCHEMA}.{name}"


def _public_action(action: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in action.items() if key != "_turn_id"}


def _validated_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_HISTORY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_HISTORY_LIMIT}")
    return limit


def _validated_duration(duration_ms: int) -> int:
    value = int(duration_ms)
    if value < 0:
        raise ValueError("duration_ms must not be negative")
    return value


def _title_from_question(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:80] or DEFAULT_TITLE


def create_conversation(user_id: int) -> dict[str, Any]:
    conversation_id = uuid4()
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"""
            INSERT INTO {_table('conversations')} (id, user_id)
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
                    FROM {_table('chat_turns')} AS t
                    WHERE t.conversation_id = c.id
                ) AS turn_count
            FROM {_table('conversations')} AS c
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
                    FROM {_table('chat_turns')} AS t
                    WHERE t.conversation_id = c.id
                ) AS turn_count
            FROM {_table('conversations')} AS c
            WHERE c.id = %s AND c.user_id = %s
            """,
            (conversation_id, user_id),
        ).fetchone()
    if row is None:
        raise ConversationNotFoundError
    return dict(row)


def _restore_turn_metadata(turn: dict[str, Any]) -> None:
    payload = dict(turn.get("response_json") or {})
    actions = payload.get("proposed_actions") or []
    payload["proposed_actions"] = [
        {**action, "_turn_id": turn["id"]}
        for action in actions
        if isinstance(action, dict)
    ]
    turn["response_json"] = payload


def _close_clarification_except_latest(
    turns: list[dict[str, Any]],
    *,
    keep_latest: bool,
) -> None:
    last = len(turns) - 1
    for index, turn in enumerate(turns):
        if keep_latest and index == last:
            continue
        payload = dict(turn.get("response_json") or {})
        if not payload.get("clarification"):
            continue
        payload["clarification"] = None
        turn["response_json"] = payload


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
                    FROM {_table('chat_turns')} AS counted
                    WHERE counted.conversation_id = c.id
                ) AS turn_count
            FROM {_table('conversations')} AS c
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
            FROM {_table('chat_turns')} AS t
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
    for turn in turns:
        _restore_turn_metadata(turn)
    _close_clarification_except_latest(turns, keep_latest=before_turn_id is None)
    return {
        "conversation": dict(conversation),
        "turns": turns,
        "next_before_turn_id": next_before_turn_id,
    }


def start_chat_attempt(
    user_id: int,
    conversation_id: UUID,
    *,
    question: str,
    clarification_reply: bool,
) -> dict[str, Any]:
    question = question.strip()
    if not question:
        raise ValueError("question must not be empty")

    with connect(admin=True) as conn, conn.transaction():
        owner = conn.execute(
            f"""
            SELECT id
            FROM {_table('conversations')}
            WHERE id = %s AND user_id = %s
            """,
            (conversation_id, user_id),
        ).fetchone()
        if owner is None:
            raise ConversationNotFoundError
        row = conn.execute(
            f"""
            INSERT INTO {_table('chat_attempts')} (
                conversation_id,
                question,
                clarification_reply
            )
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (conversation_id, question, clarification_reply),
        ).fetchone()
    return dict(row)


def fail_chat_attempt(
    user_id: int,
    attempt_id: int,
    *,
    duration_ms: int,
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    duration_ms = _validated_duration(duration_ms)
    error_code = error_code.strip()[:80]
    error_message = error_message.strip()[:500]
    if not error_code or not error_message:
        raise ValueError("failed attempts require a safe error code and message")

    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"""
            UPDATE {_table('chat_attempts')} AS a
            SET
                status = 'FAILED',
                completed_at = CURRENT_TIMESTAMP,
                duration_ms = %s,
                error_code = %s,
                error_message = %s
            FROM {_table('conversations')} AS c
            WHERE a.id = %s
              AND a.conversation_id = c.id
              AND c.user_id = %s
              AND a.status = 'IN_PROGRESS'
            RETURNING a.*
            """,
            (duration_ms, error_code, error_message, attempt_id, user_id),
        ).fetchone()
    if row is None:
        raise ChatAttemptStateError
    return dict(row)


def save_turn(
    user_id: int,
    conversation_id: UUID,
    *,
    question: str,
    answer: str,
    response_json: dict[str, Any] | None = None,
    attempt_id: int | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    question = question.strip()
    answer = answer.strip()
    if not question:
        raise ValueError("question must not be empty")
    if not answer:
        raise ValueError("answer must not be empty")
    if (attempt_id is None) != (duration_ms is None):
        raise ValueError("attempt_id and duration_ms must be supplied together")
    if duration_ms is not None:
        duration_ms = _validated_duration(duration_ms)

    with connect(admin=True) as conn, conn.transaction():
        owner = conn.execute(
            f"""
            SELECT id
            FROM {_table('conversations')}
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
            FROM {_table('chat_turns')}
            WHERE conversation_id = %s
            """,
            (conversation_id,),
        ).fetchone()["next_turn_number"]

        row = conn.execute(
            f"""
            INSERT INTO {_table('chat_turns')} (
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
            UPDATE {_table('chat_turns')}
            SET response_json = response_json - 'clarification'
            WHERE conversation_id = %s
              AND id <> %s
              AND response_json ? 'clarification'
            """,
            (conversation_id, row["id"]),
        )

        conn.execute(
            f"""
            UPDATE {_table('conversations')}
            SET
                title = CASE WHEN %s = 1 THEN %s ELSE title END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (turn_number, _title_from_question(question), conversation_id),
        )

        if attempt_id is not None:
            completed = conn.execute(
                f"""
                UPDATE {_table('chat_attempts')} AS a
                SET
                    status = 'SUCCEEDED',
                    completed_at = CURRENT_TIMESTAMP,
                    duration_ms = %s,
                    turn_id = %s
                FROM {_table('conversations')} AS c
                WHERE a.id = %s
                  AND a.conversation_id = c.id
                  AND c.user_id = %s
                  AND a.conversation_id = %s
                  AND a.status = 'IN_PROGRESS'
                RETURNING a.id
                """,
                (
                    duration_ms,
                    row["id"],
                    attempt_id,
                    user_id,
                    conversation_id,
                ),
            ).fetchone()
            if completed is None:
                raise ChatAttemptStateError

    return dict(row)


def get_chat_attempt(user_id: int, attempt_id: int) -> dict[str, Any]:
    with connect(admin=True) as conn:
        row = conn.execute(
            f"""
            SELECT a.*
            FROM {_table('chat_attempts')} AS a
            JOIN {_table('conversations')} AS c
              ON c.id = a.conversation_id
            WHERE a.id = %s AND c.user_id = %s
            """,
            (attempt_id, user_id),
        ).fetchone()
    if row is None:
        raise ConversationNotFoundError
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
            FROM {_table('chat_turns')} AS t
            JOIN {_table('conversations')} AS c
              ON c.id = t.conversation_id
            WHERE t.id = %s AND c.user_id = %s
            """,
            (turn_id, user_id),
        ).fetchone()
    if row is None:
        raise ConversationNotFoundError
    response_json = dict(row["response_json"] or {})
    if public_action not in (response_json.get("proposed_actions") or []):
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
            SELECT t.id, t.response_json
            FROM {_table('chat_turns')} AS t
            JOIN {_table('conversations')} AS c
              ON c.id = t.conversation_id
            WHERE t.id = %s AND c.user_id = %s
            FOR UPDATE OF t
            """,
            (turn_id, user_id),
        ).fetchone()
        if row is None:
            raise ConversationNotFoundError

        response_json = dict(row["response_json"] or {})
        if public_action not in (response_json.get("proposed_actions") or []):
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
            UPDATE {_table('chat_turns')}
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
            (Jsonb(response_json), turn_id),
        ).fetchone()
    return dict(updated)
