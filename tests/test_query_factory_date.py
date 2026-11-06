"""A clock two or more days past the data queries the day after the newest record."""

from datetime import date

from backend.services.factory_clock import data_hold_note, query_date_for


def test_clock_inside_the_data_is_used_as_is():
    assert query_date_for(date(2026, 3, 30), date(2026, 4, 1)) == date(2026, 3, 30)


def test_one_day_ahead_keeps_the_clock():
    assert query_date_for(date(2026, 4, 2), date(2026, 4, 1)) == date(2026, 4, 2)


def test_two_or_more_days_ahead_queries_the_day_after_the_newest_record():
    latest = date(2026, 4, 1)
    assert query_date_for(date(2026, 4, 3), latest) == date(2026, 4, 2)
    assert query_date_for(date(2026, 4, 6), latest) == date(2026, 4, 2)
    assert data_hold_note(latest) == (
        "**Data is current through 2026-04-01. Records after that date have not been updated.**"
    )
    assert data_hold_note(latest, "ORD-120 怎么样") == "**回答截止到 2026-04-01，之后的数据还未更新。**"


def test_missing_records_keep_the_clock():
    assert query_date_for(date(2026, 4, 2), None) == date(2026, 4, 2)
