"""Semantic layer covers every stored column and renders into the system prompt."""

from __future__ import annotations

from backend.agent.prompts import build_system_prompt
from backend.pg_config import PG_SCHEMA
from backend.services.pg_database import connect
from backend.services.semantic import load_semantic_layer, render_semantic_prompt


def _database_columns(table_name: str) -> set[str]:
    with connect(admin=True) as connection:
        rows = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (PG_SCHEMA, table_name),
        ).fetchall()
    columns = {row["column_name"] for row in rows}
    if table_name == "production_log":
        columns.remove("production_date")
        columns.add("date")
    return columns


def test_semantic_layer_covers_database_columns(db):
    load_semantic_layer.cache_clear()
    layer = load_semantic_layer()
    tables = layer["data_definition"]["tables"]
    assert set(tables["orders"]["columns"]) == _database_columns("orders")
    assert set(tables["production_log"]["columns"]) == _database_columns("production_log")
    assert set(tables["workshops"]["columns"]) == _database_columns("workshops")
    for table in tables.values():
        for col in (table.get("columns") or {}).values():
            assert str(col.get("description") or "").strip()


def test_semantic_prompt_includes_field_descriptions_and_terms():
    load_semantic_layer.cache_clear()
    text = render_semantic_prompt()
    assert "How many garments in this order" in text
    assert "selling_price" in text
    assert "factory_today" in text
    assert "feasibility" in text
    assert "check_feasibility" in text


def test_system_prompt_embeds_semantic_layer():
    prompt = build_system_prompt()
    assert "Semantic layer" in prompt
    assert "get_order_status" in prompt
