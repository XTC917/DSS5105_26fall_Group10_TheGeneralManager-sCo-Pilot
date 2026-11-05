"""Opt-in database performance check for conversation keyword search."""

from __future__ import annotations

import os
from statistics import quantiles
from time import perf_counter

import pytest

from backend.services.conversation_history import (
    create_conversation,
    delete_conversation,
    list_conversations,
)
from backend.services.pg_database import connect


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_PERFORMANCE_TESTS") != "1",
    reason="set RUN_DB_PERFORMANCE_TESTS=1 to run the 10k-turn search check",
)


def test_conversation_search_p95_is_below_half_a_second():
    user_id = 1
    conversation = create_conversation(user_id)

    try:
        with connect(admin=True) as connection, connection.transaction():
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO copilot.chat_turns (
                        conversation_id,
                        turn_number,
                        question,
                        answer,
                        response_json
                    )
                    VALUES (%s, %s, %s, %s, '{}'::jsonb)
                    """,
                    [
                        (
                            conversation["id"],
                            index + 1,
                            (
                                "unique-conversation-search-target"
                                if index == 9999
                                else f"ordinary question {index}"
                            ),
                            f"ordinary answer {index}",
                        )
                        for index in range(10000)
                    ],
                )
            connection.execute("ANALYZE copilot.chat_turns")

        durations: list[float] = []
        for _ in range(20):
            started = perf_counter()
            results = list_conversations(
                user_id,
                query="unique-conversation-search-target",
                limit=10,
            )
            durations.append(perf_counter() - started)
            assert [item["id"] for item in results] == [conversation["id"]]

        p95 = quantiles(durations, n=20)[18]
        assert p95 < 0.5, f"conversation search p95 was {p95:.3f}s"
    finally:
        delete_conversation(user_id, conversation["id"])
