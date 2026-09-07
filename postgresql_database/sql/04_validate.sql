\set ON_ERROR_STOP on

SELECT
    current_database(),
    current_user;


SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT order_id) AS unique_order_count,
    SUM(pieces) AS total_pieces,
    COUNT(*) FILTER (WHERE completed_date IS NULL) AS missing_completed_dates,
    COUNT(*) FILTER (WHERE days_late IS NULL) AS missing_days_late
FROM app.orders;

SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT (production_date, stage)) AS date_stage_pairs,
    SUM(pieces_completed) AS pieces_completed
FROM app.production_log;

SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT workshop_id) AS distinct_workshop_ids,
    SUM(capacity_pieces_per_day) AS total_daily_capacity,
    COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_workshops,
    COUNT(*) FILTER (WHERE max_batch_pieces IS NULL) AS missing_max_batch
FROM app.workshops;

SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE schemaname IN ('app', 'admin_meta')
ORDER BY schemaname, tablename;

WITH actual_counts AS (
    SELECT
        'orders' AS table_name,
        COUNT(*) AS actual_row_count
    FROM app.orders

    UNION ALL

    SELECT
        'production_log',
        COUNT(*)
    FROM app.production_log

    UNION ALL

    SELECT
        'workshops',
        COUNT(*)
    FROM app.workshops
)
SELECT
    data_sources.table_name,
    data_sources.row_count AS recorded_row_count,
    actual_counts.actual_row_count,
    data_sources.row_count = actual_counts.actual_row_count
        AS row_count_matches
FROM admin_meta.data_sources
JOIN actual_counts
    USING (table_name)
ORDER BY data_sources.table_name;