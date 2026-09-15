"""Canonical Phase 1 baseline: app / admin_meta / copilot / auth.

Revision ID: 001_initial_auth
Revises: None

Matches postgresql_database/sql/02_schema_tables_permissions.sql for the
app + admin_meta tables (including the ORDERED lifecycle state), and adds
the auth + copilot schemas for Phase 1.
"""
from alembic import op

revision = "001_initial_auth"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute("CREATE SCHEMA IF NOT EXISTS admin_meta")
    op.execute("CREATE SCHEMA IF NOT EXISTS copilot")
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    op.execute("""
        CREATE TABLE IF NOT EXISTS auth.users (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('ADMIN', 'EMPLOYEE')),
            status TEXT NOT NULL CHECK (status IN ('PENDING', 'ACTIVE', 'REJECTED', 'DISABLED')),
            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMPTZ,
            approved_by BIGINT REFERENCES auth.users(id),
            last_login_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app.orders (
            order_id text NOT NULL PRIMARY KEY,
            customer text NOT NULL,
            product text NOT NULL,
            category text NOT NULL CHECK (category IN ('TOPS', 'ACCESSORIES')),
            pieces integer NOT NULL CHECK (pieces > 0),
            order_date date NOT NULL,
            due_date date NOT NULL CHECK (due_date >= order_date),
            status text NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
            current_stage text NOT NULL CHECK (current_stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE')),
            last_activity_date date NOT NULL CHECK (last_activity_date >= order_date),
            completed_date date,
            days_late integer,
            CONSTRAINT orders_state_consistency CHECK (
                (status = 'IN_PROGRESS'
                AND current_stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')
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
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app.production_log (
            production_date date NOT NULL,
            stage text NOT NULL CHECK (stage IN ('KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING')),
            pieces_completed integer NOT NULL CHECK (pieces_completed >= 0),
            PRIMARY KEY (production_date, stage),
            CONSTRAINT pieces_completed_consistency CHECK (
                EXTRACT(ISODOW FROM production_date) != 7 OR pieces_completed = 0
            )
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app.workshops (
            workshop_id text NOT NULL,
            name text NOT NULL,
            capacity_pieces_per_day integer NOT NULL CHECK (capacity_pieces_per_day > 0),
            pickup_lead_days integer NOT NULL CHECK (pickup_lead_days >= 0),
            defect_rate numeric(5,4) NOT NULL CHECK (defect_rate >= 0 AND defect_rate <= 1),
            cost_per_piece numeric(10,2) NOT NULL CHECK (cost_per_piece >= 0),
            makes text NOT NULL CHECK (makes IN ('TOPS', 'ACCESSORIES')),
            status text NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED')),
            max_batch_pieces integer CHECK (max_batch_pieces IS NULL OR max_batch_pieces > 0),
            current_queue_days numeric(6,2) NOT NULL CHECK (current_queue_days >= 0),
            notes text NOT NULL,
            PRIMARY KEY (workshop_id, makes),
            UNIQUE (name, makes)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app.snapshot (
            order_id text NOT NULL,
            status text NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETE')),
            stage text NOT NULL CHECK (stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING', 'COMPLETE')),
            date date NOT NULL,
            CONSTRAINT snapshot_state_consistency CHECK (
                (status = 'IN_PROGRESS'
                AND stage IN ('ORDERED', 'KNITTING', 'ASSEMBLY', 'WASHING', 'PACKING'))
                OR (status = 'COMPLETE' AND stage = 'COMPLETE')
            ),
            PRIMARY KEY (order_id, status, stage, date)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_meta.upload_history (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            file_name text NOT NULL,
            file_type text NOT NULL CHECK (file_type IN ('csv', 'excel')),
            total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('success', 'failed', 'pending', 'processing')),
            error_message text,
            uploaded_by text NOT NULL DEFAULT 'admin',
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_meta.import_details (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            upload_id bigint NOT NULL REFERENCES admin_meta.upload_history(id) ON DELETE CASCADE,
            file_name text NOT NULL,
            table_name text NOT NULL CHECK (table_name IN ('orders', 'production_log', 'workshops')),
            total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
            success_rows integer NOT NULL DEFAULT 0 CHECK (success_rows >= 0),
            failed_rows integer NOT NULL DEFAULT 0 CHECK (failed_rows >= 0),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('success', 'failed', 'pending')),
            error_message text,
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at timestamptz,
            CHECK (success_rows + failed_rows = total_rows)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_meta.data_sources (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source_name text NOT NULL,
            table_name text NOT NULL UNIQUE CHECK (table_name IN ('orders', 'production_log', 'workshops')),
            original_file text,
            description text,
            row_count integer NOT NULL DEFAULT 0 CHECK (row_count >= 0),
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.audit_log (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            factory_today DATE NOT NULL,
            conversation_id TEXT,
            user_id BIGINT REFERENCES auth.users(id),
            user_query TEXT,
            event_type TEXT NOT NULL,
            tool TEXT,
            inputs_json JSONB,
            result_ok BOOLEAN,
            result_summary TEXT,
            confirmation_status TEXT,
            execution_status TEXT,
            target TEXT
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.order_notes (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES auth.users(id),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            order_id TEXT NOT NULL,
            note TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.reminders (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES auth.users(id),
            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            order_id TEXT,
            remind_on DATE NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN'
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.watches (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES auth.users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_factory_today DATE NOT NULL,
            order_id TEXT NOT NULL,
            condition_type TEXT NOT NULL,
            params_json JSONB NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL,
            last_evaluated_as_of DATE,
            fired_as_of DATE,
            fired_at TIMESTAMPTZ,
            notify_channel TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.watch_events (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            watch_id BIGINT NOT NULL REFERENCES copilot.watches(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            as_of DATE NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            snapshot_json JSONB NOT NULL,
            delivery_status TEXT NOT NULL
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_copilot_watch_events_one_fired ON copilot.watch_events(watch_id) WHERE event_type = 'fired'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_notes_user_order ON copilot.order_notes(user_id, order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_reminders_user ON copilot.reminders(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_watches_user ON copilot.watches(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_audit_user ON copilot.audit_log(user_id)")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE")
    op.execute("DROP SCHEMA IF EXISTS copilot CASCADE")
    op.execute("DROP SCHEMA IF EXISTS admin_meta CASCADE")
    op.execute("DROP SCHEMA IF EXISTS app CASCADE")
