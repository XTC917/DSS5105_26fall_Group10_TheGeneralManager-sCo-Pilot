"""Load data/semantic_layer.yaml and render it for the agent prompt.

data_definition = tables, columns, and field descriptions.
term_definition = special vocabulary that is not itself a stored column.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from backend.config import SEMANTIC_LAYER_PATH


@lru_cache(maxsize=1)
def load_semantic_layer() -> dict[str, Any]:
    if not SEMANTIC_LAYER_PATH.exists():
        raise FileNotFoundError(
            f"Semantic layer missing: {SEMANTIC_LAYER_PATH}. "
            "Copy the template or restore data/semantic_layer.yaml."
        )
    with SEMANTIC_LAYER_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("semantic_layer.yaml must be a mapping at the top level.")
    if "data_definition" not in data or "term_definition" not in data:
        raise ValueError("semantic_layer.yaml must have data_definition and term_definition.")
    return data


def render_semantic_prompt(layer: dict[str, Any] | None = None) -> str:
    data = layer if layer is not None else load_semantic_layer()
    data_def = data.get("data_definition") or {}
    term_def = data.get("term_definition") or {}
    lines: list[str] = [
        "## Semantic layer",
        "data_definition describes stored tables and columns.",
        "term_definition explains special vocabulary (not extra CSV columns).",
        "Do not invent columns. Formulas stay in Python tools.",
        "",
        "### Data definition",
        "",
    ]

    tables = data_def.get("tables") or {}
    for table_key, table in tables.items():
        physical = table.get("physical_name") or table_key
        source = table.get("source") or ""
        header = f"#### Table `{physical}`"
        if source:
            header += f" (source: {source})"
        lines.append(header)
        grain = (table.get("grain") or "").strip()
        if grain:
            lines.append(f"Grain: {grain}")
        desc = (table.get("description") or "").strip()
        if desc:
            lines.append(desc)
        for col_name, col in (table.get("columns") or {}).items():
            lines.extend(_render_data_column(col_name, col or {}))
        lines.append("")

    terms = term_def.get("terms") or {}
    if terms:
        lines.extend(["### Term definition", ""])
        for name, term in terms.items():
            lines.append(_render_term(name, term or {}))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_data_column(name: str, col: dict[str, Any]) -> list[str]:
    physical = col.get("physical_name") or name
    bits: list[str] = []
    if col.get("type"):
        bits.append(str(col["type"]))
    if col.get("nullable") is True:
        bits.append("nullable")
    if col.get("nullable") is False:
        bits.append("required")
    allowed = col.get("allowed_values")
    if allowed:
        bits.append("values: " + ", ".join(str(v) for v in allowed))
    suffix = f" [{'; '.join(bits)}]" if bits else ""
    parts = [f"- `{physical}`{suffix}"]
    desc = (col.get("description") or "").strip()
    if desc:
        parts.append(f"  {desc}")
    return parts


def _render_term(name: str, term: dict[str, Any]) -> str:
    desc = (term.get("description") or "").strip()
    line = f"- `{name}`"
    if term.get("in_dataset") is False:
        line += " [not a stored column]"
    extra = []
    if term.get("computed_in"):
        extra.append(str(term["computed_in"]))
    if term.get("tool"):
        extra.append(f"via `{term['tool']}`")
    if extra:
        line += f" ({'; '.join(extra)})"
    if desc:
        line += f": {desc}"
    confuse = term.get("do_not_confuse_with") or []
    if confuse:
        line += f" (do not confuse with: {', '.join(str(x) for x in confuse)})"
    return line
