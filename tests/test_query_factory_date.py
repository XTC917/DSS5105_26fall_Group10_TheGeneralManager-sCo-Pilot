"""The chosen factory date is the query date. A used CSV older than that date is named."""

from datetime import date

from backend.services.factory_clock import named_csvs, partial_update_note, query_date_for, stale_csv_updates


class _Updates:
    def __init__(self, updates):
        self.updates = updates

    def csv_latest_updates(self):
        return self.updates


def test_any_clock_is_the_query_date():
    assert query_date_for(date(2026, 3, 30), date(2026, 4, 1)) == date(2026, 3, 30)
    assert query_date_for(date(2026, 4, 2), date(2026, 4, 1)) == date(2026, 4, 2)
    assert query_date_for(date(2026, 4, 6), date(2026, 4, 1)) == date(2026, 4, 6)
    assert query_date_for(date(2026, 4, 2), None) == date(2026, 4, 2)


def test_note_names_only_a_used_csv_older_than_the_factory_date():
    db = _Updates({
        "orders.csv": date(2026, 4, 1),
        "production_log.csv": date(2026, 3, 31),
    })
    day = date(2026, 4, 1)
    assert named_csvs("production_log.csv + orders.csv + workshops.csv") == {
        "orders.csv",
        "production_log.csv",
    }
    assert stale_csv_updates(db, {"orders.csv"}, day) == []
    stale = stale_csv_updates(db, {"production_log.csv"}, day)
    assert stale == [("production_log.csv", date(2026, 3, 31))]
    assert partial_update_note(stale) == (
        "**Some of the data used here was last updated through 2026-03-31 (production_log).**"
    )
    assert partial_update_note(stale, "今天的产量") == "**部分数据的更新时间截止 2026-03-31（production_log）。**"


def test_note_lists_each_csv_when_their_updates_differ():
    db = _Updates({
        "orders.csv": date(2026, 4, 1),
        "production_log.csv": date(2026, 3, 31),
    })
    stale = stale_csv_updates(db, {"orders.csv", "production_log.csv"}, date(2026, 4, 2))
    assert partial_update_note(stale, "订单和产量") == (
        "**部分数据的更新时间截止 orders 2026-04-01、production_log 2026-03-31。**"
    )
