# Factory data admin (`SQL_related_app`)

SQLite-backed CSV/Excel admin for the three Track 1 tables: `orders`, `production_log`, `workshops`.

Windows cannot create a second folder named `SQL_related` next to the existing `SQL_Related` (same path, case-insensitive). This directory is the fixed rewrite.

## Run

Backend (from this folder):

```powershell
cd SQL_related_app\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python init_db.py --force
.\.venv\Scripts\python main.py
```

API: http://127.0.0.1:8000/docs  
Health: http://127.0.0.1:8000/health

Frontend:

```powershell
cd SQL_related_app\frontend
npm install
npm run dev
```

UI: http://localhost:3000 (proxies `/api` to the backend).

## Behaviour

- Only the three allowlisted tables can be imported, previewed, or queried.
- Identifiers are quoted with SQLite `"double quotes"`, never interpolated from raw Form input.
- Re-import replaces the table, then `INSERT OR REPLACE` so primary-key / unique rows are upserted on append.
- Data-source preview uses `PRAGMA table_info` field `name`.
- `DELETE` deactivates the catalog row; it does not `DROP TABLE`.
- Ad-hoc SQL is SELECT-only and limited by the SQLite authorizer to those three tables.

Track 1's agent still reads `data/*.csv` / `backend/services/database.py`. Point that stack at this SQLite file later if you want a single database.
