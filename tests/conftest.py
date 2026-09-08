"""Shared fixtures. The session DB is loaded from the real Track 1 CSVs."""

from __future__ import annotations

import json

import pytest

from backend.services.database import get_db, init_db


@pytest.fixture(scope="session")
def db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("db")
    init_db(db_path=tmp / "factory.db", state_db_path=tmp / "state.db")
    return get_db()


@pytest.fixture
def clean_state(db):
    from backend.services.audit import clear_state

    clear_state()
    yield
    clear_state()


def parse_tool(raw: str) -> dict:
    data = json.loads(raw)
    assert isinstance(data, dict)
    return data
