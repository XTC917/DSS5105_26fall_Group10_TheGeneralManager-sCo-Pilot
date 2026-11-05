"""User-facing evidence summaries. No new model calls or business calculations."""
from __future__ import annotations

from typing import Any
from backend.agent.answerability import reply_language

# Only these source fields are presented as facts. Operational/debug metadata is
# deliberately excluded. Full traces remain in the API for existing consumers.
_FIELDS = {
    "order_id": ("Order", "订单"), "in_progress_order_id": ("Existing order", "现有订单"), "customer": ("Customer", "客户"),
    "product": ("Product", "产品"), "pieces": ("Pieces", "件数"),
    "status": ("Status", "状态"), "current_stage": ("Current stage", "当前工序"),
    "due_date": ("Due date", "交期"), "last_activity_date": ("Last activity", "最近活动"),
    "date": ("Date", "日期"), "stage": ("Stage", "工序"),
    "pieces_completed": ("Output in pieces", "产量（件）"),
}
_CALCS = {
    "calendar_days_until_due": ("Calendar days until due", "距交期的自然日数"),
    "working_days_until_due_inclusive": ("Working days available, including the due date", "可用工作日（含交期当天）"),
    "working_days_until_due": ("Working days available", "可用工作日"),
    "working_days_since_last_activity": ("Working days without activity", "未活动的工作日数"),
    "remaining_stage_count": ("Stages remaining", "剩余工序数"),
    "remaining_stages": ("Stages remaining", "剩余工序"),
    "estimated_remaining_working_days": ("Estimated working days still needed", "预计仍需工作日"),
    "days_left": ("Estimated working days still needed", "预计仍需工作日"),
    "factory_window_capacity": ("Factory capacity before the due date (pieces)", "交期前工厂产能（件）"),
    "spare_factory_capacity": ("Spare factory capacity after existing commitments (pieces)", "扣除现有订单后的剩余产能（件）"),
    "workshop_overflow": ("External workshop capacity (pieces)", "外部工坊产能（件）"),
    "overdue": ("Past the due date", "已过交期"),
    "stalled": ("No activity for at least three working days", "至少三个工作日未活动"),
    "tight_deadline": ("Remaining work exceeds the time available", "剩余工作超过可用时间"),
}
# Same pace estimate under either name. The method sentence is shared; raw formula
# strings are not shown, because some of them point at internal code.
_PACE_ESTIMATE_NAMES = frozenset({"days_left", "estimated_remaining_working_days"})
_PACE_FORMULA = (
    r"\mathrm{days}_{\mathrm{left}}=\max\left("
    r"\sum_{\text{remaining stages}}\frac{\text{pieces}}{\mathrm{median}_{30\mathrm{d}}},"
    r"\ \text{remaining stages}\right)"
)


def _has_pace_estimate(value: Any) -> bool:
    """True when this turn's evidence carries the pace estimate, under either name."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "name" and item in _PACE_ESTIMATE_NAMES:
                return True
            if key in _PACE_ESTIMATE_NAMES and item is not None:
                return True
            if _has_pace_estimate(item):
                return True
    elif isinstance(value, list):
        return any(_has_pace_estimate(item) for item in value)
    return False


def _value(value: Any, zh: bool) -> str:
    if isinstance(value, bool):
        return ("是" if value else "否") if zh else ("Yes" if value else "No")
    if isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
        return ", ".join(str(v) for v in value)
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""


def build_why(question: str, response: dict[str, Any]) -> dict[str, Any]:
    zh = reply_language(question) == "zh"
    idx = int(zh)
    traces = [t for t in response.get("traces", []) if isinstance(t, dict)
              and t.get("tool") not in {"draw", "render_table", "assess_stored_data", "assess_tool_coverage"}]
    facts, comparisons, sources, reasons = [], [], [], []
    for trace in traces:
        rows = [r for r in trace.get("rows", []) if isinstance(r, dict)]
        source = trace.get("source_file")
        if source:
            sources.append({"name": str(source), "row_count": len(rows),
                            "rows": [{_FIELDS[k][idx]: _value(v, zh) for k, v in row.items()
                                      if k in _FIELDS and v is not None} for row in rows]})
        for row in rows[:5]:
            fields = [f"{_FIELDS[k][idx]}: {_value(v, zh)}" for k, v in row.items()
                      if k in _FIELDS and v is not None]
            if fields:
                facts.append("; ".join(fields) + ".")
        for calc in trace.get("calculations", []):
            if not isinstance(calc, dict) or calc.get("name") not in _CALCS:
                continue
            result = calc.get("result")
            if calc["name"] in _PACE_ESTIMATE_NAMES and not isinstance(result, (int, float)):
                continue
            value = _value(result, zh)
            if not value:
                continue
            text = f"{_CALCS[calc['name']][idx]}: {value}."
            comparisons.append(text)
            if calc["name"] in {"overdue", "stalled", "tight_deadline"} and result is True:
                reasons.append(text)
        if any(str(c.get("name", "")).startswith("working_days") for c in trace.get("calculations", []) if isinstance(c, dict)):
            comparisons.append("工作日计算排除周日，并采用工具中的工厂日期。" if zh else
                               "Working-day checks exclude Sundays and use the tool's factory date.")
    # Structured tool outputs carry the actual comparison and verdict. Read them
    # without repeating the arithmetic or inferring missing business outcomes.
    for result in response.get("evidence_results", []):
        data = result.get("data") or {}
        tool = result.get("tool")
        if tool == "check_feasibility" and data.get("summary"):
            reasons.append(str(data["summary"]))
        orders = data.get("orders") if tool == "get_orders_at_risk" else None
        if tool == "trace_order":
            orders = [{**(data.get("order") or {}), "pace": data.get("pace") or {},
                       "flags": (data.get("risk") or {}).get("flags") or []}]
        for order in orders or []:
            pace = order.get("pace") or {}
            needed = pace.get("estimated_remaining_working_days")
            available = pace.get("working_days_until_due_inclusive")
            oid = order.get("order_id", "")
            # A tool can return several alternative windows. Do not explain an
            # unrelated order when the answer explicitly discusses other IDs.
            import re
            answered_ids = set(re.findall(r"ORD-\d+", response.get("answer") or "", re.I))
            if answered_ids and oid not in answered_ids:
                continue
            if needed is not None and available is not None:
                comparisons.append(
                    f"{oid}：工具预计仍需 {needed} 个工作日；交期前可用 {available} 个工作日。" if zh else
                    f"{oid}: the tool estimates {needed} working days of work remaining, with {available} working days available before the due date.")
            if "TIGHT_DEADLINE" in (order.get("flags") or []):
                reasons.append(f"{oid}：在工具采用的当前产速估算下，剩余工作超过交期前可用时间，因此被标记为交期紧张。" if zh else
                               f"{oid} is flagged for a tight deadline because the tool's current-pace estimate exceeds the time available before the due date.")
        if tool == "get_order_status" and (data.get("computed") or {}).get("is_overdue") is True:
            reasons.append("订单仍未完成且已过交期，因此被判定为逾期。" if zh else
                           "The order is still in progress and its due date has passed, so it is overdue.")
    if _has_pace_estimate(traces) or _has_pace_estimate(response.get("evidence_results")):
        comparisons.insert(0, _PACE_FORMULA)
    if not facts:
        facts = ["此回答没有附带可展示的来源行；不能据此声称完成了数据核验。" if zh else
                 "No displayable source rows were attached to this answer; source verification is unavailable."]
    if not comparisons:
        comparisons = ["没有附带数值计算；此处仅说明已返回的数据或当前限制。" if zh else
                       "No numeric calculation was attached. This explanation is limited to the returned records or stated limitation."]
    conclusion = reasons or ["请结合上面的事实与计算阅读回答；这些记录本身并不能证明业务上的因果关系。" if zh else
                             "Read the answer against the facts and checks above. These records alone do not establish business causation."]
    limits = list(dict.fromkeys(response.get("evidence_limitations") or []))
    if response.get("clarification"):
        conclusion = ["需要先确认具体对象，当前不能得出订单层面的结论。" if zh else
                      "The subject needs clarification before an order-level conclusion can be drawn."]
    elif response.get("limitation"):
        conclusion = [response.get("answer") or ("数据不足，无法作出判断。" if zh else "Insufficient evidence for a conclusion.")]
    titles = [("Start from the question", "从问题出发"), ("Read what the data says", "查看数据事实"),
              ("Check the calculation or comparison", "检查计算或比较"),
              ("Understand why the conclusion follows", "理解结论依据")]
    return {"version": 1, "language": "zh" if zh else "en",
            "steps": [{"title": title[idx], "items": list(dict.fromkeys(items))}
                      for title, items in zip(titles, [[question], facts[:10], comparisons[:20], conclusion])],
            "sources": sources, "limitations": limits,
            "source_context": (("复用本对话中上一份工具结果的来源；本轮未重新查询。" if zh else
                                "Source evidence reused from an earlier tool result in this conversation; it was not queried again this turn.")
                               if response.get("evidence_reused") else None)}


def attach_prior_evidence(response: dict[str, Any], messages: list[Any]) -> None:
    """For an explicitly routed follow-up, reuse that thread's last tool evidence.

    This never adds a tool invocation, model summary or proposed action. A failed
    latest lookup is a boundary: do not silently fall back to an older result.
    """
    import json
    from langchain_core.messages import ToolMessage

    if response.get("evidence_results"):
        return
    latest_question = next((i for i in range(len(messages) - 1, -1, -1)
                            if getattr(messages[i], "type", None) == "human"), 0)
    history = messages[:latest_question]
    for index in range(len(history) - 1, -1, -1):
        msg = history[index]
        if not isinstance(msg, ToolMessage):
            continue
        try:
            payload = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        tool = payload.get("tool") or msg.name
        if tool in {"draw", "render_table"}:
            continue
        if not payload.get("ok") or not payload.get("trace"):
            return
        start = next((i for i in range(index, -1, -1)
                      if getattr(history[i], "type", None) == "human"), 0)
        traces, results, limits = [], [], []
        for prior in history[start:]:
            if not isinstance(prior, ToolMessage):
                continue
            try:
                value = json.loads(prior.content) if isinstance(prior.content, str) else prior.content
            except (ValueError, TypeError):
                continue
            if not isinstance(value, dict) or not value.get("ok"):
                continue
            name = value.get("tool") or prior.name
            if name in {"draw", "render_table"}:
                continue
            data = value.get("data") or {}
            if value.get("trace"):
                traces.append(value["trace"])
            results.append({"tool": name, "data": data})
            limits.extend(v for v in data.get("limitations", []) if isinstance(v, str))
        if traces:
            response["traces"] = traces
            response["evidence_results"] = results
            response["evidence_limitations"] = limits
            response["evidence_reused"] = True
        return
