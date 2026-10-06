from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agent.graph import _extract_llm_intents, parse_agent_result

TR = {"tool": "get_morning_briefing", "data": {"production": [{"stage": "KNITTING", "current": 100, "baseline": 150}]}}


def _msgs(answer: str):
    import json as _j
    return [
        HumanMessage(content="How is production doing this morning?"),
        AIMessage(content="", tool_calls=[{"name": "get_morning_briefing", "args": {}, "id": "1", "type": "tool_call"}]),
        ToolMessage(content=_j.dumps({"ok": True, **TR, "trace": {"tool": "get_morning_briefing"}}), tool_call_id="1", name="get_morning_briefing"),
        AIMessage(content=answer),
    ]


def test_extract_valid_block_and_strip():
    ans, intents = _extract_llm_intents(
        'Assembly is weak.\n```presentation-intents\n{"presentation_intents": [{"intent": "comparison", "source_tool": "get_morning_briefing", "source_path": "production", "title": "Production vs 30-Day Median"}]}\n```'
    )
    assert "presentation-intents" not in ans and "Assembly is weak." in ans
    assert intents and intents[0]["intent"] == "comparison"


def test_extract_rejects_bad_intent_and_keeps_narrative():
    ans, intents = _extract_llm_intents(
        'Hi.\n```presentation-intents\n{"presentation_intents": [{"intent": "custom_js", "source_tool": "x", "source_path": "", "title": "Evil"}]}\n```'
    )
    assert intents == []
    assert "presentation-intents" not in ans  # block consumed, nothing built


def test_extract_malformed_json_keeps_answer():
    raw = "Hello.\n```presentation-intents\n{not json\n```"
    ans, intents = _extract_llm_intents(raw)
    assert intents == []


def test_llm_plan_wins_over_heuristic():
    parsed = parse_agent_result(
        {"messages": _msgs(
            'Narrative.\n```presentation-intents\n{"presentation_intents": [{"intent": "comparison", "source_tool": "get_morning_briefing", "source_path": "production", "title": "P"}]}\n```'
        )}, "c1")
    assert parsed["presentations"] and parsed["presentations"][0]["kind"] == "comparison"
    assert "presentation-intents" not in parsed["answer"]


def test_no_block_falls_back_to_heuristic():
    parsed = parse_agent_result({"messages": _msgs("Just production is fine.")}, "c1")
    assert isinstance(parsed["presentations"], list)
