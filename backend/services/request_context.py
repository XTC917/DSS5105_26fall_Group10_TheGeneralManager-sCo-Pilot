"""Per-request authenticated identity for Copilot ownership checks.

Ownership must come from the authenticated request, never from a
client-provided user_id. API routes set the current user; Agent tools and
services read it from here. Defaults to None outside an HTTP request.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_current_user: ContextVar[Any | None] = ContextVar("copilot_current_user", default=None)


def set_current_user(user: Any | None) -> None:
    _current_user.set(user)


def get_current_user_id(required: bool = True) -> int | None:
    user = _current_user.get()
    user_id = getattr(user, "id", None) if user is not None else None
    if user_id is None and required:
        raise PermissionError("Authentication required")
    return user_id


def require_user_match(row_user_id: Any, *, message: str = "Not found") -> None:
    current_id = get_current_user_id(required=True)
    if row_user_id is None or int(row_user_id) != int(current_id):
        raise PermissionError(message)


def scoped_user_id(explicit: int | None) -> int | None:
    """Resolve ownership: explicit test user wins, else the request user."""
    if explicit is not None:
        return explicit
    return get_current_user_id(required=False)
