"""Compare the agent's tool data with the data that tool should return.

A read tool is called again in code, with the question's tool_args, on the
same factory date. The two data payloads must be the same JSON. Display tools
are not that payload: a chart question passes when a chart was returned, a
table question when a table was returned. A question with no business tool
passes when the agent returned no business data. Write tools are not called a
second time; the returned data must contain the order ids the question names
and the argument values stored on the question.
"""

from __future__ import annotations

import json
import re
from typing import Any

_WRITE_TOOLS = {
    "send_email",
    "draft_chase_email",
    "add_order_note",
    "create_reminder",
    "create_watch",
    "cancel_watch",
}
_DISPLAY_TOOLS = {"draw", "render_table", "filter_rows", "summarize_rows"}
_DROP_KEYS = {"trace", "generated_at", "timestamp", "created_at"}
_ORDER_ID = re.compile(r"ORD-\d+", re.IGNORECASE)


def compare_tool_run(
    case: dict[str, Any],
    parsed: dict[str, Any],
    *,
    stored_reference: Any = None,
) -> dict[str, Any]:
    """Score one run. Read tools compare data. The other modes are named in `mode`."""
    tool_name = str(case.get("relevant_tool") or "").strip()
    expected_args = case.get("tool_args") if isinstance(case.get("tool_args"), dict) else {}
    if not tool_name:
        match = not _business_payloads(parsed)
        return {
            "scored": True,
            "match": match,
            "mode": "no_data",
            "reason": "no business data, as specified" if match else "a business tool returned data",
        }
    if tool_name == "assess_ambiguity":
        match = bool(parsed.get("clarification"))
        return {
            "scored": True,
            "match": match,
            "tool": tool_name,
            "mode": "clarification",
            "reason": "clarification returned" if match else "no clarification card",
        }
    if tool_name == "draw":
        match = bool(parsed.get("charts"))
        return {
            "scored": True,
            "match": match,
            "tool": tool_name,
            "mode": "display",
            "reason": "chart returned" if match else "no chart",
        }
    if tool_name == "render_table":
        match = bool(parsed.get("tables"))
        return {
            "scored": True,
            "match": match,
            "tool": tool_name,
            "mode": "display",
            "reason": "table returned" if match else "no table",
        }
    agent_hit = _agent_payload(parsed, tool_name)
    if agent_hit is None:
        return {
            "scored": True,
            "match": False,
            "tool": tool_name,
            "mode": "data",
            "reason": "agent did not return this tool's data",
        }
    if tool_name in _WRITE_TOOLS:
        return _compare_write(tool_name, expected_args, case, agent_hit)
    reference_data = stored_reference
    if reference_data is None:
        reference = invoke_reference(tool_name, expected_args)
        if not reference.get("ok"):
            return {
                "scored": True,
                "match": False,
                "tool": tool_name,
                "mode": "data",
                "reason": "reference tool call failed",
                "reference_error": reference.get("error"),
            }
        reference_data = reference.get("data")
    same = _canonicalize(reference_data) == _canonicalize(agent_hit.get("data"))
    return {
        "scored": True,
        "match": same,
        "tool": tool_name,
        "mode": "data",
        "reason": "data match" if same else "data differ",
        "reference_data": reference_data,
    }


def _compare_write(
    tool_name: str,
    expected_args: dict[str, Any],
    case: dict[str, Any],
    agent_hit: dict[str, Any],
) -> dict[str, Any]:
    data = agent_hit.get("data") or {}
    args = agent_hit.get("args") or {}
    blob = json.dumps({"data": data, "args": args}, ensure_ascii=False, default=str)
    named_ids = {item.upper() for item in _ORDER_ID.findall(str(case.get("question") or ""))}
    ids_ok = all(order_id in blob.upper() for order_id in named_ids)
    args_ok = all(_value_present(value, args, data) for value in expected_args.values())
    match = ids_ok and args_ok
    return {
        "scored": True,
        "match": match,
        "tool": tool_name,
        "mode": "write_data",
        "reason": "returned data contains the requested values" if match else "returned data misses a requested value",
    }


def _value_present(value: Any, args: dict[str, Any], data: Any) -> bool:
    if value in args.values():
        return True
    return str(value) in json.dumps(data, ensure_ascii=False, default=str)


def _business_payloads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in parsed.get("evidence_results") or []
        if isinstance(item, dict) and item.get("tool") not in _DISPLAY_TOOLS
    ]


def invoke_reference(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    """Call one registered read tool. Write tools are refused here."""
    if tool_name in _WRITE_TOOLS or tool_name in _DISPLAY_TOOLS:
        return {"ok": False, "error": "not a reference read tool"}
    from backend.tools.registry import MVP_TOOLS

    tool = next((item for item in MVP_TOOLS if item.name == tool_name), None)
    if tool is None:
        return {"ok": False, "error": f"unknown tool {tool_name}"}
    try:
        raw = tool.invoke(dict(tool_args or {}))
    except Exception as exc:  # noqa: BLE001 — the harness records the failure
        return {"ok": False, "error": str(exc)}
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "error": "tool did not return JSON"}
    elif isinstance(raw, dict):
        payload = raw
    else:
        return {"ok": False, "error": "tool returned an unsupported payload"}
    if not payload.get("ok"):
        return {"ok": False, "error": payload.get("error") or "tool ok=false"}
    return {"ok": True, "data": payload.get("data")}


def _agent_payload(parsed: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    for item in parsed.get("evidence_results") or []:
        if isinstance(item, dict) and item.get("tool") == tool_name:
            return {"data": item.get("data"), "args": item.get("args") or {}}
    return None


def _canonicalize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {
            key: _canonicalize(value[key])
            for key in sorted(value)
            if key not in _DROP_KEYS
        }
    if isinstance(value, list):
        items = [_canonicalize(item) for item in value]
        if items and all(isinstance(item, dict) for item in items):
            items.sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
        return items
    return value
