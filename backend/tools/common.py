"""Shared helpers for tool results.

Every tool returns a JSON string so the LLM can read it, and so the API can
parse traces for the UI. Tools never raise into the agent graph — they return
structured errors instead.
"""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

# None: guard off (direct tool tests). A string: order ids must appear in it.
_MANAGER_TEXT: ContextVar[str | None] = ContextVar("manager_text", default=None)


def set_manager_text(text: str | None):
    return _MANAGER_TEXT.set(text)


def reset_manager_text(token: Any) -> None:
    _MANAGER_TEXT.reset(token)


def order_id_named_by_manager(order_id: str | None) -> bool:
    """True when this chat turn did not restrict ids, or the manager wrote this id."""
    return value_named_by_manager(order_id)


def value_named_by_manager(value: str | None) -> bool:
    """True when the guard is off, or the manager's words contain this filter value."""
    cleaned = (value or "").strip()
    if not cleaned:
        return True
    text = _MANAGER_TEXT.get()
    if text is None:
        return True
    if re.search(rf"\b{re.escape(cleaned)}\b", text, re.I):
        return True
    return cleaned.lower() in text.lower()


def manager_text() -> str:
    return _MANAGER_TEXT.get() or ""


def several_orders_message(count: int) -> str:
    if re.search(r"[\u4e00-\u9fff]", manager_text()):
        return f"有 {count} 笔订单对得上。点一笔订单号，或在「其他」里写明要查哪一笔。"
    return f"{count} orders match. Pick one, or type the order you mean."


def ungrounded_order_error(tool: str, order_id: str) -> str:
    return tool_error(
        tool,
        "UNGROUNDED_ID",
        (
            f"{order_id} was not in the manager's question. "
            "Do not take an order id from an answer template or a field example. "
            "Call again using only the customer, product, or other words they used. "
            "If several rows match, stop and ask which order id."
        ),
    )


def tool_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def tool_error(tool: str, code: str, message: str, **extra: Any) -> str:
    logger.warning("tool error %s %s: %s", tool, code, message)
    error: dict[str, Any] = {"code": code, "message": message}
    error.update(extra)
    return tool_json({"ok": False, "tool": tool, "error": error})
