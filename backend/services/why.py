"""User-facing evidence summaries. The four Why steps are drafted by the model."""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from backend.agent.answerability import reply_language

logger = logging.getLogger(__name__)

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


def _stage_name(stage: Any) -> str:
    return str(stage or "").replace("_", " ").title()


def _whole_number(value: Any) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


_LABEL_ONLY_FIELDS = frozenset({
    "stage", "issue_id", "issue_type", "priority", "order_id", "bucket", "rank",
})


def _row_has_comparison(row: dict[str, Any]) -> bool:
    return row.get("last_day_pieces") is not None and bool(row.get("lookback_median") or row.get("median_30d"))


def _explain_one_stage(row: dict[str, Any], zh: bool, facts: list[str], comparisons: list[str], reasons: list[str]) -> None:
    stage = _stage_name(row.get("stage"))
    pieces_raw = row.get("last_day_pieces")
    if pieces_raw is None:
        pieces_raw = row.get("latest_output")
    median_raw = row.get("lookback_median") or row.get("median_30d")
    if pieces_raw is None or not median_raw or not stage:
        return
    pieces = _whole_number(pieces_raw)
    median = _whole_number(median_raw)
    day = row.get("last_working_date") or "the last working day"
    ratio = row.get("ratio_to_median")
    if ratio is None:
        ratio = row.get("ratio")
    percent = round(float(ratio) * 100) if ratio is not None else round(float(pieces_raw) / float(median_raw) * 100)
    facts.append(
        f"{stage} 在 {day} 完成 {pieces} 件。它的 30 个工作日中位数是每天 {median} 件。" if zh else
        f"{stage} completed {pieces} pieces on {day}. Its 30-working-day median is {median} pieces a day."
    )
    flagged = row.get("flagged")
    if flagged is None and row.get("threshold") is not None:
        flagged = float(ratio or 0) < float(row["threshold"])
    if flagged:
        comparisons.append(
            f"{pieces} 件是中位数 {median} 件的 {percent}%。低于中位数的 70% 才会被标出，所以 {stage} 被标出。" if zh else
            f"{pieces} pieces is {percent}% of the median of {median}. A stage is flagged only when the latest day is below 70% of that median, so {stage} is flagged."
        )
        reasons.append(
            f"{stage} 被列出来，是因为最近一个工作日的产量低于它自己近 30 个工作日中位数的 70%。这比较的是全厂该工序的产量，不是某一张订单。" if zh else
            f"{stage} is listed because its latest working day is below 70% of its own 30-working-day median. The comparison is factory-wide output for that stage, not one order."
        )
    else:
        comparisons.append(
            f"{pieces} 件是中位数 {median} 件的 {percent}%，没有低于 70%，所以 {stage} 没有被标出。" if zh else
            f"{pieces} pieces is {percent}% of the median of {median}, which is not below 70%, so {stage} is not flagged."
        )


def _explain_stage_output(data: dict[str, Any], zh: bool, facts: list[str], comparisons: list[str], reasons: list[str], sources: list[dict[str, Any]]) -> None:
    """Turn the stage-output snapshot into the same four-step explanation as other answers."""
    production = data.get("production") if isinstance(data.get("production"), dict) else {}
    stages = production.get("stage_vs_30day_median") or []
    queue = production.get("in_progress_order_count")
    by_stage = production.get("in_progress_by_stage") if isinstance(production.get("in_progress_by_stage"), dict) else {}
    if queue is not None and by_stage:
        parts = [f"{count} in {_stage_name(name)}" for name, count in by_stage.items()]
        if zh or len(parts) < 2:
            counts = "、".join(parts) if zh else (parts[0] if parts else "")
        else:
            counts = ", ".join(parts[:-1]) + ", and " + parts[-1]
        facts.append(
            f"当前有 {queue} 个在制订单：{counts}。" if zh else
            f"{queue} orders are in progress: {counts}."
        )
    for row in stages:
        if isinstance(row, dict):
            _explain_one_stage(row, zh, facts, comparisons, reasons)
    if not stages:
        for issue in data.get("issues") or []:
            if isinstance(issue, dict):
                _explain_one_stage({**issue, **(issue.get("evidence") or {}), **(issue.get("inputs") or {})}, zh, facts, comparisons, reasons)
    if stages or data.get("issues"):
        sources.append({
            "name": "production_log.csv",
            "label": "production_log.csv · 最近一个工作日与 30 个工作日中位数的比较" if zh else
                     "production_log.csv · last working day compared with the 30-working-day median",
            "summary_only": True,
            "rows": [],
        })


def build_why(question: str, response: dict[str, Any]) -> dict[str, Any]:
    zh = reply_language(question) == "zh"
    idx = int(zh)
    traces = [t for t in response.get("traces", []) if isinstance(t, dict)
              and t.get("tool") not in {
                  "draw", "render_table", "filter_rows", "summarize_rows",
                  "assess_stored_data", "assess_tool_coverage",
              }]
    facts, comparisons, sources, reasons = [], [], [], []
    discovery_in_evidence = any(
        item.get("tool") == "discover_factory_issues" and isinstance((item.get("data") or {}).get("production"), dict)
        for item in response.get("evidence_results") or []
        if isinstance(item, dict)
    )
    for trace in traces:
        rows = [r for r in trace.get("rows", []) if isinstance(r, dict)]
        if trace.get("tool") == "discover_factory_issues" and discovery_in_evidence:
            continue
        source = trace.get("source_file")
        if source:
            sources.append({"name": str(source), "row_count": len(rows),
                            "rows": [{_FIELDS[k][idx]: _value(v, zh) for k, v in row.items()
                                      if k in _FIELDS and v is not None} for row in rows]})
        for row in rows[:5]:
            if _row_has_comparison(row):
                _explain_one_stage(row, zh, facts, comparisons, reasons)
                continue
            if set(row) <= _LABEL_ONLY_FIELDS:
                continue
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
        if tool == "discover_factory_issues":
            _explain_stage_output(data, zh, facts, comparisons, reasons, sources)
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
        facts = ["这次没有带回可以引用的记录，例如订单、日期或数量。" if zh else
                 "This answer did not include a record that can be quoted, such as an order, a date, or a quantity."]
    if not comparisons:
        comparisons = ["这次没有带回比较。例如，没有把产量和 30 个工作日中位数对比，也没有把剩余工作和交期前的天数对比。" if zh else
                       "This answer did not include a comparison. Output was not set against its 30-working-day median, and remaining work was not set against the days left before the due date."]
    conclusion = reasons or ["上面就是这次能核对的内容。记录本身没有再说明造成这个结果的业务原因。" if zh else
                             "That is everything this answer can check. The records do not go on to explain the business cause."]
    if any(trace.get("tool") == "uc_answer" for trace in traces):
        conclusion = ["Read the answer against the facts and checks above. These records alone do not establish business causation."]
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


_WHY_EXAMPLE = """Question: You will be given today's overall factory briefing, including risks, work in progress, output, and suspended workshops.

1. Start from the question
Today's briefing covers overdue work, tight deadlines, stalled orders, and the Assembly slowdown.

2. Read what the data says
Eight orders are overdue, including ORD-107 and ORD-114 still in Packing. Assembly finished 455 pieces on 31 March, against a 758-piece 30-day median.

3. Check the calculation or comparison
\\[\\mathrm{days}_{\\mathrm{left}}=\\max\\left(\\sum_{\\text{remaining stages}}\\frac{\\text{pieces}}{\\mathrm{median}_{30\\mathrm{d}}},\\ \\text{remaining stages}\\right)\\]
ORD-029 needs about 4.3 working days and is due today. ORD-108 and ORD-103 each need about 8.4 days, with only 3 and 4 working days left.

4. Understand why the conclusion follows
Finish the two Packing orders and unblock ORD-002 first, because those are the overdue and stalled records this briefing actually shows."""

_WHY_STEPS = (
    (
        "Start from the question",
        "从问题出发",
        "Restate what the manager asked. Do not add records.",
        "用一两句话复述经理问了什么，不要补充记录。",
    ),
    (
        "Read what the data says",
        "查看数据事实",
        "State every record the lookup tools returned: order, customer, product, pieces, status, current stage, due date, and last activity, plus the dates and quantities on any other lookup. Leave out only a field that is null. Do not say a record has no details when those fields are present. Do not replace those records with a sentence that only names the order. filter_rows, summarize_rows, draw, and render_table are intermediate tools: do not include their rows, counts, or sums.",
        "写上查询工具返回的每一条记录：订单、客户、产品、件数、状态、当前工序、交期和最近活动，以及其他查询里的日期和数量。只有字段本身为空才省略。不要只写选中了哪张订单。filter_rows、summarize_rows、draw、render_table 是中间工具，不要写入它们的行、计数或合计。",
    ),
    (
        "Check the calculation or comparison",
        "检查计算或比较",
        "Write every formula as display LaTeX inside \\[ and \\], in the same notation as "
        r"\[\mathrm{days}_{\mathrm{left}}=\max\left(\sum_{\text{remaining stages}}\frac{\text{pieces}}{\mathrm{median}_{30\mathrm{d}}},\ \text{remaining stages}\right)\]"
        ". Do not spell a formula out in words. After the formula, state the comparison and the final figures the answer uses.",
        "每个公式都写成 \\[ 和 \\] 包住的 LaTeX，记法和 "
        r"\[\mathrm{days}_{\mathrm{left}}=\max\left(\sum_{\text{remaining stages}}\frac{\text{pieces}}{\mathrm{median}_{30\mathrm{d}}},\ \text{remaining stages}\right)\]"
        " 相同。不要把公式写成文字。公式后面再写比较方法和回答用到的最终数字。",
    ),
    (
        "Understand why the conclusion follows",
        "理解结论依据",
        "Say why those records support the answer. Do not invent a cause.",
        "说明这些记录如何支持回答，不要编造原因。",
    ),
)


def _compact_evidence(value: Any, depth: int = 0) -> Any:
    # Tool JSON is packet → trace → rows → order → fields. A depth of 4
    # turned every order field into null, so the model reported empty records.
    if isinstance(value, dict):
        if depth > 8:
            return None
        return {
            key: _compact_evidence(item, depth + 1)
            for key, item in value.items()
            if key not in {"working_days", "lookback_dates"}
        }
    if isinstance(value, list):
        if depth > 8:
            return None
        return [_compact_evidence(item, depth + 1) for item in value[:40]]
    if isinstance(value, str) and len(value) > 500:
        return value[:500]
    return value


_INTERMEDIATE_TOOLS = frozenset({
    "filter_rows", "summarize_rows", "draw", "render_table",
    "assess_stored_data", "assess_tool_coverage",
})
_EMPTY_SOURCE = re.compile(
    r"no populated|source row has no|unpopulated|selected for the source|source lookup"
    r"|没有可引用|来源行为空|来源记录为空|选中了|被选为来源|来源查询",
    re.I,
)


def _step_text(text: str, titles: tuple[str, ...] = ()) -> str:
    """Keep the whole step. Code fences and a repeated step title are removed."""
    cleaned = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", str(text or "")).strip()
    lines = cleaned.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines or not titles:
        return cleaned
    first = re.sub(r"^#{1,6}\s*", "", lines[0].strip())
    first = re.sub(r"^\d+\.\s*", "", first).strip().rstrip("：:").strip()
    known = {title.casefold() for title in titles}
    if first.casefold() not in known:
        return cleaned
    lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).strip()


def _lookup_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for trace in packet.get("traces") or []:
        if not isinstance(trace, dict) or trace.get("tool") in _INTERMEDIATE_TOOLS:
            continue
        for row in trace.get("rows") or []:
            if isinstance(row, dict) and row.get("order_id") and row.get("pieces") is not None:
                key = str(row.get("order_id"))
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
    for result in packet.get("evidence_results") or []:
        if not isinstance(result, dict) or result.get("tool") in _INTERMEDIATE_TOOLS:
            continue
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        candidates = [data.get("order")] if isinstance(data.get("order"), dict) else []
        candidates.extend(item for item in data.get("orders") or [] if isinstance(item, dict))
        for row in candidates:
            if row.get("order_id") and row.get("pieces") is not None:
                key = str(row.get("order_id"))
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
    return rows


def _source_fact(evidence: str, zh: bool) -> str:
    """Records from the lookup tools, used when the draft omitted them."""
    try:
        packet = json.loads(evidence)
    except ValueError:
        return ""
    rows = _lookup_rows(packet)
    if not rows:
        return ""
    sentences = []
    for row in rows:
        oid = row.get("order_id")
        if zh:
            sentences.append(
                f"{oid} 是 {row.get('customer')} 的 {row.get('pieces')} 件 {row.get('product')}，"
                f"状态 {row.get('status')}，当前工序 {row.get('current_stage')}，"
                f"交期 {row.get('due_date')}，最近活动 {row.get('last_activity_date')}。"
            )
        else:
            sentences.append(
                f"{oid} is {row.get('pieces')} {row.get('product')} for {row.get('customer')}, "
                f"status {row.get('status')}, currently in {row.get('current_stage')}, "
                f"due {row.get('due_date')}, last activity {row.get('last_activity_date')}."
            )
    return " ".join(sentences)


def _omits_lookup(text: str, evidence: str) -> bool:
    if _EMPTY_SOURCE.search(text or ""):
        return True
    try:
        packet = json.loads(evidence)
    except ValueError:
        return False
    rows = _lookup_rows(packet)
    if not rows:
        return False
    markers = [str(rows[0].get("pieces"))]
    if rows[0].get("due_date"):
        markers.append(str(rows[0]["due_date"]))
    return not any(marker in (text or "") for marker in markers)


def _draft_step(question: str, answer: str, evidence: str, step: tuple[str, str, str, str], zh: bool) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    from backend.agent.graph import build_model

    title = step[1] if zh else step[0]
    job = step[3] if zh else step[2]
    system = (
        "You write one step of a factory manager's Why panel. "
        "Follow the example's voice: name the specific orders, dates, and quantities a manager can check. "
        "Do not dump field labels such as 'Stage: ASSEMBLY'. "
        "Do not say that the records do not establish causation. "
        "Use only names and numbers that appear in the question, the answer, or the evidence. "
        "If a number is absent, leave it out. "
        "Write in the same language as the question. "
        + (
            "For this step, include every lookup record. Do not compress them into one sentence that only names the order. "
            if step[0] == "Read what the data says"
            else ""
        )
        + "Write the full step. Do not stop early or leave a sentence unfinished. "
        + "A display formula inside \\[ \\] must be copied intact. "
        "Do not repeat the step title and do not start with a heading. "
        "Return only the step text."
    )
    user = (
        f"Example:\n{_WHY_EXAMPLE}\n\n"
        f"Write this step only: {title}\n{job}\n\n"
        f"Question:\n{question[:500]}\n\nAnswer:\n{answer[:1500]}\n\nEvidence:\n{evidence}"
    )
    result = build_model().invoke([SystemMessage(content=system), HumanMessage(content=user)])
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = " ".join(
            str(block.get("text") or "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return _step_text(str(content or ""), (step[0], step[1]))


def explain_why(question: str, response: dict[str, Any]) -> dict[str, Any]:
    """Draft the four Why steps in parallel. UC answers keep their prepared why."""
    base = build_why(question, response)
    if response.get("clarification"):
        return base
    from backend.agent.graph import llm_is_configured

    if not llm_is_configured():
        return base
    zh = base.get("language") == "zh"
    packet = _compact_evidence({
        "traces": [
            trace for trace in response.get("traces") or []
            if not isinstance(trace, dict) or trace.get("tool") not in _INTERMEDIATE_TOOLS
        ],
        "evidence_results": [
            result for result in response.get("evidence_results") or []
            if not isinstance(result, dict) or result.get("tool") not in _INTERMEDIATE_TOOLS
        ],
    })
    evidence = json.dumps(packet, ensure_ascii=False, default=str)[:6000]
    answer = str(response.get("answer") or "")
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            drafted = list(pool.map(
                lambda step: _draft_step(question, answer, evidence, step, zh),
                _WHY_STEPS,
            ))
    except Exception:
        logger.exception("why model draft failed")
        return base
    if not any(drafted):
        return base
    if _omits_lookup(drafted[1] or "", evidence):
        fact = _source_fact(evidence, zh)
        if fact:
            drafted[1] = fact
    idx = int(zh)
    base["steps"] = [
        {"title": step[idx], "items": [text] if text else base["steps"][index]["items"][:1]}
        for index, (step, text) in enumerate(zip(_WHY_STEPS, drafted))
    ]
    return base


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
