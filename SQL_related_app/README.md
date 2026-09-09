# Factory Data Administration App (`SQL_related_app`)

This folder contains a local React/FastAPI administration app for the Factory Copilot PostgreSQL database. It accepts the three agreed business datasets, validates and imports them, exposes read-only SQL endpoints, and records upload metadata.

The PostgreSQL path is currently an experimental local integration. It has been tested independently, but the main LangGraph application has not yet been formally switched to this API. Authentication and ownership of that final integration must be agreed with the main application authors.

## Current data model

The PostgreSQL database is `factory_copilot_db`.

The `app` schema contains:

- `orders`: current complete orders dataset;
- `production_log`: current complete production dataset;
- `workshops`: current workshop capabilities, with one row per workshop and category;
- `snapshot`: historical `IN_PROGRESS` order-stage observations captured before `orders` is replaced.

The `admin_meta` schema contains internal upload history, import details, and data-source metadata. It is not readable by `factory_user` or `factory_agent`.

Only `orders`, `production_log`, and `workshops` are accepted by the upload API. `snapshot` is queryable but cannot be uploaded directly.

## Import behaviour

- Accepted files: `.csv`, `.xlsx`, and `.xls`.
- Each file must use the expected columns for its selected table.
- Files are previewed before import; preview does not write to PostgreSQL.
- Each table can be uploaded independently.
- `replace` is the normal mode: the selected current table is replaced in one transaction.
- If validation or insertion fails, the previous business data remains unchanged and the failure is recorded in `admin_meta`.
- When `orders` is replaced, the outgoing `IN_PROGRESS` rows are copied to `app.snapshot` before replacement. Duplicate order-stage-date observations are ignored.
- A source `workshops` row whose `makes` value is `TOPS+ACCESSORIES` is expanded during import into two database rows: one for `TOPS` and one for `ACCESSORIES`. The source CSV/XLS/XLSX file itself is not rewritten.

For the provided data, eight source workshop rows become eleven workshop-category rows representing eight physical workshops. Count physical workshops with `COUNT(DISTINCT workshop_id)`; do not sum duplicated workshop-level capacity once per category.

## Database identities

The backend uses two PostgreSQL connections:

- `factory_agent`: read-only connection for schema discovery and SQL queries;
- `factory_admin`: administrator connection for uploads, metadata, replacement, and data-source administration.

`factory_user` is another read-only login role created by the database setup, but this administration backend does not currently open a separate connection with that role.

The `/api/admin` prefix is a route name, not application authentication. Until the main application supplies an agreed authentication layer, access to this local API must be treated as trusted local access.

## Prerequisites

- PostgreSQL running locally on port `5432` unless configured otherwise;
- the database created using `../postgresql_database/sql/01_roles_and_database.sql` through `03_import.sql`;
- Python 3.11 and `uv` for the backend environment;
- Node.js and npm for the frontend.

## Configure and run the backend

From the repository root:

```powershell
Set-Location "SQL_related_app\backend"
uv venv --python 3.11 --prompt "sql-related-app-pg" .venv
uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt
Copy-Item ".env.example" ".env"
```

Edit `backend/.env` and provide locally configured credentials:

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=factory_copilot_db
PGUSER=factory_agent
PGPASSWORD=your_local_agent_password
PGSCHEMA=app
PGCONNECTTIMEOUT=5
PG_ADMIN_USER=factory_admin
PG_ADMIN_PASSWORD=your_local_admin_password
```

Never commit `.env` or real passwords.

Activate and run the backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Useful local endpoints:

- health: <http://127.0.0.1:8001/health>
- interactive API documentation: <http://127.0.0.1:8001/docs>

## Run the frontend

Open a second terminal from the repository root:

```powershell
Set-Location "SQL_related_app\frontend"
npm install
npm run dev
```

Open <http://localhost:3000>. Vite proxies `/api` requests to the standalone
backend on port `8001`, leaving port `8000` available for the main application.

## API summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Test the PostgreSQL read-only connection |
| `GET` | `/api/query/schema` | Return live schema, sample rows, counts, and business rules |
| `POST` | `/api/query/execute` | Execute one read-only `SELECT`; return at most 100 visible rows |
| `GET` | `/api/admin/datasources/` | List current uploadable data sources |
| `GET` | `/api/admin/datasources/{id}` | Read one data-source record |
| `GET` | `/api/admin/datasources/{id}/data?limit=&offset=` | Read a page of current business data |
| `DELETE` | `/api/admin/datasources/{id}` | Mark a data source inactive |
| `DELETE` | `/api/admin/datasources/{id}?drop_table=true` | Clear its rows and mark it inactive; retain the table and catalog record |
| `POST` | `/api/admin/upload/preview` | Preview an uploaded file without importing it |
| `POST` | `/api/admin/upload/import` | Validate and import a selected table in the background |
| `GET` | `/api/admin/upload/status/{upload_id}` | Read import status and details |

Despite the `drop_table` parameter name, the implementation does not drop the PostgreSQL table. It optionally deletes its rows while retaining the schema.

## Read-only SQL rules

The query endpoint:

- accepts one statement beginning with `SELECT`;
- rejects multiple statements;
- starts a read-only transaction;
- applies a five-second statement timeout;
- uses the `app` schema as the search path;
- fetches up to 101 rows internally and exposes at most the first 100.

The PostgreSQL role remains the final protection: `factory_agent` can read `app` but cannot insert, update, delete, truncate, create, or drop project objects.

## Directory map

```text
SQL_related_app/
|-- backend/
|   |-- config.py          Environment settings, upload schemas, and table allowlists
|   |-- db.py              PostgreSQL connections plus inactive legacy SQLite helpers
|   |-- file_importer.py   File reading, validation, transformation, and transactional import
|   |-- schema_service.py  Live PostgreSQL schema context and read-only SQL execution
|   |-- main.py            FastAPI application and health endpoint
|   |-- routers/           Upload, data-source, and query endpoints
|   |-- .env.example       Safe configuration template
|   `-- requirements.txt   Backend dependencies
|-- frontend/
|   |-- src/               React components and API client
|   `-- vite.config.js     Port 3000 and backend proxy configuration
`-- README.md
```

`backend/init_db.py` and several SQLite helpers in `backend/db.py` are retained legacy code. They are not used by the active FastAPI PostgreSQL path. Do not run `init_db.py` for the PostgreSQL setup, and do not remove legacy code without agreement from its original author.

## Verified behaviour and remaining integration work

Locally verified behaviour includes PostgreSQL health checks, schema discovery, read-only queries, data-source endpoints, CSV/XLSX/XLS import, workshop-category expansion, snapshot capture, import status, database constraint failures, and transactional rollback.

Still requiring team-level agreement or final testing:

- connect the main LangGraph application to this API or directly to PostgreSQL;
- decide where admin/user/agent application authentication is enforced;
- perform the final browser-based end-to-end upload and AI-query acceptance test;
- reconcile frontend wording for source rows versus transformed database rows;
- remove legacy SQLite code only if its owner approves.
