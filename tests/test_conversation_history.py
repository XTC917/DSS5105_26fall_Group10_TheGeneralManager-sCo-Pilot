"""KAN-35 integration tests against the migrated PostgreSQL test database.

Agent responses are deterministic doubles; persistence, ownership, HTTP auth,
transactions, pagination and LangGraph checkpoints use their real code paths.
"""
from __future__ import annotations

from typing import Annotated, TypedDict
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

import backend.main as main
from backend.services import conversation_history as history
from backend.services.checkpoint_store import postgres_checkpointer
from backend.services.pg_database import connect
from backend.services.request_context import get_current_user_id


@pytest.fixture
def conversations(db):
    owned = history.create_conversation(2)
    other = history.create_conversation(1)
    yield owned, other
    with connect(admin=True) as conn:
        conn.execute("DELETE FROM copilot.conversations WHERE id = ANY(%s)", ([owned["id"], other["id"]],))


def test_persist_pair_metadata_order_and_reload(conversations):
    owned, _ = conversations
    meta = {"tools_used": ["get_order_status"], "traces": [{"tool": "get_order_status"}],
            "routing_intent": "proceed", "limitation": None, "tables": [{"title": "Orders"}],
            "charts": [{"type": "bar"}], "proposed_actions": [{"type": "add_order_note"}]}
    first = history.save_turn(2, owned["id"], question="How is ORD-120 doing?", answer="Stored answer", response_json=meta)
    history.save_turn(2, owned["id"], question="Follow up", answer="Second answer")
    # Each read opens a new PostgreSQL connection; no frontend/runtime cache.
    restored = history.read_history_window(2, owned["id"])
    assert [turn["turn_number"] for turn in restored["turns"]] == [1, 2]
    assert [turn["question"] for turn in restored["turns"]] == ["How is ORD-120 doing?", "Follow up"]
    assert [turn["answer"] for turn in restored["turns"]] == ["Stored answer", "Second answer"]
    assert restored["turns"][0]["id"] == first["id"]
    assert restored["turns"][0]["response_json"] == meta
    assert restored["conversation"]["turn_count"] == 2
    assert restored["conversation"]["title"] == "How is ORD-120 doing?"
    assert restored["conversation"]["updated_at"] >= owned["updated_at"]


def test_pagination_preserves_all_turns_and_closes_old_clarification(conversations):
    owned, _ = conversations
    ids = []
    for i in range(53):
        ids.append(history.save_turn(2, owned["id"], question=f"Question {i}", answer=f"Answer {i}",
                                    response_json={"clarification": {"options": [{"label": str(i)}]}})["id"])
    newest = history.read_history_window(2, owned["id"])
    assert len(newest["turns"]) == 50
    assert newest["next_before_turn_id"] == ids[3]
    assert newest["turns"][-1]["response_json"]["clarification"] is not None
    assert all(not turn["response_json"].get("clarification") for turn in newest["turns"][:-1])
    older = history.read_history_window(2, owned["id"], before_turn_id=newest["next_before_turn_id"])
    assert older["next_before_turn_id"] is None
    assert [turn["id"] for turn in older["turns"] + newest["turns"]] == ids
    assert all(not turn["response_json"].get("clarification") for turn in older["turns"])


def test_owner_and_latest_conversation_order(conversations):
    owned, other = conversations
    history.save_turn(2, owned["id"], question="Latest", answer="Answer")
    items = history.list_conversations(2)
    assert items[0]["id"] == owned["id"]
    assert all(item["user_id"] == 2 and item["id"] != other["id"] for item in items)


@pytest.mark.parametrize("operation", ["get", "read", "save"])
def test_cross_user_service_access_denied(conversations, operation):
    owned, _ = conversations
    with pytest.raises(history.ConversationNotFoundError):
        if operation == "get":
            history.get_owned_conversation(1, owned["id"])
        elif operation == "read":
            history.read_history_window(1, owned["id"])
        else:
            history.save_turn(1, owned["id"], question="Intrusion", answer="No")


def test_invalid_turn_rolls_back_without_partial_messages(conversations):
    owned, _ = conversations
    with pytest.raises(ValueError):
        history.save_turn(2, owned["id"], question="Question", answer=" ")
    with pytest.raises(TypeError):
        history.save_turn(2, owned["id"], question="Question", answer="Answer", response_json={"bad": object()})
    assert history.read_history_window(2, owned["id"])["turns"] == []
    assert history.get_owned_conversation(2, owned["id"])["title"] == "New conversation"


def test_conversation_fk_and_cascade(conversations):
    owned, _ = conversations
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        history.create_conversation(-12345)
    history.save_turn(2, owned["id"], question="Q", answer="A")
    with connect(admin=True) as conn:
        conn.execute("DELETE FROM copilot.conversations WHERE id=%s AND user_id=2", (owned["id"],))
        assert conn.execute("SELECT COUNT(*) AS n FROM copilot.chat_turns WHERE conversation_id=%s", (owned["id"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("method,path", [("GET", "/api/conversations"), ("POST", "/api/conversations"),
    ("GET", f"/api/conversations/{uuid4()}"), ("GET", f"/api/conversations/{uuid4()}/messages"),
    ("POST", "/api/chat")])
def test_history_and_chat_require_authentication(method, path):
    with TestClient(main.app) as client:
        res = client.request(method, path, json={"message": "Q", "conversation_id": str(uuid4())})
        assert res.status_code == 401


def test_http_user_isolation_and_client_owner_not_trusted(conversations, employee_auth_headers, admin_auth_headers, monkeypatch):
    owned, other = conversations
    calls = []
    monkeypatch.setattr(main, "llm_is_configured", lambda: True)
    def agent(message, conversation_id, **kwargs):
        calls.append((message, conversation_id, kwargs, get_current_user_id()))
        return {"answer": "Factory answer", "conversation_id": conversation_id,
                "tools_used": ["get_order_status"], "traces": [], "proposed_actions": []}
    monkeypatch.setattr(main, "run_agent", agent)
    with TestClient(main.app) as client:
        assert client.get(f"/api/conversations/{owned['id']}", headers=admin_auth_headers).status_code == 404
        assert client.get(f"/api/conversations/{owned['id']}/messages", headers=admin_auth_headers).status_code == 404
        denied = client.post("/api/chat", headers=employee_auth_headers,
            json={"message": "Attack", "conversation_id": str(other["id"]), "user_id": 1})
        assert denied.status_code == 404
        assert calls == []
        res = client.post("/api/chat", headers=employee_auth_headers,
            json={"message": "How is ORD-120 doing?", "conversation_id": str(owned["id"]), "user_id": 1, "clarification_reply": True})
        assert res.status_code == 200, res.text
        assert res.json()["answer"] == "Factory answer"
        assert calls[0][2] == {"clarification_reply": True, "thread_id": f"user:2:conversation:{owned['id']}"}
        assert calls[0][3] == 2
        messages = client.get(f"/api/conversations/{owned['id']}/messages", headers=employee_auth_headers).json()["messages"]
        assert [msg["role"] for msg in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "How is ORD-120 doing?"
        assert messages[1]["metadata"]["tools_used"] == ["get_order_status"]
        assert client.get(f"/api/conversations/{uuid4()}", headers=employee_auth_headers).status_code == 404
    # A new HTTP client/application lifespan restores the same persisted history.
    with TestClient(main.app) as client:
        restored = client.get(f"/api/conversations/{owned['id']}", headers=employee_auth_headers)
        assert restored.status_code == 200
        assert restored.json()["turns"][0]["answer"] == "Factory answer"


@pytest.mark.parametrize("failure,expected", [(RuntimeError("agent failed"), 500),
                                             (psycopg.OperationalError("private database details"), 503)])
def test_failed_chat_is_not_persisted(conversations, employee_auth_headers, monkeypatch, failure, expected):
    owned, _ = conversations
    monkeypatch.setattr(main, "llm_is_configured", lambda: True)
    def fail(*args, **kwargs):
        raise failure
    if expected == 500:
        monkeypatch.setattr(main, "run_agent", fail)
    else:
        monkeypatch.setattr(main, "run_agent", lambda *args, **kwargs: {"answer": "Good answer", "conversation_id": str(owned["id"])})
        monkeypatch.setattr(main, "save_turn", fail)
    with TestClient(main.app) as client:
        res = client.post("/api/chat", headers=employee_auth_headers, json={"message": "Q", "conversation_id": str(owned["id"])})
        assert res.status_code == expected
        assert str(failure) not in res.text
        assert client.get(f"/api/conversations/{owned['id']}", headers=employee_auth_headers).json()["turns"] == []


def test_malformed_agent_response_not_saved(conversations, employee_auth_headers, monkeypatch):
    owned, _ = conversations
    monkeypatch.setattr(main, "llm_is_configured", lambda: True)
    monkeypatch.setattr(main, "run_agent", lambda *args, **kwargs: {"answer": "Answer", "conversation_id": str(owned["id"]), "tools_used": "invalid"})
    with TestClient(main.app) as client:
        res = client.post("/api/chat", headers=employee_auth_headers, json={"message": "Q", "conversation_id": str(owned["id"])})
        assert res.status_code == 500
    assert history.read_history_window(2, owned["id"])["turns"] == []


def test_restored_action_ownership_and_decision(conversations):
    owned, _ = conversations
    action = {"type": "add_order_note", "order_id": "ORD-120", "note": "Follow up"}
    saved = history.save_turn(2, owned["id"], question="Q", answer="A", response_json={"proposed_actions": [action]})
    tagged = {**action, "_turn_id": saved["id"]}
    with pytest.raises(history.ConversationNotFoundError):
        history.validate_turn_action(1, saved["id"], action=tagged)
    assert history.validate_turn_action(2, saved["id"], action=tagged) == action
    with pytest.raises(history.ActionDecisionError):
        history.validate_turn_action(2, saved["id"], action={**tagged, "note": "tampered"})
    history.record_turn_action_decision(2, saved["id"], action=tagged, status="dismissed", summary="Dismissed")
    restored = history.read_history_window(2, owned["id"])["turns"][0]["response_json"]
    assert restored["decision"]["status"] == "dismissed"
    assert restored["proposed_actions"] == []
    with pytest.raises(history.ActionDecisionError):
        history.validate_turn_action(2, saved["id"], action=tagged)


def test_database_readonly_roles_cannot_read_chat_or_checkpoints(db):
    with connect(admin=True) as conn:
        for role in ("factory_reader", "factory_user", "factory_agent"):
            for table in ("conversations", "chat_turns", "checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"):
                result = conn.execute("SELECT has_table_privilege(%s, %s, 'SELECT') AS allowed", (role, f"copilot.{table}")).fetchone()
                assert result["allowed"] is False


def test_checkpoint_restart_and_thread_isolation(db):
    class State(TypedDict):
        messages: Annotated[list, add_messages]
    builder = StateGraph(State)
    builder.add_node("reply", lambda state: {"messages": [AIMessage(content=f"Messages seen: {len(state['messages'])}")]})
    builder.add_edge(START, "reply")
    builder.add_edge("reply", END)
    thread = f"user:2:conversation:{uuid4()}"
    config = {"configurable": {"thread_id": thread}}
    try:
        with postgres_checkpointer() as saver:
            graph = builder.compile(checkpointer=saver)
            graph.invoke({"messages": [HumanMessage(content="How is ORD-120 doing?")]}, config)
        with postgres_checkpointer() as saver:
            graph = builder.compile(checkpointer=saver)
            result = graph.invoke({"messages": [HumanMessage(content="Follow up")]}, config)
            assert len(result["messages"]) == 4
            assert result["messages"][0].content == "How is ORD-120 doing?"
            assert graph.get_state({"configurable": {"thread_id": thread.replace("user:2:", "user:1:")}}).values == {}
    finally:
        with connect(admin=True) as conn:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                conn.execute(f"DELETE FROM copilot.{table} WHERE thread_id=%s", (thread,))


def test_prior_tool_context_loaded_after_agent_restart(monkeypatch):
    from types import SimpleNamespace
    from backend.agent import graph
    tool = ToolMessage(content='{"tool":"get_order_status","data":{"order_id":"ORD-120"}}', tool_call_id="test")
    fake = SimpleNamespace(get_state=lambda config: SimpleNamespace(values={"messages": [HumanMessage(content="ORD-120"), tool]}))
    monkeypatch.setattr(graph, "_AGENT", None)
    monkeypatch.setattr(graph, "llm_is_configured", lambda: True)
    monkeypatch.setattr(graph, "get_agent", lambda: fake)
    assert "ORD-120" in graph._prior_tool_json("user:2:conversation:test")
    assert graph._previous_turn_order_ids("user:2:conversation:test") == ["ORD-120"]


def test_http_creation_uses_authenticated_owner(conversations, employee_auth_headers):
    _, other = conversations
    created_id = None
    try:
        with TestClient(main.app) as client:
            created = client.post("/api/conversations", headers=employee_auth_headers, json={"user_id": 1})
            assert created.status_code == 201
            created_id = created.json()["id"]
            assert history.get_owned_conversation(2, created_id)["user_id"] == 2
            listing = client.get("/api/conversations", headers=employee_auth_headers)
            assert listing.status_code == 200
            assert listing.json()[0]["id"] == created_id
            assert str(other["id"]) not in [item["id"] for item in listing.json()]
    finally:
        if created_id:
            with connect(admin=True) as conn:
                conn.execute("DELETE FROM copilot.conversations WHERE id=%s AND user_id=2", (created_id,))


def test_history_database_failure_is_clean_503(employee_auth_headers, monkeypatch):
    from backend.routers import conversations as routes
    def unavailable(*args, **kwargs):
        raise psycopg.OperationalError("private connection details")
    monkeypatch.setattr(routes, "list_conversations", unavailable)
    with TestClient(main.app) as client:
        response = client.get("/api/conversations", headers=employee_auth_headers)
        assert response.status_code == 503
        assert "private connection details" not in response.text


def test_existing_routing_and_authenticated_audit(conversations, employee_auth_headers, monkeypatch):
    import re
    owned, _ = conversations
    # The repository's intercept keywords are opt-in, as in test_routing.py.
    monkeypatch.setattr("backend.agent.routing._FINANCIAL", re.compile(r"revenues?", re.I))
    monkeypatch.setattr(main, "llm_is_configured", lambda: True)
    with TestClient(main.app) as client:
        response = client.post("/api/chat", headers=employee_auth_headers,
            json={"message": "What is the revenue from TrendCart?", "conversation_id": str(owned["id"])})
        assert response.status_code == 200
        assert response.json()["limitation"]
        assert response.json()["tools_used"] == []
    with connect(admin=True) as conn:
        rows = conn.execute("SELECT user_id,event_type FROM copilot.audit_log WHERE conversation_id=%s", (str(owned["id"]),)).fetchall()
        assert rows and all(row["user_id"] == 2 for row in rows)
        assert rows[0]["event_type"] == "short_circuit"
        conn.execute("DELETE FROM copilot.audit_log WHERE conversation_id=%s AND user_id=2", (str(owned["id"]),))
