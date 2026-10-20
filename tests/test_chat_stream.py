"""KAN-47 transport tests, independent of history tables and checkpoint stores."""
import json
import pytest
from fastapi.testclient import TestClient
import backend.main as main
from backend.services.auth import CurrentUser, get_current_user
from backend.services.request_context import get_current_user_id


def _user(identity):
    return CurrentUser(id=identity, username=f"test-{identity}", email=None, role="EMPLOYEE", status="ACTIVE")


@pytest.fixture
def client(monkeypatch):
    main.app.dependency_overrides[get_current_user] = lambda: _user(2)
    monkeypatch.setattr(main, "llm_is_configured", lambda: True)
    # No lifespan/database needed: requests exercise transport and model doubles.
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _events(text):
    return [(part.splitlines()[0][7:], json.loads(part.split('data: ', 1)[1]))
            for part in text.strip().split('\n\n') if part.startswith('event: ')]


def test_progress_precedes_validated_result_and_agent_is_called_once(client, monkeypatch):
    calls = []
    def agent(message, session_id, **kwargs):
        assert get_current_user_id() == 2
        calls.append(session_id)
        kwargs['progress']('Reading the order record…')
        return {'answer': 'ORD-108 is in assembly.', 'conversation_id': session_id,
                'traces': [{'tool': 'get_order_status', 'source_file': 'orders.csv',
                            'rows': [{'order_id': 'ORD-108', 'current_stage': 'ASSEMBLY'}]}]}
    monkeypatch.setattr(main, 'run_agent', agent)
    response = client.post('/api/chat/stream', json={'message': 'How is ORD-108?', 'conversation_id': 'session-a'})
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    events = _events(response.text)
    assert [event for event, _ in events] == ['progress', 'progress', 'done']
    assert len(events[-1][1]['why']['steps']) == 4
    assert events[-1][1]['conversation_id'] == 'session-a'
    assert calls == ['user:2:conversation:session-a']


def test_same_public_session_id_is_namespaced_by_authenticated_user(client, monkeypatch):
    sessions = []
    def agent(message, session_id, **kwargs):
        sessions.append(session_id)
        return {'answer': 'A', 'conversation_id': session_id}
    monkeypatch.setattr(main, 'run_agent', agent)
    client.post('/api/chat/stream', json={'message': 'Q', 'conversation_id': 'same'})
    main.app.dependency_overrides[get_current_user] = lambda: _user(1)
    client.post('/api/chat/stream', json={'message': 'Q', 'conversation_id': 'same'})
    assert sessions == ['user:2:conversation:same', 'user:1:conversation:same']


@pytest.mark.parametrize('endpoint', ['/api/chat', '/api/chat/stream'])
def test_chat_requires_auth_before_tools(endpoint, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail('Unauthenticated request reached a tool')
    monkeypatch.setattr(main, 'run_agent', forbidden)
    response = TestClient(main.app).post(endpoint, json={'message': 'Q'})
    assert response.status_code == 401


def test_missing_configuration_is_http_error_before_stream(client, monkeypatch):
    monkeypatch.setattr(main, 'llm_is_configured', lambda: False)
    response = client.post('/api/chat/stream', json={'message': 'Q'})
    assert response.status_code == 503
    assert 'text/event-stream' not in response.headers['content-type']


@pytest.mark.parametrize('failure', [RuntimeError('PRIVATE DETAILS'), {'tools_used': 'invalid'}])
def test_failure_never_emits_success_or_internal_details(client, monkeypatch, failure):
    def agent(*args, **kwargs):
        if isinstance(failure, Exception): raise failure
        return {'answer': 'A', 'conversation_id': 'id', **failure}
    monkeypatch.setattr(main, 'run_agent', agent)
    response = client.post('/api/chat/stream', json={'message': 'Q'})
    events = _events(response.text)
    assert events[-1][0] == 'error'
    assert all(event != 'done' for event, _ in events)
    assert 'PRIVATE' not in response.text


def test_json_chat_uses_the_same_explanation_without_history_tables(client, monkeypatch):
    monkeypatch.setattr(main, 'run_agent', lambda *a, **kw: {'answer': 'A', 'conversation_id': a[1]})
    response = client.post('/api/chat', json={'message': 'Why?', 'conversation_id': 'old-style-session'})
    assert response.status_code == 200
    assert response.json()['conversation_id'] == 'old-style-session'
    assert len(response.json()['why']['steps']) == 4
