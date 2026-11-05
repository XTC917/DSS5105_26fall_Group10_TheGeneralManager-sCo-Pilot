"""Persistent conversation history, attempts, and user isolation."""

from __future__ import annotations

from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from langgraph.graph import START, StateGraph
from psycopg.errors import InsufficientPrivilege

from backend.main import app
from backend.services.checkpoint_store import postgres_checkpointer
from backend.services.conversation_history import (
    ConversationNotFoundError,
    create_conversation,
    delete_conversation,
    fail_chat_attempt,
    get_chat_attempt,
    get_owned_conversation,
    list_conversations,
    read_history_window,
    record_clarification_choice,
    record_turn_action_decision,
    save_turn,
    start_chat_attempt,
)
from backend.services.pg_database import connect


@pytest.fixture(autouse=True)
def clean_conversations():
    with connect(admin=True) as connection, connection.transaction():
        connection.execute("DELETE FROM copilot.conversations WHERE user_id IN (1, 2)")
        connection.execute(
            "DELETE FROM copilot.checkpoint_writes WHERE thread_id LIKE 'test:%'"
        )
        connection.execute(
            "DELETE FROM copilot.checkpoint_blobs WHERE thread_id LIKE 'test:%'"
        )
        connection.execute(
            "DELETE FROM copilot.checkpoints WHERE thread_id LIKE 'test:%'"
        )
    yield
    with connect(admin=True) as connection, connection.transaction():
        connection.execute("DELETE FROM copilot.conversations WHERE user_id IN (1, 2)")
        connection.execute(
            "DELETE FROM copilot.checkpoint_writes WHERE thread_id LIKE 'test:%'"
        )
        connection.execute(
            "DELETE FROM copilot.checkpoint_blobs WHERE thread_id LIKE 'test:%'"
        )
        connection.execute(
            "DELETE FROM copilot.checkpoints WHERE thread_id LIKE 'test:%'"
        )


def test_history_and_attempts_are_user_owned():
    first = create_conversation(1)
    second = create_conversation(2)

    assert list_conversations(1) == []
    assert list_conversations(2) == []
    with pytest.raises(ConversationNotFoundError):
        get_owned_conversation(2, first["id"])

    attempt = start_chat_attempt(
        1,
        first["id"],
        question="How is ORD-120?",
        clarification_reply=False,
    )
    turn = save_turn(
        1,
        first["id"],
        question="How is ORD-120?",
        answer="ORD-120 is in progress.",
        response_json={"tools_used": ["get_order_status"]},
        attempt_id=attempt["id"],
        duration_ms=12,
    )
    completed = get_chat_attempt(1, attempt["id"])
    assert completed["status"] == "SUCCEEDED"
    assert completed["turn_id"] == turn["id"]
    assert completed["duration_ms"] == 12
    assert [row["id"] for row in list_conversations(1)] == [first["id"]]
    assert list_conversations(2) == []
    with pytest.raises(ConversationNotFoundError):
        get_chat_attempt(2, attempt["id"])

    failed = start_chat_attempt(
        1,
        first["id"],
        question="Try again",
        clarification_reply=True,
    )
    failed = fail_chat_attempt(
        1,
        failed["id"],
        duration_ms=3,
        error_code="MODEL_QUOTA",
        error_message="Chat service is temporarily unavailable.",
    )
    assert failed["status"] == "FAILED"
    assert failed["turn_id"] is None
    assert failed["error_message"] == "Chat service is temporarily unavailable."


def test_history_pagination_preserves_old_clarification_and_restores_decision():
    conversation = create_conversation(2)
    proposal = {
        "type": "create_watch",
        "order_id": "ORD-005",
        "check_date": "2026-04-02",
    }
    first = save_turn(
        2,
        conversation["id"],
        question="Which customer?",
        answer="Please choose.",
        response_json={"clarification": {"options": [{"label": "TrendCart"}]}},
    )
    second = save_turn(
        2,
        conversation["id"],
        question="TrendCart",
        answer="Please confirm.",
        response_json={"proposed_actions": [proposal]},
    )
    record_turn_action_decision(
        2,
        second["id"],
        action={**proposal, "_turn_id": second["id"]},
        status="dismissed",
        summary="Dismissed. Nothing was saved.",
    )
    third = save_turn(
        2,
        conversation["id"],
        question="What next?",
        answer="Nothing else is pending.",
    )

    page = read_history_window(2, conversation["id"], limit=2)
    assert [turn["id"] for turn in page["turns"]] == [second["id"], third["id"]]
    assert page["next_before_turn_id"] == second["id"]
    assert page["turns"][0]["response_json"]["decision"]["status"] == "dismissed"
    assert page["turns"][0]["response_json"]["proposed_actions"] == []

    older = read_history_window(
        2,
        conversation["id"],
        limit=2,
        before_turn_id=page["next_before_turn_id"],
    )
    assert [turn["id"] for turn in older["turns"]] == [first["id"]]
    assert older["turns"][0]["response_json"]["clarification"] == {
        "options": [{"label": "TrendCart"}]
    }


def test_clarification_choice_sticks_to_the_latest_unanswered_card():
    conversation = create_conversation(2)
    save_turn(
        2,
        conversation["id"],
        question="Which customer?",
        answer="Please choose.",
        response_json={"clarification": {"options": [{"label": "TrendCart"}, {"label": "Harbor Knits"}]}},
    )
    record_clarification_choice(2, conversation["id"], "TrendCart")
    record_clarification_choice(2, conversation["id"], "Harbor Knits")
    history = read_history_window(2, conversation["id"], limit=5)
    assert history["turns"][0]["response_json"]["clarification_choice"] == "TrendCart"
        admin_conversation = create_conversation(1)
        hidden = client.get(
            f"/api/conversations/{admin_conversation['id']}",
            headers=employee_auth_headers,
        )
        assert hidden.status_code == 404

        captured = {}

        def fake_run_agent(
            message,
            public_id,
            *,
            clarification_reply,
            original_question,
            thread_id,
            progress=None,
            on_token=None,
        ):
            captured.update(
                message=message,
                public_id=public_id,
                clarification_reply=clarification_reply,
                original_question=original_question,
                thread_id=thread_id,
                progress=progress,
                on_token=on_token,
            )
            return {
                "answer": "ORD-120 is in progress.",
                "conversation_id": public_id,
                "tools_used": ["get_order_status"],
                "traces": [],
                "proposed_actions": [],
                "charts": [],
                "tables": [],
            }

        monkeypatch.setattr("backend.main.llm_is_configured", lambda: True)
        monkeypatch.setattr("backend.main.run_agent", fake_run_agent)
        response = client.post(
            "/api/chat",
            headers=employee_auth_headers,
            json={"message": "How is ORD-120?", "conversation_id": conversation_id},
        )
        assert response.status_code == 200, response.text
        assert captured["thread_id"] == f"user:2:conversation:{conversation_id}"

        history = client.get(
            f"/api/conversations/{conversation_id}",
            headers=employee_auth_headers,
        )
        assert history.status_code == 200
        assert history.json()["turns"][0]["question"] == "How is ORD-120?"


def test_conversation_search_and_delete_api_are_user_owned(
    employee_auth_headers,
):
    trendcart = create_conversation(2)
    northwind = create_conversation(2)
    foreign = create_conversation(1)

    save_turn(
        2,
        trendcart["id"],
        question="Show TrendCart orders",
        answer="TrendCart has two active orders.",
    )
    save_turn(
        2,
        northwind["id"],
        question="Show Northwind orders",
        answer="Northwind has one active order.",
    )
    save_turn(
        1,
        foreign["id"],
        question="Private TrendCart conversation",
        answer="This belongs to another user.",
    )

    with TestClient(app) as client:
        searched = client.get(
            "/api/conversations",
            params={"query": "TrendCart"},
            headers=employee_auth_headers,
        )
        assert searched.status_code == 200, searched.text

        ids = {item["id"] for item in searched.json()}
        assert str(trendcart["id"]) in ids
        assert str(northwind["id"]) not in ids
        assert str(foreign["id"]) not in ids

        foreign_delete = client.delete(
            f"/api/conversations/{foreign['id']}",
            headers=employee_auth_headers,
        )
        assert foreign_delete.status_code == 404

        deleted = client.delete(
            f"/api/conversations/{trendcart['id']}",
            headers=employee_auth_headers,
        )
        assert deleted.status_code == 204
        assert deleted.content == b""

        missing = client.get(
            f"/api/conversations/{trendcart['id']}",
            headers=employee_auth_headers,
        )
        assert missing.status_code == 404


def test_failed_chat_is_recorded_without_a_fake_turn(
    monkeypatch,
    employee_auth_headers,
):
    conversation = create_conversation(2)
    monkeypatch.setattr("backend.main.llm_is_configured", lambda: False)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            headers=employee_auth_headers,
            json={
                "message": "How is ORD-120?",
                "conversation_id": str(conversation["id"]),
            },
        )
    assert response.status_code == 503
    with connect(admin=True) as connection:
        attempts = connection.execute(
            "SELECT * FROM copilot.chat_attempts WHERE conversation_id = %s",
            (conversation["id"],),
        ).fetchall()
        turns = connection.execute(
            "SELECT * FROM copilot.chat_turns WHERE conversation_id = %s",
            (conversation["id"],),
        ).fetchall()
    assert len(attempts) == 1
    assert attempts[0]["status"] == "FAILED"
    assert attempts[0]["error_code"] == "LLM_NOT_CONFIGURED"
    assert attempts[0]["duration_ms"] >= 0
    assert turns == []


class CounterState(TypedDict):
    value: int


def test_delete_conversation_removes_langgraph_checkpoint():
    conversation = create_conversation(2)
    thread_id = f"user:2:conversation:{conversation['id']}"
    config = {"configurable": {"thread_id": thread_id}}

    builder = StateGraph(CounterState)
    builder.add_node(
        "increment",
        lambda state: {"value": state.get("value", 0) + 1},
    )
    builder.add_edge(START, "increment")

    with postgres_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        assert graph.invoke({"value": 1}, config)["value"] == 2

    with connect(admin=True) as connection:
        before = {
            table: connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM copilot.{table}
                WHERE thread_id = %s
                """,
                (thread_id,),
            ).fetchone()["count"]
            for table in (
                "checkpoint_writes",
                "checkpoint_blobs",
                "checkpoints",
            )
        }

    assert before["checkpoints"] > 0

    delete_conversation(2, conversation["id"])

    with connect(admin=True) as connection:
        after = {
            table: connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM copilot.{table}
                WHERE thread_id = %s
                """,
                (thread_id,),
            ).fetchone()["count"]
            for table in (
                "checkpoint_writes",
                "checkpoint_blobs",
                "checkpoints",
            )
        }

    assert after == {
        "checkpoint_writes": 0,
        "checkpoint_blobs": 0,
        "checkpoints": 0,
    }

    with pytest.raises(ConversationNotFoundError):
        get_owned_conversation(2, conversation["id"])


def test_postgres_checkpoint_survives_pool_restart():
    builder = StateGraph(CounterState)
    builder.add_node("increment", lambda state: {"value": state.get("value", 0) + 1})
    builder.add_edge(START, "increment")
    config = {"configurable": {"thread_id": "test:checkpoint:restart"}}

    with postgres_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        assert graph.invoke({"value": 4}, config)["value"] == 5

    with postgres_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        assert graph.get_state(config).values["value"] == 5


def test_direct_answer_is_persisted_in_visible_history():
    conversation = create_conversation(2)
    turn = save_turn(
        2,
        conversation["id"],
        question="Unsupported question",
        answer="This request is outside the supported scope.",
        response_json={"limitation": "unsupported"},
    )

    history = read_history_window(2, conversation["id"])
    assert [row["id"] for row in history["turns"]] == [turn["id"]]
    assert history["turns"][0]["question"] == "Unsupported question"
    assert history["turns"][0]["answer"] == (
        "This request is outside the supported scope."
    )


def test_runtime_role_cannot_read_private_memory_tables(db):
    with connect(admin=False) as connection:
        row = connection.execute("SELECT count(*) AS row_count FROM app.orders").fetchone()
        assert row["row_count"] == 120
    with connect(admin=False) as connection:
        with pytest.raises(InsufficientPrivilege):
            connection.execute("SELECT count(*) FROM copilot.conversations")
