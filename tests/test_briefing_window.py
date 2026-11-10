"""Deterministic checks for the Weekly briefing Monday–Saturday window.

These are pure functions and do not touch the database, but the shared
`tests/conftest.py` autouse fixture still opens PostgreSQL for the session, so
run the full suite only against a disposable database.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.services.briefing import previous_working_week


def test_weekday_returns_previous_complete_monday_to_saturday():
    # 2026-04-01 is a Wednesday; its week is Mon 3/30 – Sat 4/4, so the
    # previous complete week is Mon 3/23 – Sat 3/28.
    assert previous_working_week(date(2026, 4, 1)) == (date(2026, 3, 23), date(2026, 3, 28))


def test_monday_returns_the_week_that_just_ended():
    # 2026-04-06 is a Monday; the just-ended Mon–Sat is 3/30 – 4/4.
    assert previous_working_week(date(2026, 4, 6)) == (date(2026, 3, 30), date(2026, 4, 4))


def test_sunday_current_behaviour_is_documented():
    """Current main returns the week *before* the one that just finished.

    On Sunday 2026-04-05 the most recently completed Monday–Saturday is
    3/30 – 4/4, but the function returns 3/23 – 3/28. This is recorded here so
    the acceptance-team decision is pinned by a test until the rule is changed
    as a separate, deliberate fix.
    """
    assert previous_working_week(date(2026, 4, 5)) == (date(2026, 3, 23), date(2026, 3, 28))


@pytest.mark.xfail(
    reason=(
        "Desired behaviour: on a Sunday the 'most recently completed' week is the "
        "Monday–Saturday that just ended (3/30 – 4/4). Needs a backend rule change, "
        "tracked as its own fix and intentionally out of scope for Phase 5D."
    ),
    strict=False,
)
def test_sunday_should_return_the_just_finished_week():
    assert previous_working_week(date(2026, 4, 5)) == (date(2026, 3, 30), date(2026, 4, 4))
