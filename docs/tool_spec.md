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

## `get_morning_briefing` (structured ops summary)

No inputs. Returns JSON facts for the LLM to turn into a short briefing.

Reuses `get_orders_at_risk` for overdue / stalled / tight-deadline orders.
Also includes IN_PROGRESS counts by stage, last working day's factory-wide
output from `production_log.csv`, stages whose last-day output is below
`PRODUCTION_DROP_RATIO` (0.70) × the same 30-day median used by feasibility,
and `SUSPENDED` workshops from `workshops.csv`.

**Limitations:** not a canned script; `production_log` is not per-order; no
revenue or worker names.

**Example questions:** "Give me this morning's briefing."

**Unsupported:** selling price, who is on shift.

---

## `find_orders` (user-directed filter)

**Inputs:** at least one of `customer`, `product`, `status`, `current_stage`.

- Customer: case-insensitive exact match.
- Product: names already in `orders.csv`, plus simple plurals (`hoodies` → Hoodie).
- Status: `IN_PROGRESS` or `COMPLETE`.
- Stage: `KNITTING`, `ASSEMBLY`, `WASHING`, `PACKING`, `COMPLETE`.

Returns **all** matching rows (ids + summary fields). Never picks one order.
0 rows → `count: 0`, not an invented customer. Invalid status/stage → `INVALID_INPUT`.
No filters → `INVALID_INPUT` (will not dump the whole table).

This is **not** ranked discovery. It only answers the filter the manager named.

If the manager asks *how* "the TrendCart order" is doing, keep using
`get_order_status` (AMBIGUOUS). Use `find_orders` when they want a list or ids.

**Example questions:** "List the TrendCart orders." / "Which orders are in ASSEMBLY?"

**Unsupported:** arbitrary SQL, fuzzy name search, customer phone/email.

---

## `discover_factory_issues` (ranked discovery, V1)

Proactive, **read-only**. Python finds and sorts issues that already have a
defined rule. The LLM only explains the JSON. No generated SQL. No writes.

**Not** `find_orders`. `find_orders` is user-directed filtering.
**Not** a general anomaly detector. It cannot discover problems the CSVs
cannot define.

**Inputs:** `limit` (integer, default 5, max 20).

**Issue types:**

| Type | Source rule | Priority | Severity |
|---|---|---|---|
| `ORDER_OVERDUE` | `assess_order_risk` flag `OVERDUE` | P1 | high |
| `ORDER_STALLED` | flag `STALLED` (and not overdue) | P2 | medium |
| `ORDER_TIGHT_DUE` | flag `TIGHT_DEADLINE` (and not overdue) | P2 | medium |
| `STAGE_BELOW_BASELINE` | briefing heuristic: last working-day pieces < `0.70` × 30-day median | P3 | low |

One issue per at-risk order. Multiple flags stay on that issue's `evidence`.
Primary type: OVERDUE wins, else TIGHT (same weight as existing `rank_score`), else STALLED.

**Sort (deterministic):** priority ascending, then existing `rank_score`
descending (orders) or ratio ascending (stages), then `issue_id`.

**Output:** `issues`, `total_found`, `returned_count`, `counts_by_type`,
`factory_today` / `as_of`, `limitations`. Each issue has `rule`, `inputs`,
`result`, `source_file`, and `evidence`. Empty → `issues: []` plus a message.
Do not invent issues.

Top-N may omit P3 stage issues when many P1 overdue orders exist; see
`counts_by_type`.

**Example questions:** "What should I be concerned about right now?" /
"Find the top 5 factory issues."

**Unsupported:** revenue; dumping the whole factory; LLM-invented severity.

---

## `draft_chase_email` / `send_email` / `add_order_note` / `create_reminder`

There is **no SMTP, SMS, or calendar integration**.

Confirmation is a **UI click** on Confirm (or a chat “yes” fallback). The
browser posts the `proposed_action` to `POST /api/actions/confirm`; Python
re-invokes the same tool with `confirmed=true`. The LLM is not in that path.

| Tool | Default (`confirmed=false`) | After explicit confirmation |
|---|---|---|
| `draft_chase_email` | Local draft from order fields. `sent: false` | n/a (drafting does not send) |
| `send_email` | Proposal only. `sent: false` | Audit row with `execution_status=SIMULATED`. Still `sent: false` |
| `add_order_note` | Proposal only. `saved: false` | Row in `copilot_state.db` |
| `create_reminder` | Proposal only. `saved: false` | Row in `copilot_state.db`. `notified: false` |

`remind_on` is a factory-calendar ISO date. "Tomorrow" from 2026-04-01 is **2026-04-02**.

**This is not a standing watch.** The `message` is display text only. Nothing
re-checks factory data, and the row never auto-fires.

**Example questions:** "Draft a chase-up email for ORD-120." / "Add a note to ORD-107." / "Create a reminder to check ORD-005 tomorrow."

**Unsupported:** inventing a customer email address; claiming an external send.

---

## `create_watch` (standing watch, V1)

**Not the same as `create_reminder`.** A watch is a typed, inspectable condition.
Python decides whether it has fired. The LLM only maps the manager's words onto
the tool arguments.

**V1 condition (only):** `ORDER_INACTIVE_BY_DATE`

```
as_of >= check_date
AND order.status == IN_PROGRESS
AND order.last_activity_date < check_date
```

"Hasn't moved" means `last_activity_date` is still before `check_date`.
`production_log.csv` is factory-wide (`date × stage`) and is **not** used.

**Inputs:** `order_id`, `check_date` (YYYY-MM-DD or a weekday name), optional
`message` (display only), `confirmed` (default false), `condition_type`
(must be `ORDER_INACTIVE_BY_DATE`).

Weekdays are resolved from **factory today 2026-04-01** (Wednesday), not
`date.today()`. **Thursday → 2026-04-02**.

| `confirmed` | Effect |
|---|---|
| `false` | Proposal only. No row in `watches`. UI shows Confirm / Dismiss. |
| `true` | Insert `watches` with `status=ACTIVE`, `notify_channel=local`. |

COMPLETE orders (e.g. ORD-058) are rejected (`INVALID_INPUT`).

**Evaluation:** `GET /api/watches?as_of=YYYY-MM-DD` calls
`evaluate_active_watches(as_of)`. Default `as_of` is `FACTORY_TODAY`. There is
**no scheduler**. Repeat calls are idempotent: each watch produces at most one
`watch_events` row with `event_type=fired`.

When the condition is true: status becomes `FIRED`, a `watch_events` snapshot is
written, `audit_log` gets `watch_fired`, then `WatchNotifier.notify` runs.
V1 `LocalWatchNotifier` only acknowledges the local row. Notify failures must
not un-fire the watch. SMTP is not implemented.

**Non-goals:** other condition types, reminder-text parsing, LLM judging the
condition, order-level production_log joins, email, cron.

**Example:** "Tell me if ORD-005 hasn't moved by Thursday."

**Failure modes:** missing order → `NOT_FOUND`; completed order or unknown
condition → `INVALID_INPUT`; unparseable date → `INVALID_INPUT`.

---

## `list_watches` (read)

Returns **all** standing watches from `copilot_state.db`, including
`CANCELLED`. Optional `order_id` filter.

Cancel does **not** delete the row. If the manager asks "did we ever watch
ORD-005?", a `CANCELLED` row is the answer: it existed and was stopped.

Also groups `active` / `fired` / `cancelled` so the agent can separate live
watches from history.

---

## `cancel_watch`

Stops an **ACTIVE** watch (it will not evaluate again) or dismisses a **FIRED**
alert (it leaves the live sidebar lists). The watch **row is kept** with
`status=CANCELLED`. `watch_events` and audit rows are also kept.

Same confirmation pattern as create:

| `confirmed` | Effect |
|---|---|
| `false` | Proposal only. Status unchanged. |
| `true` | `status = CANCELLED` |

**Inputs:** `order_id` and/or `watch_id`.

- One match → propose / cancel that row.
- Several ACTIVE/FIRED rows for the same order → `AMBIGUOUS` + candidate `watch_id`s. Do not pick one.
- None → `NOT_FOUND`.
- Already `CANCELLED` → `INVALID_INPUT`.

**Not** `create_reminder`. Calendar reminders are a different table and still do not auto-fire.

**Example:** "Cancel the watch on ORD-005." / "Dismiss the ORD-005 alert."

---

## `get_recent_actions` (audit read)

Returns recent rows from `copilot_state.db`: user query, tool, inputs, result
summary, confirmation/execution status. This file is **not** wiped when
`factory.db` is rebuilt from CSV.

---

## Not implemented

| Tool | Status |
|---|---|
| `assess_stage_performance` | TODO — full stage analytics beyond the briefing/discovery drop heuristic |
| Other watch conditions | V1 is `ORDER_INACTIVE_BY_DATE` only |
| Watch scheduler / SMTP | Evaluate via `GET /api/watches?as_of=`; local alert only |
