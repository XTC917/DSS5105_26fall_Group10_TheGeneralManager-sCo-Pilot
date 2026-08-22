"""Shared fixtures. The session DB is loaded from the real Track 1 CSVs."""

from __future__ import annotations

import json

import pytest

from backend.services.database import get_db, init_db


@pytest.fixture(scope="session")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "factory.db"
    init_db(db_path=path)
    return get_db()


def parse_tool(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data
