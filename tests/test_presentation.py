from backend.presentation.engine import build_presentations, plan_intents

def test_comparison_valid():
    tr=[{"tool":"get_morning_briefing","data":{"production":[{"stage":"KNITTING","current":100,"baseline":150}]}}]
    out=build_presentations(tr,[{"intent":"comparison","source_tool":"get_morning_briefing","source_path":"production","title":"P"}])
    assert out and out[0]["kind"]=="comparison" and out[0]["data"][0]["current"]==100

def test_ranking_and_missing_rejected():
    tr=[{"tool":"discover_factory_issues","data":{"counts_by_type":{"OVERDUE":3},"issues":[{"issue_id":"I1","issue_type":"OVERDUE","priority":"P1"}]}}]
    out=build_presentations(tr,[{"intent":"ranking","source_tool":"discover_factory_issues","source_path":"counts_by_type","title":"T"},{"intent":"ranking","source_tool":"nope","source_path":"x","title":"X"}])
    assert len(out)==1 and out[0]["kind"]=="bar"

def test_incompatible_rejected():
    tr=[{"tool":"get_morning_briefing","data":{"production":[{"stage":"K","current":"bad","baseline":1}]}}]
    assert build_presentations(tr,[{"intent":"comparison","source_tool":"get_morning_briefing","source_path":"production","title":"P"}])==[]

def test_plan_limits_and_greeting():
    assert plan_intents("Hello",[{"tool":"get_morning_briefing","data":{}}])==[]
    tr=[{"tool":"get_order_status","data":{"order":{"order_id":"ORD-1"}}}]
    out=plan_intents("What is status of ORD-1?",tr)
    assert out[0]["intent"]=="entity_summary" and out[0]["source_tool"]=="get_order_status"
