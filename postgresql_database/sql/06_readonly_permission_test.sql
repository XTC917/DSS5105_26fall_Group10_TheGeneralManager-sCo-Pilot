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
    ) AS can_use_schema,

    has_schema_privilege(
        current_user,
        'app',
        'CREATE'
    ) AS can_create_in_schema;

SELECT
    tablename,

    has_table_privilege(
        current_user,
        schemaname || '.' || tablename,
        'SELECT'
    ) AS can_select,

    has_table_privilege(
        current_user,
        schemaname || '.' || tablename,
        'INSERT'
    ) AS can_insert,

    has_table_privilege(
        current_user,
        schemaname || '.' || tablename,
        'UPDATE'
    ) AS can_update,

    has_table_privilege(
        current_user,
        schemaname || '.' || tablename,
        'DELETE'
    ) AS can_delete,

    has_table_privilege(
        current_user,
        schemaname || '.' || tablename,
        'TRUNCATE'
    ) AS can_truncate
FROM pg_tables
WHERE schemaname = 'app'
ORDER BY tablename;

SELECT COUNT(*) AS readable_order_rows
FROM app.orders;


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


\echo === All six permission-denial tests passed ===


\echo === Final integrity check ===

SELECT 'orders' AS table_name, COUNT(*) AS row_count
FROM app.orders

UNION ALL

SELECT 'production_log', COUNT(*)
FROM app.production_log

UNION ALL

SELECT 'workshops', COUNT(*)
FROM app.workshops

ORDER BY table_name;
