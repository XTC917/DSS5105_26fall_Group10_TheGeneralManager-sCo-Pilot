"""Persistent conversation history, attempts, and user isolation."""

from __future__ import annotations

from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import START, MessagesState, StateGraph
from psycopg.errors import InsufficientPrivilege

from backend.main import app
from backend.agent import graph as graph_module
from backend.services.checkpoint_store import postgres_checkpointer
from backend.services.conversation_history import (
    ConversationNotFoundError,
    create_conversation,
    fail_chat_attempt,
    get_chat_attempt,
    get_owned_conversation,
    list_conversations,
    read_history_window,
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

    assert [row["id"] for row in list_conversations(1)] == [first["id"]]
    assert [row["id"] for row in list_conversations(2)] == [second["id"]]
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


def test_history_pagination_closes_old_clarification_and_restores_decision():
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
    assert older["turns"][0]["response_json"].get("clarification") is None


def test_conversation_api_and_chat_are_authenticated(
    monkeypatch,
    employee_auth_headers,
):
    with TestClient(app) as client:
        assert client.get("/api/conversations").status_code == 401
        created = client.post(
            "/api/conversations",
            headers=employee_auth_headers,
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        admin_conversation = create_conversation(1)
        hidden = client.get(
            f"/api/conversations/{admin_conversation['id']}",
            headers=employee_auth_headers,
        )
        assert hidden.status_code == 404

        captured = {}

        def fake_run_agent(message, public_id, *, clarification_reply, thread_id):
            captured.update(
                message=message,
                public_id=public_id,
                clarification_reply=clarification_reply,
                thread_id=thread_id,
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


def test_direct_human_ai_exchange_is_checkpointed(monkeypatch):
    builder = StateGraph(MessagesState)
    builder.add_node("agent", lambda state: {})
    builder.add_edge(START, "agent")
    config = {"configurable": {"thread_id": "test:checkpoint:direct"}}

    with postgres_checkpointer() as checkpointer:
        compiled = builder.compile(checkpointer=checkpointer)
        monkeypatch.setattr(graph_module, "llm_is_configured", lambda: True)
        monkeypatch.setattr(graph_module, "get_agent", lambda: compiled)
        graph_module._append_direct_exchange(
            config["configurable"]["thread_id"],
            "Unsupported question",
            "This request is outside the supported scope.",
        )

    with postgres_checkpointer() as checkpointer:
        compiled = builder.compile(checkpointer=checkpointer)
        messages = compiled.get_state(config).values["messages"]
    assert isinstance(messages[-2], HumanMessage)
    assert isinstance(messages[-1], AIMessage)
    assert messages[-2].content == "Unsupported question"
    assert messages[-1].content == "This request is outside the supported scope."


def test_runtime_role_cannot_read_private_memory_tables(db):
    with connect(admin=False) as connection:
        row = connection.execute("SELECT count(*) AS row_count FROM app.orders").fetchone()
        assert row["row_count"] == 120
    with connect(admin=False) as connection:
        with pytest.raises(InsufficientPrivilege):
            connection.execute("SELECT count(*) FROM copilot.conversations")
