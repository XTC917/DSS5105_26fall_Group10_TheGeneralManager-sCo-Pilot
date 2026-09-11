-- Reset the database to the reproducible baseline dataset.
-- This script clears and reloads the current business tables and initial snapshot.
-- Use the application upload API for normal daily updates.
-- If any step fails, the transaction rolls back all changes.

\set ON_ERROR_STOP on

SELECT
    current_database(),
    current_user;

BEGIN;

TRUNCATE TABLE app.orders, app.production_log, app.workshops, app.snapshot;


\copy app.orders (order_id, customer, product, category, pieces, order_date, due_date, status, current_stage, last_activity_date, completed_date, days_late) FROM 'data/orders.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')
\copy app.production_log (production_date, stage, pieces_completed) FROM 'data/production_log.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')
\copy app.snapshot (order_id, status, stage, date) FROM 'data/altogether_summary.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')

CREATE TEMP TABLE workshops_import
(LIKE app.workshops)
ON COMMIT DROP;
\copy workshops_import (workshop_id, name, capacity_pieces_per_day, pickup_lead_days, defect_rate, cost_per_piece, makes, status, max_batch_pieces, current_queue_days, notes) FROM 'data/workshops.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')
INSERT INTO app.workshops(
    workshop_id,
    name,
    capacity_pieces_per_day,
    pickup_lead_days,
    defect_rate,
    cost_per_piece,
    makes,
    status,
    max_batch_pieces,
    current_queue_days,
    notes
)
SELECT
    workshop.workshop_id,
    workshop.name,
    workshop.capacity_pieces_per_day,
    workshop.pickup_lead_days,
    workshop.defect_rate,
    workshop.cost_per_piece,
    BTRIM(split_makes.makes),
    workshop.status,
    workshop.max_batch_pieces,
    workshop.current_queue_days,
    workshop.notes
FROM workshops_import AS workshop
CROSS JOIN LATERAL
    UNNEST(STRING_TO_ARRAY(workshop.makes, '+')) AS split_makes(makes);

INSERT INTO admin_meta.data_sources (
    source_name,
    table_name,
    original_file,
    description,
    row_count
)
VALUES
    (
        'Orders',
        'orders',
        'data/orders.csv',
        'Current orders data source',
        (SELECT COUNT(*) FROM app.orders)
    ),
    (
        'Production Log',
        'production_log',
        'data/production_log.csv',
        'Current production output by date and stage',
        (SELECT COUNT(*) FROM app.production_log)
    ),
    (
        'Workshops',
        'workshops',
        'data/workshops.csv',
        'Current workshop capacity, cost, quality, and availability data',
        (SELECT COUNT(*) FROM app.workshops)
    )
ON CONFLICT (table_name)
DO UPDATE SET
    source_name = EXCLUDED.source_name,
    original_file = EXCLUDED.original_file,
    description = EXCLUDED.description,
    row_count = EXCLUDED.row_count,
    is_active = true,
    updated_at = CURRENT_TIMESTAMP;


SELECT
    source_name,
    table_name,
    original_file,
    row_count,
    is_active,
    created_at,
    updated_at
FROM admin_meta.data_sources
ORDER BY table_name;

COMMIT;