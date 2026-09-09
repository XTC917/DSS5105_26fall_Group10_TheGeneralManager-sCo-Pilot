\set ON_ERROR_STOP on

SELECT
    current_database(),
    current_user;


SELECT
    has_database_privilege(
        current_user,
        'factory_copilot_db',
        'CONNECT'
    ) AS can_connect,

    has_schema_privilege(
        current_user,
        'app',
        'USAGE'
    ) AS can_use_app_schema,

    has_schema_privilege(
        current_user,
        'admin_meta',
        'USAGE'
    ) AS can_use_admin_meta_schema,

    has_schema_privilege(
        current_user,
        'app',
        'CREATE'
    ) AS can_create_in_app_schema,

    has_schema_privilege(
        current_user,
        'admin_meta',
        'CREATE'
    ) AS can_create_in_admin_meta_schema;

SELECT
    n.nspname AS schemaname,
    c.relname AS tablename,

    has_table_privilege(
        current_user,
        c.oid,
        'SELECT'
    ) AS can_select,

    has_table_privilege(
        current_user,
        c.oid,
        'INSERT'
    ) AS can_insert,

    has_table_privilege(
        current_user,
        c.oid,
        'UPDATE'
    ) AS can_update,

    has_table_privilege(
        current_user,
        c.oid,
        'DELETE'
    ) AS can_delete,

    has_table_privilege(
        current_user,
        c.oid,
        'TRUNCATE'
    ) AS can_truncate
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname IN ('app', 'admin_meta')
    AND c.relkind in ('r', 'p')
ORDER BY n.nspname, c.relname;

SELECT COUNT(*) AS readable_order_rows
FROM app.orders;

SELECT
    has_sequence_privilege(
        current_user,
        c.oid,
        'USAGE'
    ) AS can_use_upload_history_sequence
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'admin_meta'
    AND c.relname = 'upload_history_id_seq'
    AND c.relkind = 'S';

\echo === Negative test: admin_meta data SELECT must fail ===

DO $permission_test$
BEGIN
    BEGIN
        PERFORM 1
        FROM admin_meta.upload_history
        LIMIT 1;

        RAISE EXCEPTION
            'TEST FAILED: admin_meta data SELECT unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: admin_meta data SELECT was denied';
    END;
END
$permission_test$;

\echo === Negative test: INSERT must fail ===

DO $permission_test$
BEGIN
    BEGIN
        INSERT INTO app.production_log (
            production_date,
            stage,
            pieces_completed
        )
        VALUES (
            DATE '2999-01-01',
            'KNITTING',
            0
        );

        RAISE EXCEPTION
            'TEST FAILED: INSERT unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: INSERT was denied';
    END;
END
$permission_test$;


\echo === Negative test: UPDATE must fail ===

DO $permission_test$
BEGIN
    BEGIN
        UPDATE app.orders
        SET pieces = pieces
        WHERE order_id = 'ORD-001';

        RAISE EXCEPTION
            'TEST FAILED: UPDATE unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: UPDATE was denied';
    END;
END
$permission_test$;


\echo === Negative test: DELETE must fail ===

DO $permission_test$
BEGIN
    BEGIN
        DELETE FROM app.orders
        WHERE order_id = 'ORD-001';

        RAISE EXCEPTION
            'TEST FAILED: DELETE unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: DELETE was denied';
    END;
END
$permission_test$;


\echo === Negative test: TRUNCATE must fail ===

DO $permission_test$
BEGIN
    BEGIN
        TRUNCATE TABLE app.production_log;

        RAISE EXCEPTION
            'TEST FAILED: TRUNCATE unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: TRUNCATE was denied';
    END;
END
$permission_test$;


\echo === Negative test: CREATE TABLE must fail ===

DO $permission_test$
BEGIN
    BEGIN
        CREATE TABLE app.agent_should_not_create (
            id integer
        );

        RAISE EXCEPTION
            'TEST FAILED: CREATE TABLE unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: CREATE TABLE was denied';
    END;
END
$permission_test$;


\echo === Negative test: DROP TABLE must fail ===

DO $permission_test$
BEGIN
    BEGIN
        DROP TABLE app.orders;

        RAISE EXCEPTION
            'TEST FAILED: DROP TABLE unexpectedly succeeded';

    EXCEPTION
        WHEN insufficient_privilege THEN
            RAISE NOTICE
                'TEST PASSED: DROP TABLE was denied';
    END;
END
$permission_test$;


\echo === All seven permission-denial tests passed ===


\echo === Final integrity check ===

SELECT 'orders' AS table_name, COUNT(*) AS row_count
FROM app.orders

UNION ALL

SELECT 'production_log', COUNT(*)
FROM app.production_log

UNION ALL

SELECT 'snapshot', COUNT(*)
FROM app.snapshot

UNION ALL

SELECT 'workshops', COUNT(*)
FROM app.workshops

ORDER BY table_name;
