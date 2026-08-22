"""Shared helpers for tool results.

Every tool returns a JSON string so the LLM can read it, and so the API can
parse traces for the UI. Tools never raise into the agent graph — they return
structured errors instead.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def tool_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def tool_error(tool: str, code: str, message: str, **extra: Any) -> str:
    logger.warning("tool error %s %s: %s", tool, code, message)
    error: dict[str, Any] = {"code": code, "message": message}
    error.update(extra)
    return tool_json({"ok": False, "tool": tool, "error": error})
