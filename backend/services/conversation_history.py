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


def discard_unused_conversations(user_id: int, keep: list[UUID] | None = None) -> None:
    """Drop conversations that never received a question.

    A conversation stays if a question is still being answered, or if the
    caller just submitted one and asked to keep that id.
    """
    keep_ids = list(dict.fromkeys(str(item) for item in (keep or [])))
    keep_clause = ""
    params: list[Any] = [user_id]
    if keep_ids:
        keep_clause = "AND c.id::text <> ALL(%s)"
        params.append(keep_ids)
    with connect(admin=True) as conn, conn.transaction():
        unused = conn.execute(
            f"""
            SELECT id
            FROM {_table('conversations')} AS c
            WHERE c.user_id = %s
              AND NOT EXISTS (
                    SELECT 1
                    FROM {_table('chat_turns')} AS t
                    WHERE t.conversation_id = c.id
              )
              AND NOT EXISTS (
                    SELECT 1
                    FROM {_table('chat_attempts')} AS a
                    WHERE a.conversation_id = c.id
                      AND a.status = 'IN_PROGRESS'
              )
              {keep_clause}
            """,
            tuple(params),
        ).fetchall()
        for row in unused:
            thread_id = f"user:{user_id}:conversation:{row['id']}"
            for table_name in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                conn.execute(
                    f"DELETE FROM {_table(table_name)} WHERE thread_id = %s",
                    (thread_id,),
                )
            conn.execute(
                f"DELETE FROM {_table('conversations')} WHERE id = %s AND user_id = %s",
                (row["id"], user_id),
            )


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
    query: str | None = None,
) -> list[dict[str, Any]]:
    limit = _validated_limit(limit)
    query = (query or "").strip()
    search_clause = ""
    params: list[Any] = [user_id]
    if query:
        pattern = f"%{query}%"
        search_clause = f"""
            AND (
             c.title ILIKE %s
                OR EXISTS (
                    SELECT 1
                    FROM {_table('chat_turns')} AS searched
                    WHERE searched.conversation_id = c.id
                    AND (
                          searched.question ILIKE %s
                        OR searched.answer ILIKE %s
                    )
                )
            )
    """
        params.extend([pattern, pattern, pattern])
    params.append(limit)
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
                ) AS turn_count,
                EXISTS (
                    SELECT 1
                    FROM {_table('chat_attempts')} AS running
                    WHERE running.conversation_id = c.id
                      AND running.status = 'IN_PROGRESS'
                ) AS in_progress
            FROM {_table('conversations')} AS c
            WHERE c.user_id = %s
              AND (
                    EXISTS (
                        SELECT 1
                        FROM {_table('chat_turns')} AS asked
                        WHERE asked.conversation_id = c.id
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM {_table('chat_attempts')} AS running
                        WHERE running.conversation_id = c.id
                          AND running.status = 'IN_PROGRESS'
                    )
              )
            {search_clause}
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT %s
            """,
            tuple(params),
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


def delete_conversation(
    user_id: int,
    conversation_id: UUID,
) -> None:
    thread_id = f"user:{user_id}:conversation:{conversation_id}"

    with connect(admin=True) as conn, conn.transaction():
        owned = conn.execute(
            f"""
            SELECT id
            FROM {_table('conversations')}
            WHERE id = %s AND user_id = %s
            FOR UPDATE
            """,
            (conversation_id, user_id),
        ).fetchone()

        if owned is None:
            raise ConversationNotFoundError

        for table_name in (
            "checkpoint_writes",
            "checkpoint_blobs",
            "checkpoints",
        ):
            conn.execute(
                f"""
                DELETE FROM {_table(table_name)}
                WHERE thread_id = %s
                """,
                (thread_id,),
            )

        conn.execute(
            f"""
            DELETE FROM {_table('conversations')}
            WHERE id = %s AND user_id = %s
            """,
            (conversation_id, user_id),
        )


def _restore_turn_metadata(turn: dict[str, Any]) -> None:
    payload = dict(turn.get("response_json") or {})
    actions = payload.get("proposed_actions") or []
    payload["proposed_actions"] = [
        {**action, "_turn_id": turn["id"]}
        for action in actions
        if isinstance(action, dict)
    ]
    turn["response_json"] = payload


def recent_turn_memory(conversation_id: UUID, *, limit: int = 3) -> str:
    """Question and answer text from the last saved turns, oldest first."""
    if limit < 1:
        return ""
    with connect(admin=True) as conn:
        rows = conn.execute(
            f"""
            SELECT question, answer
            FROM {_table('chat_turns')}
            WHERE conversation_id = %s
            ORDER BY id DESC
            LIMIT %s
            """,
            (conversation_id, limit),
        ).fetchall()
    lines: list[str] = []
    for row in reversed(rows):
        question = " ".join(str(row["question"] or "").split())[:500]
        answer = " ".join(str(row["answer"] or "").split())[:800]
        if question:
            lines.append(f"Manager: {question}")
        if answer:
            lines.append(f"Co-Pilot: {answer}")
    return "\n".join(lines)


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
        if not clarification_reply:
            conn.execute(
                f"""
                UPDATE {_table('conversations')}
                SET
                    title = CASE WHEN title = %s THEN %s ELSE title END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (
                    DEFAULT_TITLE,
                    _title_from_question(question),
                    conversation_id,
                    user_id,
                ),
            )
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


def record_clarification_choice(
    user_id: int,
    conversation_id: UUID,
    choice: str,
) -> None:
    """Remember which clarification option the manager already chose.

    Only the latest unanswered card in this conversation is updated.
    """
    choice = choice.strip()
    if not choice:
        return
    with connect(admin=True) as conn, conn.transaction():
        conn.execute(
            f"""
            UPDATE {_table('chat_turns')} AS t
            SET response_json = jsonb_set(
                COALESCE(t.response_json, '{{}}'::jsonb),
                '{{clarification_choice}}',
                to_jsonb(%s::text),
                true
            )
            FROM {_table('conversations')} AS c
            WHERE t.conversation_id = c.id
              AND c.user_id = %s
              AND t.conversation_id = %s
              AND t.response_json -> 'clarification' IS NOT NULL
              AND jsonb_typeof(t.response_json -> 'clarification') = 'object'
              AND NOT (t.response_json ? 'clarification_choice')
              AND t.id = (
                SELECT id
                FROM {_table('chat_turns')}
                WHERE conversation_id = %s
                  AND response_json -> 'clarification' IS NOT NULL
                  AND jsonb_typeof(response_json -> 'clarification') = 'object'
                  AND NOT (response_json ? 'clarification_choice')
                ORDER BY turn_number DESC
                LIMIT 1
              )
            """,
            (choice, user_id, conversation_id, conversation_id),
        )


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
    if not _action_belongs_to_turn(response_json, public_action):
        raise ActionDecisionError(
            "The proposed action does not belong to this chat turn"
        )
    return public_action


def _stored_offer_action(response_json: dict[str, Any]) -> dict[str, Any] | None:
    offer = response_json.get("action_offer")
    if not isinstance(offer, dict) or not isinstance(offer.get("action"), dict):
        return None
    return _public_action(offer["action"])


def _action_belongs_to_turn(response_json: dict[str, Any], public_action: dict[str, Any]) -> bool:
    if public_action in (response_json.get("proposed_actions") or []):
        return True
    return _stored_offer_action(response_json) == public_action


def attach_action_offer(user_id: int, turn_id: int, offer: dict[str, Any]) -> None:
    """Store the automatic watch or email suggestion on the turn that produced it."""
    prompt = str(offer.get("prompt") or "").strip()
    action = offer.get("action")
    if not prompt or not isinstance(action, dict):
        raise ValueError("An action offer needs a prompt and an action")
    stored = {"prompt": prompt, "action": _public_action(action)}
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"""
            SELECT t.response_json
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
        response_json["action_offer"] = stored
        conn.execute(
            f"UPDATE {_table('chat_turns')} SET response_json = %s WHERE id = %s",
            (Jsonb(response_json), turn_id),
        )


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
        if not _action_belongs_to_turn(response_json, public_action):
            raise ActionDecisionError(
                "The proposed action does not belong to this chat turn"
            )
        if public_action in (response_json.get("proposed_actions") or []):
            response_json["proposed_actions"] = []
            response_json["decision"] = {
                "status": status,
                "summary": summary,
                "action": public_action,
            }
        if _stored_offer_action(response_json) == public_action:
            response_json["action_offer_decision"] = {
                "status": status,
                "summary": summary,
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
