# Database Guide

## 1. Purpose and scope

This PostgreSQL database supports the Factory Copilot prototype. It stores customer orders, daily production output and candidate workshop information so that administrators, ordinary users and the AI Agent can access the data with appropriate permissions.

The repository is a reproducible local prototype. Its CSV files contain learning and acceptance-test data rather than permanent production records.

## 2. Connection information

| Item | Value |
|---|---|
| Database management system | PostgreSQL |
| SQL dialect | PostgreSQL SQL |
| Default host | `localhost` |
| Default port | `5432` |
| Database | `factory_copilot_db` |
| Application schema | `app` |
| Project administrator | `factory_admin` |
| Ordinary login user | `factory_user` |
| AI Agent login user | `factory_agent` |
| Shared read-only role | `factory_reader` (`NOLOGIN`) |

The default port is the repository convention. A local installation may use another configured PostgreSQL port. Each user must enter the password created locally for the selected login role. Passwords must not be stored in this guide or committed to Git.

Example connection command:

```powershell
psql -X -h localhost -p 5432 -U factory_agent -d factory_copilot_db -W
```

## 3. Tables and fields

### 3.1 `app.orders`

One row represents one customer order. The table supports order tracking, due-date monitoring and production-stage reporting. Its primary key is `order_id`.

| Field | Type | Nullable | Description |
|---|---|---|---|
| `order_id` | `text` | No | Unique order identifier |
| `customer` | `text` | No | Customer name |
| `product` | `text` | No | Ordered product |
| `category` | `text` | No | `TOPS` or `ACCESSORIES` |
| `pieces` | `integer` | No | Ordered quantity; must be greater than zero |
| `order_date` | `date` | No | Date the order was placed |
| `due_date` | `date` | No | Promised delivery date; cannot precede `order_date` |
| `status` | `text` | No | `IN_PROGRESS` or `COMPLETE` |
| `current_stage` | `text` | No | `KNITTING`, `ASSEMBLY`, `WASHING`, `PACKING` or `COMPLETE` |
| `last_activity_date` | `date` | No | Most recent production activity date |
| `completed_date` | `date` | Yes | Completion date; null while an order is in progress |
| `days_late` | `integer` | Yes | `completed_date - due_date`; a negative value means early completion |

The table enforces consistency between `status`, `current_stage`, `completed_date` and `days_late`.

### 3.2 `app.production_log`

One row represents the number of pieces completed on one date at one production stage. The composite primary key is (`production_date`, `stage`).

| Field | Type | Nullable | Description |
|---|---|---|---|
| `production_date` | `date` | No | Production date; mapped from the source field `date` |
| `stage` | `text` | No | `KNITTING`, `ASSEMBLY`, `WASHING` or `PACKING` |
| `pieces_completed` | `integer` | No | Completed pieces for the date and stage; zero or greater |

Sunday rows must have zero completed pieces.

### 3.3 `app.workshops`

One row represents one candidate workshop. The table supports comparisons of capacity, lead time, quality, cost and current workload. Its primary key is `workshop_id`, and `name` is also unique.

| Field | Type | Nullable | Description |
|---|---|---|---|
| `workshop_id` | `text` | No | Unique workshop identifier |
| `name` | `text` | No | Unique workshop name |
| `capacity_pieces_per_day` | `integer` | No | Maximum daily capacity |
| `pickup_lead_days` | `integer` | No | Pickup or transport lead time in days |
| `defect_rate` | `numeric(5,4)` | No | Expected defect rate between 0 and 1 |
| `cost_per_piece` | `numeric(10,2)` | No | Processing cost per piece |
| `makes` | `text` | No | `TOPS`, `ACCESSORIES` or `TOPS+ACCESSORIES` |
| `status` | `text` | No | `ACTIVE` or `SUSPENDED` |
| `max_batch_pieces` | `integer` | Yes | Optional maximum batch size |
| `current_queue_days` | `numeric(6,2)` | No | Current waiting time in days |
| `notes` | `text` | No | Operational notes about the workshop |

For source-file names, sample values, nullability and constraints, see [field_mapping.md](field_mapping.md).

## 4. Common queries

All examples below are read-only and may be run by `factory_admin`, `factory_user` or `factory_agent`.

### Check table row counts

```sql
SELECT 'orders' AS table_name, COUNT(*) AS row_count
FROM app.orders
UNION ALL
SELECT 'production_log', COUNT(*) FROM app.production_log
UNION ALL
SELECT 'workshops', COUNT(*) FROM app.workshops
ORDER BY table_name;
```

Expected counts for the current snapshot are 120, 360 and 8 respectively.

### List orders still in progress

```sql
SELECT order_id, customer, product, pieces, due_date, current_stage
FROM app.orders
WHERE status = 'IN_PROGRESS'
ORDER BY due_date, order_id;
```

### List completed orders delivered late

```sql
SELECT order_id, customer, due_date, completed_date, days_late
FROM app.orders
WHERE days_late > 0
ORDER BY days_late DESC, order_id;
```

### Summarise production by stage

```sql
SELECT stage, SUM(pieces_completed) AS total_pieces_completed
FROM app.production_log
GROUP BY stage
ORDER BY stage;
```

### Compare active workshops

```sql
SELECT name, makes, capacity_pieces_per_day,
       defect_rate, cost_per_piece, current_queue_days
FROM app.workshops
WHERE status = 'ACTIVE'
ORDER BY current_queue_days, defect_rate, cost_per_piece;
```

## 5. Roles and permission boundaries

The prototype distinguishes the project administrator from ordinary and Agent access. Ordinary users and the Agent currently have the same effective table permissions, but they remain separate login identities for auditing and future policy changes.

| Role | Login | SELECT | INSERT | UPDATE | DELETE | TRUNCATE | CREATE/DROP in `app` | Purpose |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `factory_admin` | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Owns and maintains the project database |
| `factory_reader` | No | Yes | No | No | No | No | No | Shared read-only permission role |
| `factory_user` | Yes | Yes | No | No | No | No | No | Ordinary user; inherits `factory_reader` |
| `factory_agent` | Yes | Yes | No | No | No | No | No | AI Agent; inherits `factory_reader` |

The design follows least privilege:

- `factory_admin` owns `factory_copilot_db`, the `app` schema and the project tables.
- `factory_reader` stores shared read-only permissions but cannot log in directly.
- `factory_user` and `factory_agent` inherit `factory_reader`.
- public schema creation is revoked.
- public access to the project tables is revoked.
- future tables created by `factory_admin` in `app` automatically grant `SELECT` to `factory_reader` and no table access to `PUBLIC`.

Use `factory_admin` only for database setup and maintenance. Applications and the AI Agent must not connect as the administrator.

## 6. Validation and acceptance procedure

Run the scripts from the repository root in this order:

1. `sql/01_roles_and_database.sql` — initial setup only.
2. `sql/02_schema_tables_permissions.sql` — initial construction only.
3. `sql/03_import.sql` — import or replace the CSV snapshot.
4. `sql/04_validate.sql` — validate counts, totals, uniqueness and ownership.
5. `sql/05_admin_permission_test.sql` — verify administrator permissions with a disposable probe table.
6. `sql/06_readonly_permission_test.sql` — verify Agent reads succeed and dangerous operations fail.

The acceptance outputs generated for the current prototype are indexed in [../evidence/README.md](../evidence/README.md).

## 7. Security and operational notes

- Never commit passwords, access tokens, `.env` files or PostgreSQL data directories.
- Do not expose passwords in screenshots, terminal transcripts or chat messages.
- Do not restore or initialise this prototype over an existing database containing important data.
- Expected permission-denied messages in the read-only test are evidence of correct behaviour.
- Apply structural changes through reviewed SQL scripts rather than undocumented manual edits.
- Create a backup before destructive administrative maintenance.
