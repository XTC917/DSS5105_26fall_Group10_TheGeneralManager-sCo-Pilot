# SweaterCo GM Co-Pilot (DSS5105 Track 1)

AI co-pilot for the general manager of a small knitwear factory. The core is a **tool-using LangGraph agent**, not a generic chatbot.

This repository is the **first MVP**: data layer, four tools, a chat API, and a minimal React UI.

Factory date in the dataset: **2026-04-01**. Do not use the computer clock for business logic.

## What works now

- Load `orders.csv`, `production_log.csv`, `workshops.csv` into SQLite
- `get_order_status` — look up one order; ask for an id if several match
- `get_orders_at_risk` — overdue / stalled / tight-deadline (formulas in Python)
- `trace_order` — source row + calculations
- `check_feasibility` — inspectable capacity estimate for a new order
- `POST /api/chat` — LangGraph agent that must call those tools
- Minimal manager UI with answer + “Why?” traces

## What is not built yet

Morning briefing, discovery engine, emails / notes / reminders, audit log, `assess_stage_performance`, and the full home-screen layout. Placeholder files exist so we can add them later without reshaping the project.

## Repository layout

```
backend/          FastAPI + LangGraph + tools + services
frontend/         React + Vite + Tailwind
data/             Track 1 CSVs (source of truth)
docs/             architecture.md, tool_spec.md
evaluation/       starter questions
tests/            pytest — no LLM key required
```

Read `docs/architecture.md` and `docs/tool_spec.md` before changing rules.

## Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenAI-compatible API key **only if you want the chat agent**
  (pytest and data loading work without a key)

## Backend

From the project root (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set OPENAI_API_KEY (and optionally OPENAI_BASE_URL, LLM_MODEL)

uvicorn backend.main:app --reload --port 8000
```

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to port 8000.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

These tests check schemas, date arithmetic, risk flags, and tool JSON. They do not call an LLM.

## Try these questions (after the API key is set)

- How is ORD-120 doing?
- How is the TrendCart order doing?  ← should ask which order
- Which orders are at risk?
- Why is ORD-120 considered risky?
- Can we take 800 hoodies by August 25?
- What is the revenue from TrendCart?  ← should refuse (no price data)

## Rules for teammates

1. Do not invent columns or business facts that are not in `data/` + `data/data_dictionary.md`.
2. Do not put totals, day counts, or capacity math in the prompt — add a Python function.
3. If a design is not supported by the files, leave a `# TODO` instead of guessing.
4. Side-effecting actions (later) must never run without an explicit confirmation.

## Logging

API logs go to the console and `logs/app.log`.
