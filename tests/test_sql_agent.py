from backend.agent.sql_agent import validate_sql
from backend.pg_config import PG_SCHEMA
import pytest


def test_validate_prefixes_and_limits():
    sql = validate_sql("SELECT order_id FROM orders WHERE status='IN_PROGRESS'")
    assert f"{PG_SCHEMA}.orders" in sql.lower()
    assert "limit" in sql.lower()


def test_validate_rejects_write():
    with pytest.raises(ValueError):
        validate_sql("DELETE FROM app.orders")


def test_validate_rejects_other_schema():
    with pytest.raises(ValueError):
        validate_sql("SELECT 1 FROM pg_catalog.pg_tables")
