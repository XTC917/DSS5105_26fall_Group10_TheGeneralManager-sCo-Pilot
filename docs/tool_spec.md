# Tool specification (MVP)

All formulas live in Python (`backend/services/calculations.py`,
`backend/services/feasibility.py`). The LLM must not recompute them.

Unsupported questions (revenue, selling price, profit, worker names) are
rejected by `backend/agent/routing.py` **before** any tool runs. Do not call
`get_order_status` / `get_orders_at_risk` / `check_feasibility` just to discover
that a field is missing.

Factory today = **2026-04-01**. Working day = Monday–Saturday.

---

## `get_order_status` (retrieval)

**Inputs:** `order_id`, `customer`, and/or `product` (all optional, at least one required).

**Behaviour:**

- Filters `orders.csv` with case-insensitive exact match.
- 0 rows → `NOT_FOUND`.
- 2+ rows → `AMBIGUOUS` + candidate list. Agent must ask for `order_id`.
- 1 row → order fields + computed date/stage fields.

**Computed fields:**

| Name | Formula |
|---|---|
| `calendar_days_until_due` | `due_date − 2026-04-01` (signed, calendar days) |
| `working_days_until_due_inclusive` | Count of Mon–Sat from today through `due_date`; `0` if overdue |
| `working_days_since_last_activity` | Count of Mon–Sat after `last_activity_date` through today |
| `remaining_stages` | From `current_stage` through PACKING; empty if COMPLETE |

**Trace:** `source_file=orders.csv`, the matching row, the computed fields.

---

## `get_orders_at_risk` (retrieval + inspectable flags)

Only `status = IN_PROGRESS`. An order is at risk if any flag below is true.

| Flag | Definition |
|---|---|
| `OVERDUE` | `due_date < 2026-04-01` |
| `STALLED` | working days since `last_activity_date` ≥ **3** (`STALL_WORKING_DAYS`) |
| `TIGHT_DEADLINE` | not overdue, and `working_days_until_due_inclusive < remaining_stage_count` |

`TIGHT_DEADLINE` is a **heuristic**. The dataset does not tell us how many pieces
are left at the current stage, so we require at least one working day per remaining stage.

Optional input `flag` filters to one of the three names.

Ranking: overdue first (more calendar days late = higher), then tight, then stalled.

COMPLETE orders are never at risk.

---

## `trace_order` (tracing)

**Input:** `order_id`.

Returns the `orders.csv` row, computed fields, risk flags, and calculations.

**Limitation (do not invent a join):** `production_log.csv` is factory-wide
(`date × stage`), not per order. The only per-order activity timestamp is
`last_activity_date`.

---

## `check_feasibility` (judgement, MVP)

**Inputs:** `pieces`, `due_date` (YYYY-MM-DD), `product` and/or `category`.

**Category resolution:** look up `product` in `orders.csv` (case-insensitive).
Simple plurals of names that already exist in that file are accepted:
`beanies` → Beanie → ACCESSORIES; `hoodies` → Hoodie → TOPS; `scarves` → Scarf → ACCESSORIES.
This is string normalisation of known names, not an invented product list.
A name that is not in `orders.csv` (e.g. Spaceship) without a category → `UNKNOWN_PRODUCT`.
Do not ask the manager to type TOPS/ACCESSORIES for ordinary dataset garments.

**Steps:**

1. `working_days` = Mon–Sat from 2026-04-01 through `due_date` inclusive (`0` if past).
2. For each stage, take the **median** `pieces_completed` on the last **30** working days
   in `production_log.csv` (Sundays excluded; dates before factory today).
3. `bottleneck_median` = minimum of those four medians.
4. `factory_window_capacity` = `bottleneck_median × working_days`.
5. `in_progress_pieces` = sum of `pieces` for all `IN_PROGRESS` orders.
6. `spare_factory_capacity` = `max(0, factory_window_capacity − in_progress_pieces)`.
7. For each **ACTIVE** workshop whose `makes` includes the category:

   ```
   available_days = max(0, working_days − pickup_lead_days − current_queue_days)
   raw = capacity_pieces_per_day × (1 − defect_rate) × available_days
   effective = min(raw, max_batch_pieces)  if max_batch_pieces is set, else raw
   ```

   `SUSPENDED` workshops are excluded. MVP models **one new batch** per workshop.

**How the agent must present this:** it is a planning estimate under the
heuristic above, not a guaranteed factory outcome. Preferred wording:
“Under the current capacity heuristic…” and “Estimated spare capacity under
this model…”. Always keep the `limitations` list from the tool.

**Verdict:**

| Value | When |
|---|---|
| `FEASIBLE_IN_HOUSE` | `pieces ≤ spare_factory_capacity` and due is not in the past |
| `FEASIBLE_WITH_WORKSHOPS` | not in-house, but `pieces ≤ spare + workshop_overflow` |
| `NOT_FEASIBLE` | otherwise, or due date before factory today |

### TODO — not modelled yet (do not silently add)

- Sequential four-stage pipeline latency (first piece is not packed on day 1).
- Partial remaining work on IN_PROGRESS orders (we count full piece counts).
- Multiple workshop batches over the window.
- Selling price / margin (not in the dataset).

---

## Not in this MVP

| Tool | Status |
|---|---|
| `assess_stage_performance` | TODO |
| `discover_factory_issues` | placeholder file only |
| `draft_chase_email` / `send_email` / `add_order_note` / `create_reminder` | placeholder; must require confirmation + audit log |
