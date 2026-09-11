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
    COUNT(*) AS current_order_states_missing_from_snapshot
FROM app.orders AS orders
WHERE NOT EXISTS (
    SELECT 1
    FROM app.snapshot AS snapshot
    WHERE snapshot.order_id = orders.order_id
      AND snapshot.status = orders.status
      AND snapshot.stage = orders.current_stage
      AND snapshot.date = orders.last_activity_date
);

SELECT
    COUNT(*) AS snapshot_rows,
    COUNT(DISTINCT (order_id, status, stage, date)) AS unique_snapshot_states,
    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') AS in_progress_states,
    COUNT(*) FILTER (WHERE status = 'COMPLETE') AS complete_states
FROM app.snapshot;

SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT (production_date, stage)) AS date_stage_pairs,
    SUM(pieces_completed) AS pieces_completed
FROM app.production_log;

WITH physical_workshops AS (
    SELECT
        workshop_id,
        MAX(capacity_pieces_per_day) AS capacity_pieces_per_day,
        BOOL_OR(status = 'ACTIVE') AS is_active,
        MAX(max_batch_pieces) AS max_batch_pieces
    FROM app.workshops
    GROUP BY workshop_id
)
SELECT
    (SELECT COUNT(*) FROM app.workshops) AS row_count,
    COUNT(*) AS distinct_workshop_ids,
    SUM(capacity_pieces_per_day) AS total_daily_capacity,
    COUNT(*) FILTER (WHERE is_active) AS active_workshops,
    COUNT(*) FILTER (WHERE max_batch_pieces IS NULL) AS missing_max_batch
FROM physical_workshops;

WITH workshop_consistency AS (
    SELECT
        workshop_id,
        COUNT(*) AS category_rows,
        COUNT(
            DISTINCT (
                name,
                capacity_pieces_per_day,
                pickup_lead_days,
                defect_rate,
                cost_per_piece,
                status,
                max_batch_pieces,
                current_queue_days,
                notes
            )
        ) AS shared_profile_versions
    FROM app.workshops
    GROUP BY workshop_id
)
SELECT workshop_id, category_rows, shared_profile_versions
FROM workshop_consistency
WHERE shared_profile_versions > 1
ORDER BY workshop_id;

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

DO $$
DECLARE
    metadata_mismatches integer;
    inconsistent_workshops integer;
    current_states_missing integer;
BEGIN
   WITH actual_counts AS (
        SELECT 'orders' AS table_name, COUNT(*) AS actual_row_count
        FROM app.orders

        UNION ALL

        SELECT 'production_log', COUNT(*)
        FROM app.production_log

        UNION ALL

        SELECT 'workshops', COUNT(*)
        FROM app.workshops
    )
    SELECT COUNT(*)
    INTO metadata_mismatches
    FROM actual_counts
    LEFT JOIN admin_meta.data_sources
        USING (table_name)
    WHERE data_sources.table_name IS NULL
       OR data_sources.row_count
            IS DISTINCT FROM actual_counts.actual_row_count;

    IF metadata_mismatches > 0 THEN
        RAISE EXCEPTION
            'Validation failed: % data source row counts do not match',
            metadata_mismatches;
    END IF;

    SELECT COUNT(*)
    INTO inconsistent_workshops
    FROM (
        SELECT workshop_id
        FROM app.workshops
        GROUP BY workshop_id
        HAVING COUNT(
            DISTINCT (
                name,
                capacity_pieces_per_day,
                pickup_lead_days,
                defect_rate,
                cost_per_piece,
                status,
                max_batch_pieces,
                current_queue_days,
                notes
            )
        ) > 1
    ) AS inconsistent;

    IF inconsistent_workshops > 0 THEN
        RAISE EXCEPTION
            'Validation failed: % workshops have inconsistent shared attributes',
            inconsistent_workshops;
    END IF;

    SELECT COUNT(*)
    INTO current_states_missing
    FROM app.orders AS orders
    WHERE NOT EXISTS (
        SELECT 1
        FROM app.snapshot AS snapshot
        WHERE snapshot.order_id = orders.order_id
          AND snapshot.status = orders.status
          AND snapshot.stage = orders.current_stage
          AND snapshot.date = orders.last_activity_date
    );

    IF current_states_missing > 0 THEN
        RAISE EXCEPTION
            'Validation failed: % current order states are missing from snapshot',
            current_states_missing;
    END IF;
    RAISE NOTICE
        'VALIDATION PASSED: metadata counts, workshop profiles, and snapshot states are consistent';
END
$$;