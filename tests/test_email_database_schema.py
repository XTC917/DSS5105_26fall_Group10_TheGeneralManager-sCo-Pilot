"""Database contract tests for email drafts and send attempts."""

from __future__ import annotations

from uuid import uuid4

import pytest
from psycopg.errors import InsufficientPrivilege, UniqueViolation
from psycopg.types.json import Jsonb

from backend.services.conversation_history import (
    create_conversation,
    delete_conversation,
)
from backend.services.pg_database import connect


@pytest.fixture(autouse=True)
def clean_email_records():
    with connect(admin=True) as connection, connection.transaction():
        connection.execute(
            """
            DELETE FROM copilot.email_send_attempts
            WHERE confirmed_by IN (1, 2)
            """
        )
        connection.execute(
            "DELETE FROM copilot.email_drafts WHERE user_id IN (1, 2)"
        )
    yield
    with connect(admin=True) as connection, connection.transaction():
        connection.execute(
            """
            DELETE FROM copilot.email_send_attempts
            WHERE confirmed_by IN (1, 2)
            """
        )
        connection.execute(
            "DELETE FROM copilot.email_drafts WHERE user_id IN (1, 2)"
        )


def _insert_draft(user_id: int, conversation_id) -> dict:
    draft_id = uuid4()
    with connect(admin=True) as connection, connection.transaction():
        row = connection.execute(
            """
            INSERT INTO copilot.email_drafts (
                id,
                user_id,
                conversation_id,
                order_id,
                recipient_email,
                from_address,
                subject,
                body,
                language,
                audience,
                content_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'en', 'customer', %s)
            RETURNING *
            """,
            (
                draft_id,
                user_id,
                conversation_id,
                "ORD-005",
                "customer@example.com",
                "operations@example.com",
                "Order update",
                "Your order is in progress.",
                "a" * 64,
            ),
        ).fetchone()
    return dict(row)


def test_email_draft_survives_conversation_deletion():
    conversation = create_conversation(1)
    draft = _insert_draft(1, conversation["id"])

    delete_conversation(1, conversation["id"])

    with connect(admin=True) as connection:
        kept = connection.execute(
            """
            SELECT id, user_id, conversation_id
            FROM copilot.email_drafts
            WHERE id = %s
            """,
            (draft["id"],),
        ).fetchone()

    assert kept is not None
    assert kept["user_id"] == 1
    assert kept["conversation_id"] is None


def test_email_send_attempt_is_unique_per_draft_version():
    conversation = create_conversation(1)
    draft = _insert_draft(1, conversation["id"])
    payload = Jsonb(
        {
            "from": "operations@example.com",
            "to": ["customer@example.com"],
            "subject": "Order update",
            "text": "Your order is in progress.",
        }
    )

    try:
        with connect(admin=True) as connection, connection.transaction():
            connection.execute(
                """
                INSERT INTO copilot.email_send_attempts (
                    id,
                    draft_id,
                    draft_version,
                    confirmed_by,
                    content_hash,
                    payload_snapshot,
                    idempotency_key
                )
                VALUES (%s, %s, 1, 1, %s, %s, %s)
                """,
                (uuid4(), draft["id"], "a" * 64, payload, "email-test-key-1"),
            )

        with pytest.raises(UniqueViolation):
            with connect(admin=True) as connection, connection.transaction():
                connection.execute(
                    """
                    INSERT INTO copilot.email_send_attempts (
                        id,
                        draft_id,
                        draft_version,
                        confirmed_by,
                        content_hash,
                        payload_snapshot,
                        idempotency_key
                    )
                    VALUES (%s, %s, 1, 1, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        draft["id"],
                        "a" * 64,
                        payload,
                        "email-test-key-2",
                    ),
                )
    finally:
        delete_conversation(1, conversation["id"])


def test_runtime_role_cannot_read_email_tables():
    with connect(admin=False) as connection:
        with pytest.raises(InsufficientPrivilege):
            connection.execute("SELECT count(*) FROM copilot.email_drafts")

    with connect(admin=False) as connection:
        with pytest.raises(InsufficientPrivilege):
            connection.execute(
                "SELECT count(*) FROM copilot.email_send_attempts"
            )
