"""Action tools with side effects — not executed in this MVP.

Required future pattern (do not silently execute):

    Agent proposes action
    → UI shows the proposal
    → manager explicitly confirms
    → action runs
    → row written to the audit log

Audit record minimum fields:
    timestamp, action_type, target, confirmation_status, execution_status
"""

from __future__ import annotations

from backend.tools.common import tool_error


def draft_chase_email() -> str:
    return _not_implemented("draft_chase_email")


def send_email() -> str:
    return _not_implemented("send_email")


def add_order_note() -> str:
    return _not_implemented("add_order_note")


def create_reminder() -> str:
    return _not_implemented("create_reminder")


def _not_implemented(name: str) -> str:
    return tool_error(
        name,
        "NOT_IMPLEMENTED",
        "Action tools are out of scope for the first MVP. They must never run without confirmation.",
    )
