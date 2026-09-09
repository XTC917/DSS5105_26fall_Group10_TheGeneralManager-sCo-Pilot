# Factory Copilot PostgreSQL Database

## Overview

This directory contains the reproducible local PostgreSQL database for the Factory Copilot project. The SQL files create project roles, schemas, tables, constraints and permissions; import the three supplied datasets; and test data integrity and access control.

The database is currently local rather than cloud-hosted. The experimental `SQL_related_app` backend has been connected to it and tested, but the main LangGraph application has not yet been formally switched to this PostgreSQL source.

## Database design

- Database: `factory_copilot_db`
- Business schema: `app`
- Administration schema: `admin_meta`
- Project administrator: `factory_admin`
- Shared read-only permission role: `factory_reader` (`NOLOGIN`)
- Ordinary read-only login: `factory_user`
- AI Agent read-only login: `factory_agent`

`factory_user` and `factory_agent` inherit the permissions stored by `factory_reader`. Role attributes such as `LOGIN`, `CREATEDB` and `CREATEROLE` are defined separately for each login role.

### Business tables

| Table | Purpose |
|---|---|
| `app.orders` | Current complete orders dataset |
| `app.production_log` | Current complete production dataset |
| `app.workshops` | Current workshop capabilities, one row per workshop-category pair |
| `app.snapshot` | Prior `IN_PROGRESS` order-stage observations captured before `orders` replacement |

`app.snapshot` is append-only in the current design. Its composite primary key prevents the same order, stage and activity date from being stored twice.

The source `workshops.csv` retains its original format. During import, `TOPS+ACCESSORIES` is split into separate `TOPS` and `ACCESSORIES` rows. Therefore the supplied eight source rows become eleven database rows representing eight physical workshops.

### Administration tables

The `admin_meta` schema contains:

- `upload_history`: one record per upload attempt;
- `import_details`: per-table outcome for an upload;
- `data_sources`: the latest registered state and row count of each uploadable table.

Only `factory_admin` can access this schema. The two read-only login roles cannot inspect upload metadata.

## Directory structure

```text
postgresql_database/
|-- data/
|   |-- orders.csv
|   |-- production_log.csv
|   `-- workshops.csv
|-- docs/
|   |-- database_guide.md
|   `-- field_mapping.md
|-- sql/
|   |-- 01_roles_and_database.sql
|   |-- 02_schema_tables_permissions.sql
|   |-- 03_import.sql
|   |-- 04_validate.sql
|   |-- 05_admin_permission_test.sql
|   `-- 06_readonly_permission_test.sql
`-- README.md
```

Validation output files are intentionally not stored in the repository. The SQL scripts are the reproducible tests; run them locally whenever current evidence is needed.

## Prerequisites

- PostgreSQL server and command-line tools, including `psql`;
- a local PostgreSQL system administrator account, normally `postgres`;
- PostgreSQL `bin` on the Windows PATH;
- the three supplied CSV files under `data/`.

Verify the client and server:

```powershell
psql --version
pg_isready -h localhost -p 5432
```

Do not store PostgreSQL passwords in this repository.

## Reproduce the database

Open PowerShell and move to this directory:

```powershell
Set-Location "C:\path\to\DSS5105_26fall_Group10_TheGeneralManager-sCo-Pilot\postgresql_database"
```

Run the commands from `postgresql_database`, because `03_import.sql` uses relative paths such as `data/orders.csv`.

### 1. Create roles and the database

Run once as the PostgreSQL system administrator:

```powershell
psql -X -h localhost -p 5432 -U postgres -d postgres -W -f "sql/01_roles_and_database.sql"
```

The script creates `factory_reader`, `factory_admin`, `factory_user`, `factory_agent`, grants the shared reader role to the two read-only logins, asks for three local login passwords, and creates `factory_copilot_db` owned by `factory_admin`.

This is an initial-setup script. Do not rerun it after the roles and database exist.

### 2. Create schemas, tables and permissions

Run once as the project administrator:

```powershell
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/02_schema_tables_permissions.sql"
```

The script creates the four `app` tables, three `admin_meta` tables, database constraints, identity sequences, current permissions and default permissions for future `app` tables.

Expected output includes `BEGIN`, two `CREATE SCHEMA` messages, seven `CREATE TABLE` messages, permission statements, and `COMMIT`.

This is also an initial-construction script. Do not rerun it against an already constructed database.

### 3. Import current data

Run as `factory_admin`:

```powershell
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/03_import.sql"
```

The import runs as one transaction:

1. copy outgoing `IN_PROGRESS` order states into `app.snapshot`;
2. clear the three current business tables;
3. import 120 orders and 360 production rows;
4. read eight workshop source rows through a temporary table;
5. split combined workshop categories and insert eleven workshop-category rows;
6. update the three `admin_meta.data_sources` records.

If any step fails, PostgreSQL rolls back the current-table replacement and the snapshot additions together.

The number of rows inserted into `snapshot` varies. It is normally zero on a fresh database, may increase after a new orders dataset replaces an existing one, and remains unchanged when all outgoing states are already present.

### 4. Validate data and metadata

```powershell
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/04_validate.sql"
```

For the supplied current data, the key results are:

| Check | Expected result |
|---|---:|
| Orders rows | 120 |
| Unique order IDs | 120 |
| Total order pieces | 93,500 |
| Missing completed dates | 34 |
| Missing days late | 34 |
| Production rows/date-stage pairs | 360 |
| Production pieces completed | 231,595 |
| Workshop-category rows | 11 |
| Distinct physical workshops | 8 |
| Physical daily capacity | 1,600 |
| Active physical workshops | 7 |
| Physical workshops missing maximum batch | 7 |

`snapshot_rows` is not fixed because history grows across order replacements. `snapshot_rows` and `unique_snapshot_states` should match.

The workshop consistency query should return zero rows. All three `data_sources.row_count` values should match their corresponding current business tables.

The script now performs active assertions. A successful run ends with:

```text
VALIDATION PASSED: metadata counts and workshop profiles are consistent
```

A metadata mismatch or inconsistent workshop profile raises an exception and returns a non-zero `psql` exit code.

### 5. Test administrator permissions

```powershell
psql -X -h localhost -p 5432 -U factory_admin -d factory_copilot_db -W -f "sql/05_admin_permission_test.sql"
```

Expected behaviour:

- `factory_admin` can connect and use/create in both schemas;
- it can select, insert, update, delete and truncate all project tables;
- it can use the `admin_meta` identity sequence;
- a disposable table successfully passes create, read, update, delete, truncate and drop tests;
- the entire probe transaction is rolled back, and `probe_table_removed` is `t`.

The test does not persist its probe table or modify the four business tables.

### 6. Test read-only permissions

Run with either inherited read-only login. The Agent example is:

```powershell
psql -X -h localhost -p 5432 -U factory_agent -d factory_copilot_db -W -f "sql/06_readonly_permission_test.sql"
```

Expected behaviour:

- connection and `app` schema usage succeed;
- `admin_meta` schema usage and sequence usage are denied;
- `SELECT` succeeds for all four `app` tables;
- all write/create/drop permissions are false;
- explicit negative tests report that metadata SELECT, INSERT, UPDATE, DELETE, TRUNCATE, CREATE TABLE and DROP TABLE were denied;
- the final table counts remain unchanged.

A correct run includes:

```text
TEST PASSED: admin_meta data SELECT was denied
TEST PASSED: INSERT was denied
TEST PASSED: UPDATE was denied
TEST PASSED: DELETE was denied
TEST PASSED: TRUNCATE was denied
TEST PASSED: CREATE TABLE was denied
TEST PASSED: DROP TABLE was denied
=== All seven permission-denial tests passed ===
```

The final counts should show 120 `orders`, 360 `production_log` rows, eleven `workshops` rows, and the current variable number of `snapshot` rows.

## Safe reruns

- `01_roles_and_database.sql`: initial setup only;
- `02_schema_tables_permissions.sql`: initial construction only;
- `03_import.sql`: may be rerun to replace current data and preserve outgoing in-progress order states;
- `04_validate.sql`: safe to rerun;
- `05_admin_permission_test.sql`: safe to rerun because its changes are rolled back;
- `06_readonly_permission_test.sql`: safe to rerun because denied operations cannot persist.

Do not delete a database, schema, table or role merely to resolve an `already exists` message. First confirm the current database, user and intended environment.

## Connect the administration app

After completing Steps 1–3, configure and run the local FastAPI/React administration app using [`../SQL_related_app/README.md`](../SQL_related_app/README.md).

The active backend uses:

- `factory_agent` for read-only schema and SQL access;
- `factory_admin` for uploads and administration.

The backend can import CSV, XLSX and XLS files. The SQL bootstrap script itself uses `psql` `\copy` and therefore imports the tracked CSV seed files.

## Documentation

- [`docs/field_mapping.md`](docs/field_mapping.md): source-to-database field mapping and data audit;
- [`docs/database_guide.md`](docs/database_guide.md): database concepts, roles, permissions and usage guidance.

These documents should describe the current SQL files. They must not contain passwords or private environment values.

## Troubleshooting

- `psql is not recognized`: add the PostgreSQL `bin` directory to PATH and reopen PowerShell.
- `localhost:5432 - no response`: start the PostgreSQL service and verify it with `pg_isready`.
- `password authentication failed`: confirm the selected login role and its locally configured password.
- `data/orders.csv: No such file or directory`: run `03_import.sql` from `postgresql_database`.
- `role already exists` or `database already exists`: Step 1 has already been run; do not delete objects without checking the environment.
- Red underlines in a graphical SQL editor do not prove the file is invalid; `psql` backslash commands such as `\copy`, `\set` and `\echo` are not ordinary server-side SQL.

## Security and scope

- Never commit `.env` files or passwords.
- Use `factory_admin` only for maintenance and trusted administration endpoints.
- Use `factory_agent` for AI read-only access.
- The current deployment is local and is not a shared production server.
- The route name `/api/admin` does not itself authenticate a human administrator; application authentication remains a team integration decision.
