"""Answer-token streaming keeps tool-call text out of the visible reply."""

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from backend.agent.graph import _stream_agent
from backend.services.chat_stream import ToolProgress


class _Agent:
    def __init__(self, events):
        self.events = events

    def stream(self, payload, config, stream_mode):
        assert stream_mode == ["messages", "values"]
        yield from self.events

    def get_state(self, config):
        raise AssertionError("values mode already returned the final state")


def test_answer_tokens_skip_tool_calls_and_keep_the_final_state():
    pieces = []
    final = {
        "messages": [
            AIMessage(content="ORD-120 is 15 days overdue."),
        ]
    }
    agent = _Agent(
        [
            ("messages", (AIMessageChunk(content="Checking"), {})),
            (
                "messages",
                (
                    AIMessageChunk(
                        content="",
                        tool_call_chunks=[{"name": "get_order_status", "args": "", "id": "1", "index": 0}],
                    ),
                    {},
                ),
            ),
            ("messages", (ToolMessage(content="{}", tool_call_id="1"), {})),
            ("messages", (AIMessageChunk(content="ORD-120 is "), {})),
            ("messages", (AIMessageChunk(content="ORD-120 is 15 days overdue."), {})),
            ("values", final),
        ]
    )

    state = _stream_agent(agent, {}, {}, pieces.append)

    assert pieces == ["Checking", {"reset": True}, "ORD-120 is ", "15 days overdue."]
    assert state is final


def test_progress_labels_do_not_include_tool_arguments():
    seen = []
    handler = ToolProgress(seen.append)
    handler.on_tool_start(
        {"name": "get_orders_at_risk"},
        '{"customer":"TrendCart","secret":"do-not-show"}',
    )
    handler.on_tool_end('{"orders":["ORD-120"]}')
    assert seen == [
        "Comparing remaining work with available time…",
        "Preparing the evidence and answer…",
    ]
    assert "TrendCart" not in "".join(seen)
