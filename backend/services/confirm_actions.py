"""Execute a proposed action after the manager clicks Confirm in the UI.

No LLM. The client cannot choose an arbitrary tool: only the whitelist below,
and `confirmed=true` is forced here.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.services.audit import record_event
from backend.tools.actions import add_order_note, create_reminder, send_email
from backend.tools.watches import cancel_watch, create_watch

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS: dict[str, tuple[Any, tuple[str, ...]]] = {
    "create_watch": (create_watch, ("order_id", "condition_type", "check_date", "message")),
    "cancel_watch": (cancel_watch, ("order_id", "watch_id")),
    "send_email": (send_email, ("order_id",)),
    "add_order_note": (add_order_note, ("order_id", "note")),
    "create_reminder": (create_reminder, ("order_id", "remind_on", "message")),
}


class ConfirmError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_tool_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfirmError("INTERNAL", "Tool returned invalid JSON.") from exc
    raise ConfirmError("INTERNAL", "Tool did not return JSON.")


def confirm_proposed_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ConfirmError("INVALID_INPUT", "action must be an object.")
    kind = action.get("type")
    if kind not in ALLOWED_ACTIONS:
        raise ConfirmError(
            "UNSUPPORTED",
            "That action cannot be confirmed from the UI.",
        )
    tool, keys = ALLOWED_ACTIONS[kind]
    kwargs: dict[str, Any] = {}
    for key in keys:
        value = action.get(key)
        if value is None or value == "":
            continue
        kwargs[key] = value
    kwargs["confirmed"] = True
    logger.info("ui confirm type=%s keys=%s", kind, sorted(k for k in kwargs if k != "confirmed"))
    payload = _parse_tool_result(tool.invoke(kwargs))
    return {
        "ok": bool(payload.get("ok")),
        "type": kind,
        "tool": payload.get("tool") or kind,
        "data": payload.get("data") or {},
        "error": payload.get("error"),
        "trace": payload.get("trace"),
        "summary": _result_summary(kind, payload),
    }


def decline_proposed_action(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ConfirmError("INVALID_INPUT", "action must be an object.")
    kind = action.get("type") or "unknown"
    if kind not in ALLOWED_ACTIONS and kind != "unknown":
        raise ConfirmError("UNSUPPORTED", "That action cannot be declined from the UI.")
    record_event(
        event_type="action_declined",
        tool=kind if kind in ALLOWED_ACTIONS else None,
        inputs={"type": kind, "order_id": action.get("order_id"), "watch_id": action.get("watch_id")},
        result_ok=True,
        result_summary=f"{kind} declined in UI",
        confirmation_status="declined",
        execution_status="not_saved",
        target=action.get("order_id"),
    )
    return {"ok": True, "type": kind, "declined": True}


def _result_summary(kind: str, payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        err = payload.get("error") or {}
        return err.get("message") or "Confirmation failed."
    data = payload.get("data") or {}
    if kind == "create_watch":
        return (
            f"Watch saved for {data.get('order_id')} "
            f"(id {data.get('watch_id')}, {data.get('check_date')})."
        )
    if kind == "cancel_watch":
        return (
            f"Watch {data.get('watch_id')} for {data.get('order_id')} is CANCELLED "
            "(kept in history, not deleted)."
        )
    if kind == "add_order_note":
        return f"Note saved locally on {data.get('order_id')}."
    if kind == "create_reminder":
        return f"Reminder saved locally for {data.get('order_id')} on {data.get('remind_on')}."
    if kind == "send_email":
        return (
            f"Simulated send recorded for {data.get('order_id') or data.get('draft', {}).get('order_id')}. "
            "No email was actually sent."
        )
    return "Action confirmed."
