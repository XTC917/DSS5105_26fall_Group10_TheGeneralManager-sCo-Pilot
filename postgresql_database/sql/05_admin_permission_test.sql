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


\echo === Administrator CRUD test ===

BEGIN;

CREATE TABLE app.admin_permission_probe (
    probe_id integer PRIMARY KEY,
    note text NOT NULL
);

INSERT INTO app.admin_permission_probe (
    probe_id,
    note
)
VALUES (
    1,
    'original value'
);

SELECT *
FROM app.admin_permission_probe;

UPDATE app.admin_permission_probe
SET note = 'updated value'
WHERE probe_id = 1;

SELECT *
FROM app.admin_permission_probe;

DELETE FROM app.admin_permission_probe
WHERE probe_id = 1;

SELECT COUNT(*) AS rows_after_delete
FROM app.admin_permission_probe;

INSERT INTO app.admin_permission_probe (
    probe_id,
    note
)
VALUES (
    2,
    'row for truncate test'
);

TRUNCATE TABLE app.admin_permission_probe;

SELECT COUNT(*) AS rows_after_truncate
FROM app.admin_permission_probe;

DROP TABLE app.admin_permission_probe;

ROLLBACK;


SELECT
    to_regclass('app.admin_permission_probe') IS NULL
        AS probe_table_removed;