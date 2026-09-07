-- Replace the current database snapshot with the three CSV files.
-- If any import fails, the previous complete snapshot is preserved.

\set ON_ERROR_STOP on

SELECT
    current_database(),
    current_user;

BEGIN;

TRUNCATE TABLE
    app.orders,
    app.production_log,
    app.workshops;


\copy app.orders (order_id, customer, product, category, pieces, order_date, due_date, status, current_stage, last_activity_date, completed_date, days_late) FROM 'data/orders.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')
\copy app.production_log (production_date, stage, pieces_completed) FROM 'data/production_log.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')
\copy app.workshops (workshop_id, name, capacity_pieces_per_day, pickup_lead_days, defect_rate, cost_per_piece, makes, status, max_batch_pieces, current_queue_days, notes) FROM 'data/workshops.csv' WITH (FORMAT CSV, HEADER true, NULL '', ENCODING 'UTF8')


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