"""Switches for the three-condition evaluation. Unset means the live product."""

from __future__ import annotations

import os


def _off(name: str) -> bool:
    return os.getenv(name, "1").strip().lower() in {"0", "false", "no", "off"}


def semantic_layer_enabled() -> bool:
    return not _off("EVAL_SEMANTIC_LAYER")


def response_templates_enabled() -> bool:
    return not _off("EVAL_RESPONSE_TEMPLATES")


def few_shot_mode() -> str:
    """full, exclude_exact, or off. The default is full, which is today's retrieval."""
    raw = os.getenv("EVAL_FEW_SHOT", "full").strip().lower().replace("-", "_")
    if raw in {"off", "none", "0", "false", "no"}:
        return "off"
    if raw in {"exclude_exact", "exclude"}:
        return "exclude_exact"
    return "full"
