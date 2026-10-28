from datetime import date, timedelta

from statistics import median

from backend.agent.uc_answers import compose_uc_why, match_uc_answer, stage_daily_chart, uc_why_traces
from backend.services.why import build_why


EXACT = (
    "You will be given today's overall factory briefing, including risks, "
    "work in progress, output,and suspended workshops."
)


def test_uc_answer_matches_only_the_exact_question():
    hit = match_uc_answer(EXACT)
    assert hit is not None
    assert "34 active orders" in hit["answer"]
    assert hit["reserve_chart"] is True


def test_stage_daily_chart_is_assembly_median_and_alert():
    today = date(2026, 4, 1)
    log = [
        {"date": "2026-03-02", "stage": "KNITTING", "pieces_completed": 10},
        {"date": "2026-03-02", "stage": "KNITTING", "pieces_completed": 5},
        {"date": "2026-03-08", "stage": "ASSEMBLY", "pieces_completed": 100},
        {"date": "2026-03-01", "stage": "KNITTING", "pieces_completed": 999},
        {"date": "2026-04-01", "stage": "KNITTING", "pieces_completed": 999},
    ]
    # Fill the other working days so the window is the last 30, not just two dates.
    cursor = date(2026, 2, 1)
    while cursor < today:
        if cursor.weekday() != 6:
            log.append({"date": cursor.isoformat(), "stage": "PACKING", "pieces_completed": 2})
        cursor += timedelta(days=1)
    chart = stage_daily_chart(log, today)
    assert chart["type"] == "stage_daily"
    assert len(chart["data"]) == 30
    assert chart["data"][0]["date"] == "2026-02-25"
    assert chart["data"][-1]["date"] == "2026-03-31"
    assert "2026-03-08" not in {row["date"] for row in chart["data"]}
    assert all(date.fromisoformat(row["date"]).weekday() != 6 for row in chart["data"])
    assert all(row["date"] != "2026-04-01" for row in chart["data"])
    assert chart["stages"] == [{"key": "ASSEMBLY", "color": "#4c78a8", "median": chart["stages"][0]["median"]}]
    assert "KNITTING" not in chart["data"][0]
    expected = round(float(median([row["ASSEMBLY"] for row in chart["data"]])), 1)
    assert chart["stages"][0]["median"] == expected
    assert chart["data"][0]["median"] == expected
    assert chart["data"][0]["alert_threshold"] == round(expected * 0.7, 1)
    labeled = stage_daily_chart(log, today, median=758)
    assert labeled["stages"][0]["median"] == 758
    assert labeled["threshold"] == 530.6
    assert labeled["label_date"] == "2026-03-31"


def test_uc_why_matches_the_pinned_four_steps():
    why = build_why(EXACT, {"answer": "Today's main focus", "traces": uc_why_traces()})
    items = [item for step in why["steps"] for item in step["items"]]
    assert items[0] == EXACT
    assert "Order: ORD-029; Customer: Northwind Apparel; Product: Beanie; Pieces: 1500; Due date: 2026-04-01; Current stage: WASHING." in items
    assert "Order: ORD-108; Customer: Harbor Knits; Product: Scarf; Pieces: 2000; Due date: 2026-04-03; Current stage: ASSEMBLY." in items
    assert "Order: ORD-103; Customer: Bright Basics; Product: Scarf; Pieces: 2000; Due date: 2026-04-04; Current stage: ASSEMBLY." in items
    assert any(r"\mathrm{days}_{\mathrm{left}}" in item for item in items)
    assert items[-1] == "Read the answer against the facts and checks above. These records alone do not establish business causation."
    assert why["sources"] == []
    sourced = compose_uc_why(EXACT, "Today's main focus", {
        "source_file": "orders.csv, production_log.csv, workshops.csv",
        "rows": [{
            "order_id": "ORD-029",
            "customer": "Northwind Apparel",
            "product": "Beanie",
            "pieces": 1500,
            "due_date": "2026-04-01",
            "current_stage": "WASHING",
        }],
    })
    assert [item for step in sourced["steps"] for item in step["items"]] == items
    assert sourced["sources"] == [{
        "name": "orders.csv, production_log.csv, workshops.csv",
        "row_count": 1,
        "rows": [],
        "summary_only": True,
    }]


def test_uc_answer_misses_a_one_character_change():
    assert match_uc_answer(EXACT.replace("output,and", "output, and")) is None
    assert match_uc_answer(EXACT + " ") is None
    assert match_uc_answer("Which of these did you mean?\n" + EXACT) is None
