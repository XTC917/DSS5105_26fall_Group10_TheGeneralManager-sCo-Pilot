-- Run this file once as factory_admin in factory_copilot_db.

\set ON_ERROR_STOP on

SELECT
    current_database(),
    current_user;

BEGIN;

REVOKE CONNECT, TEMPORARY
ON DATABASE factory_copilot_db
FROM PUBLIC;

GRANT CONNECT, TEMPORARY
ON DATABASE factory_copilot_db
TO factory_admin;

GRANT CONNECT
ON DATABASE factory_copilot_db
TO factory_reader;

REVOKE CREATE
ON SCHEMA public
FROM PUBLIC;

CREATE SCHEMA app
AUTHORIZATION factory_admin;

GRANT USAGE
ON SCHEMA app
TO factory_reader;

REVOKE CREATE
ON SCHEMA app
FROM factory_reader;

CREATE TABLE app.orders (
    order_id text NOT NULL PRIMARY KEY,
    customer text NOT NULL,
    product text NOT NULL,
    category text NOT NULL CHECK (category IN ('TOPS', 'ACCESSORIES')),
    pieces integer NOT NULL CHECK (pieces > 0),
    order_date date NOT NULL,
    due_date date NOT NULL CHECK (due_date >= order_date),
    status text NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
    current_stage text NOT NULL CHECK (current_stage IN ('KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE')),
    last_activity_date date NOT NULL CHECK (last_activity_date >= order_date),
    completed_date date,
    days_late integer,

    CONSTRAINT orders_state_consistency CHECK (
        (status = 'IN_PROGRESS'
        AND current_stage IN ('KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')
        AND completed_date IS NULL
        AND days_late IS NULL)
        OR
        (status = 'COMPLETE'
        AND current_stage = 'COMPLETE'
        AND completed_date IS NOT NULL
        AND completed_date = last_activity_date
        AND days_late IS NOT NULL
        AND days_late = completed_date - due_date)
    )

);

CREATE TABLE app.production_log(
    production_date date NOT NULL,
    stage text NOT NULL CHECK (stage IN ('KNITTING','ASSEMBLY', 'WASHING', 'PACKING')),
    pieces_completed integer NOT NULL CHECK (pieces_completed >= 0),
    PRIMARY KEY (production_date, stage),

    CONSTRAINT pieces_completed_consistency CHECK (
        EXTRACT(ISODOW FROM production_date) != 7 OR pieces_completed = 0
    )
);

CREATE TABLE app.workshops (
    workshop_id text NOT NULL PRIMARY KEY,
    name text NOT NULL UNIQUE,
    capacity_pieces_per_day integer NOT NULL CHECK (capacity_pieces_per_day > 0),
    pickup_lead_days integer NOT NULL CHECK (pickup_lead_days >= 0),
    defect_rate numeric(5,4) NOT NULL CHECK (defect_rate >= 0 AND defect_rate <= 1),
    cost_per_piece numeric(10,2) NOT NULL CHECK (cost_per_piece >= 0),
    makes text NOT NULL CHECK (makes IN ('TOPS', 'ACCESSORIES', 'TOPS+ACCESSORIES')),
    status text NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED')),
    max_batch_pieces integer CHECK (max_batch_pieces IS NULL OR max_batch_pieces > 0),
    current_queue_days numeric(6,2) NOT NULL CHECK (current_queue_days >= 0),
    notes text NOT NULL
);

REVOKE ALL
ON ALL TABLES IN SCHEMA app
FROM PUBLIC;

GRANT SELECT
ON ALL TABLES IN SCHEMA app
TO factory_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA app
GRANT SELECT ON TABLES TO factory_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA app
REVOKE ALL ON TABLES FROM PUBLIC;

COMMIT;
