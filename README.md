# SweaterCo GM Co-Pilot (DSS5105 Track 1)

## Introduction

<!-- Write the project introduction here. -->



---

## Start here (new users)

This repo is an **AI co-pilot for a knitwear factory general manager**.  
It is **not** a generic chatbot: the model calls **inspectable Python business tools**, and those tools own the numbers.

**Factory date in the dataset: `2026-04-01`.**  
Business logic uses that date, not your laptop clock.

### One-minute mental model

```text
Manager question (UI)
        │
        ▼
FastAPI  /api/chat
        │
        ▼
LangGraph agent  ──selects tool──►  Python tools (orders, risk, feasibility, …)
        │                                      │
        ▼                                      ▼
Natural-language answer  ◄──────── tool JSON + Why traces
```

| Layer | Responsibility |
| --- | --- |
| **Python tools / services** | Status, risk flags, medians, feasibility, briefing, watches |
| **LLM** | Pick an in-scope tool and explain the tool result |
| **UI** | Chat, Overview, Confirm/Dismiss for side effects, Why panel |

If the data cannot support a question (e.g. revenue / selling price), the system should **refuse** instead of guessing.

---

## What you get in this repo

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI app, LangGraph agent, tools, services |
| `frontend/` | React + Vite manager UI |
| `data/` | Source CSVs, `semantic_layer.yaml`, as-of snapshots |
| `docs/` | Architecture, tool behaviour, deploy, email |
| `evaluation/` | Question bank, annotation packs, scoring SOP, 3-condition runner |
| `tests/` | pytest (no LLM key required) |
| `postgresql_database/` | Postgres schema / seed / validation notes |
| `SQL_related_app/` | Standalone data-admin experiment |
| `deploy/` | Cloud env example |
| `Dockerfile`, `render.yaml` | Backend deploy (Render) |
| `frontend/vercel.json` | Frontend deploy (Vercel) |

Deployed shape: **frontend on Vercel**, **API on Render (Docker)**, **email via Resend** (optional; off by default).

---

## Requirements

Install these before the first local run:

| Requirement | Version / notes |
| --- | --- |
| **Python** | **3.10+** (3.11 / 3.13 work; use a venv) |
| **Node.js** | **18+** (for the Vite frontend) |
| **PostgreSQL** | **16+** local server, with `psql` on your `PATH` |
| **OpenAI-compatible API key** | **Optional** — needed only for the chat agent. `pytest`, health, Overview, and tool JSON work without a key. |

**PostgreSQL on Windows:** add the server `bin` folder to `PATH`, for example  
`C:\Program Files\PostgreSQL\18\bin`  
(replace `18` with your installed major version). Confirm with:

```powershell
psql --version
pg_isready -h localhost -p 5432
```

Factory operational tables (`app.orders`, `production_log`, `workshops`, …),
auth, chat history, and LangGraph checkpoints all live in **PostgreSQL**.

---

## Setup instructions

Do these **once** on a new machine (PowerShell examples). Later days: jump to [How to run it locally](#how-to-run-it-locally).

### Checklist (first time)

1. Start PostgreSQL and confirm it accepts connections  
2. Create roles + database + import seed CSVs (`postgresql_database/sql/01`–`04`)  
3. Create Python venv, install `requirements.txt`, copy `.env.example` → `.env`  
4. Fill `.env` (DB passwords, `AUTH_SECRET_KEY`, optional `OPENAI_API_KEY`)  
5. Run Alembic migrations (`auth` / `copilot` schemas)  
6. Start backend, then frontend  
7. (Optional) run `pytest`

### 0. Start PostgreSQL

```powershell
Get-Service -Name "postgresql*"
# If Stopped (Administrator PowerShell):
# Start-Service -Name "postgresql-x64-18"   # use the name from Get-Service

pg_isready -h localhost -p 5432
# expect: localhost:5432 - accepting connections
```

### 1. Create the database (first time only)

From `postgresql_database/` (paths in `03_import.sql` are relative to that folder):

```powershell
cd postgresql_database

# Once, as the Postgres superuser (prompts for the postgres password, then
# asks you to set passwords for factory_admin / factory_user / factory_agent):
psql -X -h localhost -p 5432 -U postgres -d postgres -W -f "sql/01_roles_and_database.sql"

# Once, as factory_admin:
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/02_schema_tables_permissions.sql"

# Baseline import / reset of business tables:
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/03_import.sql"

# Optional check (expect VALIDATION PASSED):
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/04_validate.sql"

cd ..
```

Do **not** re-run `01` / `02` on an existing database. Re-running `03` wipes
post-baseline order-state history and restores the tracked seed.

Details: `postgresql_database/README.md`.

### 2. Python env and `.env`

From the **repo root**:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` so it matches the passwords you set in step 1. The example defaults are:

| Variable | Example | Role |
| --- | --- | --- |
| `PGHOST` / `PGPORT` / `PGDATABASE` | `localhost` / `5432` / `factory_copilot_db` | connection |
| `PGSCHEMA` | `app` | factory tables |
| `PG_COPILOT_SCHEMA` / `PG_AUTH_SCHEMA` / `PG_ADMIN_META_SCHEMA` | `copilot` / `auth` / `admin_meta` | app schemas |
| `PGUSER` / `PGPASSWORD` | `factory_agent` / *(your password)* | runtime app login |
| `PG_ADMIN_USER` / `PG_ADMIN_PASSWORD` | `factory_admin` / *(your password)* | Alembic + admin ops |
| `AUTH_SECRET_KEY` | ≥ 32 random characters | required for login |
| `ADMIN_REGISTRATION_CODE` | any shared code you choose | admin signup |
| `OPENAI_API_KEY` | your key | chat agent only |
| `LLM_MODEL` | `gpt-5.6` (default in example) | optional override |

Leave `EMAIL_DELIVERY_ENABLED=false` unless you have configured Resend
(`docs/email_delivery.md`).

**Linux / macOS** (same steps, different activate / copy):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. App migrations (auth / chat / checkpoints)

Still in the activated venv, from the **repo root**:

```powershell
alembic -c alembic.ini upgrade head
```

This creates/updates `auth` and `copilot` tables on top of the SQL baseline.
FastAPI startup does **not** run migrations for you.

You are done with one-time setup when Alembic finishes without errors.

---

## How to run it locally

Use **two terminals**. Activate the venv in the backend terminal each time.

### 1. Backend (API)

```powershell
# repo root
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000
```

**Health check:** open http://127.0.0.1:8000/api/health  

Expect JSON with `"ok": true`, `"factory_today": "2026-04-01"`, and a `tools` list.  
`"llm_configured": false` is normal until you set `OPENAI_API_KEY`. Without a key, chat returns **503**; other endpoints still work.

### 2. Frontend (UI)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173  
Vite proxies `/api` to port `8000` (so the UI talks to the local API automatically).

Register / sign in from the UI. Admin signup needs the same `ADMIN_REGISTRATION_CODE` as in `.env`.

### 3. Tests (no LLM key)

From the repo root, with the venv active and Postgres running:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

These tests cover schemas, dates, risk flags, routing, and tool JSON. They do **not** call an LLM.

### Day-2 shortcut (DB already created)

```powershell
# Terminal A — API
Get-Service -Name "postgresql*"   # start if needed
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000

# Terminal B — UI
cd frontend
npm run dev
```

Only re-run `alembic upgrade head` after pulling new migration files.  
Only re-run `postgresql_database/sql/03_import.sql` if you intentionally want to reset business tables to the seed.

### Quick troubleshooting

| Symptom | What to check |
| --- | --- |
| `psql` / `pg_isready` not found | Add PostgreSQL `bin` to `PATH`, open a new terminal |
| Alembic / app cannot connect | `.env` passwords match step 1; Postgres is running; DB name is `factory_copilot_db` |
| Login fails | `AUTH_SECRET_KEY` ≥ 32 characters; migrations applied |
| Chat returns 503 | Set `OPENAI_API_KEY` in `.env` and restart uvicorn |
| UI loads but API fails | Backend on port `8000`; frontend proxy expects that port |

---

## How the product works (short)

### Data

- Runtime factory facts: PostgreSQL schema `app` (seeded from the CSVs under
  `data/` / `postgresql_database/data/` via the SQL baseline)
- Field meanings for the agent: `data/semantic_layer.yaml`
- `production_log` is factory-wide (`date × stage`), **not** per order

### Tools (course kinds)

| Kind | Examples |
| --- | --- |
| Retrieval | `get_order_status`, `get_orders_at_risk`, `find_orders` |
| Judgement | `check_feasibility` |
| Tracing | `trace_order` |
| Discovery | `discover_factory_issues`, `get_today_priority`, `get_morning_briefing` |
| Action | notes, reminders, watches, email draft / simulated send |

Side-effecting actions **propose first**; they persist only after **Confirm** in the UI.  
Default email path is local / simulated unless Resend delivery is explicitly enabled — see `docs/email_delivery.md`.

### Try these after the API key works

- How is ORD-120 doing?
- Which orders are at risk?
- Can we take 800 hoodies by August 25?
- Give me this morning's briefing
- Draft a chase-up email for ORD-120
- What is the revenue from TrendCart? ← should refuse

---

## Evaluation (dev harness)

- `evaluation/questions.json` — few-shot bank + development question set
- `evaluation/run_conditions.py` — three conditions: baseline / exclude_exact / full
- `evaluation/人工评分SOP.md` — how humans grade summary answers
- Annotation packs: `evaluation/annotation_sets.json`

This is a **development** harness, not a held-out official score.

Env switches used by the harness (unset = live product behaviour):

- `EVAL_SEMANTIC_LAYER`
- `EVAL_RESPONSE_TEMPLATES`
- `EVAL_FEW_SHOT` (`full` | `exclude_exact` | `off`)
- `EVAL_CAPTURE_TOOL_ARGS=1` — attach tool args for scoring

---

## Where to read next

1. `docs/architecture.md` — request path and system shape  
2. `docs/tool_spec.md` — tool behaviour and limits  
3. `Factory_Primer.md` — factory domain background  
4. `docs/phase4a_deployment_plan.md` / `docs/email_delivery.md` — deploy & mail  
5. `postgresql_database/README.md` — local Postgres setup

---

## Rules for contributors

1. Do not invent columns or business facts that are not in `data/` + `semantic_layer.yaml`.
2. Do not put totals / day counts / capacity math in the prompt — put them in Python.
3. If the files do not support a design, leave a `# TODO` instead of guessing.
4. Side-effecting actions need explicit confirmation; never claim an external email was sent unless delivery is really enabled.
