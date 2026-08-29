"""Semantic layer covers every CSV column and renders into the system prompt."""

from __future__ import annotations

from backend.agent.prompts import build_system_prompt
from backend.services.database import (
    _ORDERS_COLUMNS,
    _PRODUCTION_COLUMNS,
    _WORKSHOP_COLUMNS,
)
from backend.services.semantic import load_semantic_layer, render_semantic_prompt


def test_semantic_layer_covers_csv_columns():
    load_semantic_layer.cache_clear()
    layer = load_semantic_layer()
    tables = layer["data_definition"]["tables"]
    assert set(tables["orders"]["columns"]) == set(_ORDERS_COLUMNS)
    assert set(tables["production_log"]["columns"]) == set(_PRODUCTION_COLUMNS)
    assert set(tables["workshops"]["columns"]) == set(_WORKSHOP_COLUMNS)
    for table in tables.values():
        for col in (table.get("columns") or {}).values():
            assert str(col.get("description") or "").strip()


def test_semantic_prompt_includes_field_descriptions_and_terms():
    load_semantic_layer.cache_clear()
    text = render_semantic_prompt()
    assert "How many garments in this order" in text
    assert "selling_price" in text
    assert "factory_today" in text


def test_system_prompt_embeds_semantic_layer():
    prompt = build_system_prompt()
    assert "Semantic layer" in prompt
    assert "get_order_status" in prompt
