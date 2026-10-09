"""Temporary SQL-writing chat path. Rollback: SQL_AGENT_MODE=false (default).

Token budget: skip answerability + ReAct (saves 2–4 LLM rounds). Two calls only:
1) pick one catalog tool and write one SELECT (SQL examples stay in this prompt)
2) compose from SQL rows + few-shot templates
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.agent.answerability import _ask_json, _content_text
from backend.agent.prompts import format_retrieved_templates
from backend.pg_config import PG_SCHEMA
from backend.services.pg_database import db_connection
from backend.services.question_templates import (
    retrieve_answer_templates,
    supplement_templates_for_tools,
)

logger = logging.getLogger(__name__)

MAX_ROWS = 40
ALLOWED_TABLES = {
    f"{PG_SCHEMA}.orders",
    f"{PG_SCHEMA}.production_log",
    f"{PG_SCHEMA}.workshops",
    f"{PG_SCHEMA}.snapshot",
}
BARE_TABLES = {name.split(".", 1)[1] for name in ALLOWED_TABLES}
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|"
    r"execute|call|do|comment|notify|listen|load|lock|vacuum|analyze|refresh)\b",
    re.I,
)
_FROM_JOIN = re.compile(r"\b(from|join)\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)", re.I)
_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)

_CATALOG = f"""Today=2026-04-01. One SELECT. Tables: {PG_SCHEMA}.orders, {PG_SCHEMA}.production_log, {PG_SCHEMA}.workshops, {PG_SCHEMA}.snapshot.
orders(order_id,customer,product,category,pieces,order_date,due_date,status,current_stage,last_activity_date,completed_date,days_late)
production_log(production_date,stage,pieces_completed)  snapshot(order_id,status,stage,date)
workshops(workshop_id,name,makes,status,capacity_pieces_per_day,pickup_lead_days,defect_rate,current_queue_days)

Pick exactly one tool and write SQL that matches it:
get_order_status — one order
  SELECT order_id,customer,product,pieces,due_date,status,current_stage,last_activity_date FROM {PG_SCHEMA}.orders WHERE order_id='ORD-120'
find_orders — list
  SELECT order_id,customer,product,status,current_stage FROM {PG_SCHEMA}.orders WHERE customer='TrendCart'
get_orders_at_risk — miss-due list is Python (max of pieces / 30-day stage median and remaining stage count), not this SQL. Overdue is due_date < '2026-04-01'.
  SELECT order_id,due_date,current_stage,pieces FROM {PG_SCHEMA}.orders WHERE status='IN_PROGRESS' AND due_date>='2026-04-01'
trace_order — stage history
  SELECT stage,date FROM {PG_SCHEMA}.snapshot WHERE order_id='ORD-120' ORDER BY date
discover_factory_issues / get_morning_briefing — recent output
  SELECT production_date,stage,pieces_completed FROM {PG_SCHEMA}.production_log ORDER BY production_date DESC LIMIT 20
get_today_priority — in-progress orders for Python 1st/2nd/3rd grouping
  SELECT order_id,customer,product,pieces,due_date,current_stage FROM {PG_SCHEMA}.orders WHERE status='IN_PROGRESS'
check_feasibility — shops
  SELECT workshop_id,makes,status,capacity_pieces_per_day FROM {PG_SCHEMA}.workshops WHERE status='ACTIVE'
"""

_WRITE_SYS = """Reply with one JSON object only:
{"tool":"<catalog name>","sql":"SELECT ..."}
sql must be a single SELECT (or WITH ... SELECT) on app.* tables above. No writes. Factory today 2026-04-01.
"""

_COMPOSE_SYS = """You are the GM Co-Pilot. Factory today is 2026-04-01.
Answer only from SQL_ROWS. Copy ids and numbers. Same language as the manager.
Do not greet. Do not invent rows. If SQL_ROWS is empty, say so.
"""


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def strip_sql(sql: str) -> str:
    text = _COMMENT.sub(" ", sql or "")
    text = " ".join(text.split())
    return text.strip().rstrip(";")


def qualify_sql(sql: str) -> str:
    def repl(match: re.Match[str]) -> str:
        kw, name = match.group(1), match.group(2)
        low = name.lower()
        if "." not in low and low in BARE_TABLES:
            return f"{kw} {PG_SCHEMA}.{low}"
        return match.group(0)

    return _FROM_JOIN.sub(repl, sql)


def validate_sql(sql: str) -> str:
    """Return cleaned SQL or raise ValueError."""
    cleaned = qualify_sql(strip_sql(sql))
    if not cleaned:
        raise ValueError("empty sql")
    if ";" in cleaned:
        raise ValueError("multiple statements are not allowed")
    if _FORBIDDEN.search(cleaned):
        raise ValueError("only a read-only SELECT is allowed")
    head = cleaned.lstrip("(").lower()
    if not (head.startswith("select") or head.startswith("with")):
        raise ValueError("sql must start with SELECT or WITH")
    tables = {m.group(2).lower() for m in _FROM_JOIN.finditer(cleaned)}
    if not tables:
        raise ValueError("sql must read app.orders, production_log, workshops, or snapshot")
    for table in tables:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"table not allowed: {table}")
    if not re.search(r"\blimit\s+\d+\b", cleaned, re.I):
        cleaned = f"{cleaned} LIMIT {MAX_ROWS}"
    return cleaned


def run_select(sql: str) -> list[dict[str, Any]]:
    with db_connection(admin=False) as conn:
        rows = conn.execute(sql).fetchmany(MAX_ROWS)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        out.append({k: _json_safe(v) for k, v in item.items()})
    return out


def _ask_text(model: Any, system: str, user: str) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    result = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _content_text(getattr(result, "content", result)).strip()


def run_sql_agent(message: str, conversation_id: str) -> dict[str, Any]:
    """Two LLM calls: write SQL, then answer from rows + templates."""
    from backend.agent.graph import build_model, llm_is_configured

    if not llm_is_configured():
        raise RuntimeError("LLM key is not set.")

    model = build_model()
    picked = _ask_json(
        model,
        _WRITE_SYS,
        f"{_CATALOG}\n\nManager:\n{message}",
    )
    tool_name = str(picked.get("tool") or "sql").strip() or "sql"
    try:
        sql = validate_sql(str(picked.get("sql") or ""))
        rows = run_select(sql)
        error = None
    except Exception as exc:  # noqa: BLE001
        logger.info("sql_agent rejected conversation=%s err=%s", conversation_id, exc)
        sql = str(picked.get("sql") or "")
        rows = []
        error = str(exc)

    traces = [
        {
            "tool": "sql_agent",
            "source_file": f"{PG_SCHEMA} tables",
            "filter": {"tool": tool_name, "sql": sql},
            "rows": rows[:MAX_ROWS],
            "calculations": [],
            "basis": error or "Read-only SELECT on app schema. Python tools were not called.",
        }
    ]
    tools_used = ["sql_agent", tool_name]
    if error:
        answer = (
            "I could not run that query on the factory tables "
            f"({error}). Ask again, or turn off SQL_AGENT_MODE to use the registered tools."
        )
        logger.info("sql_agent fail conversation=%s tool=%s", conversation_id, tool_name)
        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "tools_used": tools_used,
            "traces": traces,
            "proposed_actions": [],
            "limitation": "sql_rejected",
            "routing_intent": "proceed",
        }

    hits = retrieve_answer_templates(message)
    hits = supplement_templates_for_tools(message, hits, [tool_name])
    extra = format_retrieved_templates(hits)
    payload = json.dumps(rows, ensure_ascii=False, default=str)
    if len(payload) > 6000:
        payload = payload[:6000] + "…"
    user = f"Manager:\n{message}\n\nSQL_ROWS ({len(rows)} rows):\n{payload}"
    if extra:
        user = extra + "\n\n" + user
    answer = _ask_text(model, _COMPOSE_SYS, user)
    logger.info(
        "sql_agent done conversation=%s tool=%s rows=%s",
        conversation_id,
        tool_name,
        len(rows),
    )
    return {
        "answer": answer,
        "conversation_id": conversation_id,
        "tools_used": tools_used,
        "traces": traces,
        "proposed_actions": [],
        "limitation": None,
        "routing_intent": "proceed",
    }
