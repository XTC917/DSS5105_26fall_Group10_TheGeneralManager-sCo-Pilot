"""Presentation / Visualization Engine — deterministic, no LLM, no DB."""
from __future__ import annotations
from typing import Any

INTENTS = {"summary","comparison","ranking","distribution","trend","entity_summary","entity_comparison","table","alerts","metric_cards","bar","line","ranked_list","data_table","status_card","alert_list"}
CANON = {"metric_cards":"summary","bar":"ranking","line":"trend","ranked_list":"ranking","data_table":"table","status_card":"entity_summary","alert_list":"alerts","comparison":"comparison","distribution":"distribution","trend":"trend","ranking":"ranking","table":"table","alerts":"alerts","summary":"summary","entity_summary":"entity_summary","entity_comparison":"entity_comparison"}

def _get_path(data: dict, path: str):
    cur: Any = data
    for part in (path or "").split("."):
        if not part: continue
        if isinstance(cur, dict): cur = cur.get(part)
        else: return None
    return cur

def build_presentations(tool_results: list[dict], intents: list[dict]) -> list[dict]:
    """tool_results: [{tool, data}]. intents: [{intent, source_tool, source_path, title, emphasis}]."""
    by_tool = {r.get("tool"): r.get("data") for r in tool_results if r.get("tool")}
    out: list[dict] = []
    for pi in intents[:3]:
        intent = CANON.get(str(pi.get("intent","")).lower(), "")
        if not intent: continue
        src_tool = pi.get("source_tool")
        data = by_tool.get(src_tool)
        if data is None: continue
        path = pi.get("source_path") or ""
        sub = _get_path(data, path) if path else data
        if sub is None: continue
        title = str(pi.get("title") or path or src_tool)[:120]
        try:
            spec = _build(intent, title, sub, pi, src_tool, path)
        except ValueError:
            continue
        if spec: out.append(spec)
    return out

def _build(intent, title, sub, pi, src_tool, path):
    prov = {"source_tool": src_tool, "source_path": path}
    if intent == "summary":
        cards = _metric_cards(sub)
        if not cards: raise ValueError("no metrics")
        return {"kind":"metric_cards","title":title,"data":cards[:6],"provenance":prov}
    if intent in ("ranking",):
        if isinstance(sub, dict) and sub and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in sub.values()):
            return {"kind":"bar","title":title,"data":[{"label":k,"value":v} for k,v in list(sub.items())[:12]],"provenance":prov}
        items = _ranking_items(sub)
        if not items: raise ValueError("no ranking")
        return {"kind":"ranked_list","title":title,"data":items[:8],"provenance":prov}
    if intent == "distribution":
        if isinstance(sub, dict) and all(isinstance(v,(int,float)) for v in sub.values()):
            return {"kind":"bar","title":title,"data":[{"label":k,"value":v} for k,v in list(sub.items())[:12]],"provenance":prov}
        raise ValueError("bad distribution")
    if intent == "comparison":
        rows = _comparison_rows(sub)
        if not rows: raise ValueError("no comparison")
        return {"kind":"comparison","title":title,"data":rows[:8],"provenance":prov,"emphasis":pi.get("emphasis")}
    if intent == "trend":
        pts = _trend_points(sub)
        if len(pts) < 2: raise ValueError("no trend")
        return {"kind":"line","title":title,"data":pts[:30],"provenance":prov}
    if intent == "entity_summary":
        ent = sub if isinstance(sub, dict) else {}
        if not ent: raise ValueError("no entity")
        return {"kind":"status_card","title":title,"data":ent,"provenance":prov}
    if intent in ("table","entity_comparison"):
        rows = sub if isinstance(sub, list) else sub.get("orders") if isinstance(sub, dict) else None
        if not isinstance(rows, list) or not rows: raise ValueError("no table")
        cols = sorted({k for r in rows[:8] if isinstance(r,dict) for k in r.keys()})[:7]
        return {"kind":"data_table","title":title,"columns":cols,"data":[ {c:r.get(c) for c in cols} for r in rows[:12]],"provenance":prov}
    if intent == "alerts":
        rows = sub if isinstance(sub, list) else sub.get("issues", sub.get("orders", [])) if isinstance(sub, dict) else []
        if not rows: raise ValueError("no alerts")
        return {"kind":"alert_list","title":title,"data":[{"label":str(r.get("issue_id") or r.get("order_id")), "detail":str(r.get("issue_type") or ",".join(r.get("flags",[])))[:160], "severity":str(r.get("priority","")).lower()} for r in rows[:8]],"provenance":prov}
    raise ValueError("unknown intent")

def _metric_cards(sub):
    cards = []
    if isinstance(sub, dict):
        for k in ("count","total_found","in_progress_order_count","at_risk_count","returned_count"):
            if isinstance(sub.get(k),(int,float)): cards.append({"label":k,"value":sub[k]})
        for k,v in list(sub.items()):
            if isinstance(v,(int,float)) and len(cards)<6 and not any(c["label"]==k for c in cards): cards.append({"label":k,"value":v})
    return cards

def _ranking_items(sub):
    if isinstance(sub, dict):
        if "issues" in sub and isinstance(sub["issues"],list):
            return [{"label":i.get("issue_id",i.get("order_id","")),"detail":str(i.get("issue_type"))[:160],"severity":str(i.get("priority","")).lower()} for i in sub["issues"]]
        if "orders" in sub and isinstance(sub["orders"],list):
            return [{"label":o.get("order_id",""),"detail":",".join(o.get("flags",[])) if isinstance(o.get("flags"),list) else str(o.get("current_stage","")),"severity":"high"} for o in sub["orders"]]
    if isinstance(sub, list):
        return [{"label":str(r.get("order_id") or r.get("issue_id") or r.get("label")),"detail":str(r.get("issue_type") or r.get("current_stage") or "")[:160]} for r in sub if isinstance(r,dict)]
    return []

def _comparison_rows(sub):
    # briefing production: dict or list of {stage, output/current, median/baseline}
    cand = sub if isinstance(sub,list) else sub.get("production", sub.get("stages", sub.get("stage_output", []))) if isinstance(sub,dict) else []
    rows = []
    if isinstance(cand, dict):  # {stage: {current, baseline}}
        for k,v in cand.items():
            if isinstance(v,dict) and ("current" in v or "output" in v):
                rows.append({"label":k,"current":v.get("current",v.get("output")),"baseline":v.get("baseline",v.get("median"))})
        return rows
    for r in (cand or []):
        if not isinstance(r,dict): continue
        label = r.get("stage") or r.get("label")
        cur = r.get("current", r.get("output", r.get("pieces", r.get("last_day", r.get("last_day_pieces")))))
        base = r.get("baseline", r.get("median", r.get("median_30d", r.get("lookback_median"))))
        if label is not None and isinstance(cur,(int,float)) and isinstance(base,(int,float)):
            # prevent incompatible units: both must be numeric pcs — ok
            rows.append({"label":label,"current":cur,"baseline":base})
    return rows

def _trend_points(sub):
    cand = sub if isinstance(sub,list) else sub.get("history", sub.get("series", sub.get("daily_output",[]))) if isinstance(sub,dict) else []
    pts = []
    for r in (cand or []):
        if isinstance(r,dict) and isinstance(r.get("value"),(int,float)) and r.get("date"):
            pts.append({"x":r["date"],"y":r["value"]})
        elif isinstance(r,(list,tuple)) and len(r)==2:
            pts.append({"x":str(r[0]),"y":r[1]})
    return pts

def plan_intents(question: str, tool_results: list[dict]) -> list[dict]:
    """Heuristic planner (no LLM): question-aware, max 2 specs. Replaces LLM intent to avoid extra round-trip."""
    q = (question or "").lower()
    has = {r.get("tool") for r in tool_results}
    intents = []
    def has_path(tool, path):
        for r in tool_results:
            if r.get("tool")==tool and _get_path(r.get("data") or {}, path) is not None: return True
        return False
    if "get_morning_briefing" in has:
        if any(w in q for w in ("wip","stage","distribut")) and has_path("get_morning_briefing","in_progress_by_stage"):
            intents.append({"intent":"distribution","source_tool":"get_morning_briefing","source_path":"in_progress_by_stage","title":"WIP by Stage"})
        elif any(w in q for w in ("production","baseline","output","median")) and has_path("get_morning_briefing","unusual_stage_output"):
            intents.append({"intent":"comparison","source_tool":"get_morning_briefing","source_path":"unusual_stage_output","title":"Production vs 30-Day Baseline"})
        elif "briefing" in q or "morning" in q or "overview" in q or "today" in q:
            if has_path("get_morning_briefing","at_risk"): intents.append({"intent":"summary","source_tool":"get_morning_briefing","source_path":"at_risk","title":"At-Risk Summary"})
            if has_path("get_morning_briefing","unusual_stage_output"): intents.append({"intent":"comparison","source_tool":"get_morning_briefing","source_path":"unusual_stage_output","title":"Production vs 30-Day Baseline"})
        elif has_path("get_morning_briefing","at_risk"):
            intents.append({"intent":"alerts","source_tool":"get_morning_briefing","source_path":"at_risk.orders","title":"At-Risk Orders"})
    if "discover_factory_issues" in has:
        if "concern" in q or "issue" in q or "problem" in q or "risk" in q or "attention" in q or not intents:
            intents.append({"intent":"ranking","source_tool":"discover_factory_issues","source_path":"counts_by_type","title":"Issues by Type"})
            if len(intents)<2: intents.append({"intent":"alerts","source_tool":"discover_factory_issues","source_path":"issues","title":"Top Priority Issues"})
    if "get_order_status" in has and not intents:
        intents.append({"intent":"entity_summary","source_tool":"get_order_status","source_path":"order","title":"Order Status"})
    if "check_feasibility" in has and not intents:
        intents.append({"intent":"summary","source_tool":"check_feasibility","source_path":"","title":"Feasibility Summary"})
    if ("find_orders" in has or "get_orders_at_risk" in has) and not intents:
        t = "get_orders_at_risk" if "get_orders_at_risk" in has else "find_orders"
        intents.append({"intent":"table","source_tool":t,"source_path":"orders","title":"Orders"})
    if any(w in q for w in ("hello","hi","thanks","thank")) and len(q.split())<4:
        return []
    return intents[:2]
