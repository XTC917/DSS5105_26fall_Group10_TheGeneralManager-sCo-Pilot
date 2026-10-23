"""REVERT-SUMMARIZE: delete this file to drop grouped-count processing.

Holds the latest lookup rows for summarize_rows and filter_rows.
The model never supplies the rows.

Tool tracing runs the tool in a copied context, so the row lists live in a
shared slot. The context only carries the slot id.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from itertools import count
from typing import Any

_KEY: ContextVar[int | None] = ContextVar("lookup_rows_key", default=None)
_SLOTS: dict[int, dict[str, Any]] = {}
_IDS = count(1)

_SKIP_TOOLS = frozenset({"draw", "render_table", "summarize_rows", "filter_rows"})
_ROW_KEYS = ("orders", "series", "rows")


def bind_lookup_rows() -> Token[int | None]:
    key = next(_IDS)
    _SLOTS[key] = {"rows": None, "initial": None, "source": ""}
    return _KEY.set(key)


def reset_lookup_rows(token: Token[int | None]) -> None:
    key = _KEY.get()
    if key is not None:
        _SLOTS.pop(key, None)
    _KEY.reset(token)


def _slot() -> dict[str, Any] | None:
    key = _KEY.get()
    if key is None:
        return None
    return _SLOTS.get(key)


def lookup_rows() -> tuple[list[dict[str, Any]] | None, str]:
    slot = _slot()
    if slot is None:
        return None, ""
    return slot["rows"], slot["source"]


def initial_rows() -> tuple[list[dict[str, Any]] | None, str]:
    """The retrieval rows, before filter_rows narrows the working set."""
    slot = _slot()
    if slot is None:
        return None, ""
    return slot["initial"], slot["source"]


def set_working_rows(rows: list[dict[str, Any]]) -> None:
    slot = _slot()
    if slot is not None:
        slot["rows"] = rows


def note_lookup_payload(payload: dict[str, Any]) -> None:
    """Keep the latest successful lookup rows. Display and summary tools do not replace them."""
    slot = _slot()
    if slot is None or not isinstance(payload, dict) or payload.get("ok") is False:
        return
    tool = str(payload.get("tool") or "").strip()
    if tool in _SKIP_TOOLS:
        return
    rows = _extract_rows(payload)
    if rows is None:
        return
    slot["initial"] = rows
    slot["rows"] = rows
    slot["source"] = tool


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in _ROW_KEYS:
            rows = _dict_rows(data.get(key))
            if rows is not None:
                return rows
        order = data.get("order")
        if isinstance(order, dict) and order:
            return [order]
    trace = payload.get("trace")
    if isinstance(trace, dict):
        return _dict_rows(trace.get("rows"))
    return None


def _dict_rows(value: Any) -> list[dict[str, Any]] | None:
    if isinstance(value, list) and value and all(isinstance(row, dict) for row in value):
        return value
    return None
