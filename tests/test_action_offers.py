"""Yes/no action offers stay inside actions the turn can already execute."""

from backend.services import action_offers as offers


ORDER = {
    "order_id": "ORD-120",
    "status": "IN_PROGRESS",
    "customer": "TrendCart",
    "due_date": "2026-03-17",
}


def _traces(*rows: dict) -> list[dict]:
    return [{"rows": list(rows)}]


def _lookup(order_id: str) -> dict:
    if order_id == "ORD-108":
        return {
            "order_id": "ORD-108",
            "status": "IN_PROGRESS",
            "customer": "Harbor Knits",
            "due_date": "2026-04-10",
        }
    return {**ORDER, "order_id": order_id}


def test_one_in_progress_order_can_be_watched(monkeypatch):
    monkeypatch.setattr(offers, "factory_date", lambda: __import__("datetime").date(2026, 4, 1))
    found = offers.candidate_offers(_traces({"order_id": "ORD-120"}), lookup=_lookup)
    assert [item["id"] for item in found] == ["create_watch:ORD-120"]
    assert found[0]["action"]["check_date"] == "2026-04-02"
    assert found[0]["action"]["order_id"] == "ORD-120"


def test_due_today_can_be_watched_today(monkeypatch):
    monkeypatch.setattr(offers, "factory_date", lambda: __import__("datetime").date(2026, 4, 1))
    found = offers.candidate_offers(
        _traces({"order_id": "ORD-029", "due_date": "2026-04-01", "status": "IN_PROGRESS"}),
        lookup=lambda order_id: {
            "order_id": order_id,
            "status": "IN_PROGRESS",
            "due_date": "2026-04-01",
        },
    )
    assert found[0]["action"]["check_date"] == "2026-04-01"


def test_projected_finish_is_the_watch_date(monkeypatch):
    monkeypatch.setattr(offers, "factory_date", lambda: __import__("datetime").date(2026, 4, 1))
    found = offers.candidate_offers(
        _traces(
            {
                "order_id": "ORD-120",
                "status": "IN_PROGRESS",
                "due_date": "2026-03-17",
                "days_left": 6.3,
            }
        ),
        lookup=_lookup,
    )
    assert found[0]["action"]["check_date"] == "2026-04-08"


def test_finish_today_moves_to_the_next_day_unless_due_today(monkeypatch):
    monkeypatch.setattr(offers, "factory_date", lambda: __import__("datetime").date(2026, 4, 1))
    overdue = offers.candidate_offers(
        _traces({"order_id": "ORD-120", "days_left": 1}),
        lookup=_lookup,
    )
    assert overdue[0]["action"]["check_date"] == "2026-04-02"
    due_today = offers.candidate_offers(
        _traces({"order_id": "ORD-029", "due_date": "2026-04-01", "days_left": 1}),
        lookup=lambda order_id: {
            "order_id": order_id,
            "status": "IN_PROGRESS",
            "due_date": "2026-04-01",
            "days_left": 1,
        },
    )
    assert due_today[0]["action"]["check_date"] == "2026-04-01"


def test_a_series_keeps_every_order_for_the_model():
    found = offers.candidate_offers(
        _traces({"order_id": "ORD-120", "flags": ["OVERDUE"]}, {"order_id": "ORD-108"}),
        lookup=_lookup,
    )
    assert "create_watch:ORD-120" in [item["id"] for item in found]
    assert "create_watch:ORD-108" in [item["id"] for item in found]


def test_same_card_is_the_only_drop():
    found = offers.candidate_offers(
        _traces({"order_id": "ORD-120"}),
        proposed_actions=[{"type": "create_watch", "order_id": "ORD-120"}],
        lookup=_lookup,
    )
    assert [item["id"] for item in found] == []


def test_model_can_choose_the_one_problem_in_a_series(monkeypatch):
    monkeypatch.setattr(offers, "_choose_with_model", lambda *args, **kwargs: "create_watch:ORD-120")
    offer = offers.compose_action_offer(
        "How are ORD-120 and ORD-108 doing?",
        "ORD-120 is overdue. ORD-108 is on track.",
        _traces({"order_id": "ORD-120"}, {"order_id": "ORD-108"}),
        lookup=_lookup,
    )
    assert offer["action"]["type"] == "create_watch"
    assert offer["action"]["order_id"] == "ORD-120"


def test_unknown_offer_is_dropped(monkeypatch):
    monkeypatch.setattr(offers, "_choose_with_model", lambda *args, **kwargs: "delete_factory")
    offer = offers.compose_action_offer(
        "How is ORD-120 doing?",
        "ORD-120 is overdue.",
        _traces({"order_id": "ORD-120"}),
        lookup=_lookup,
    )
    assert offer is None
