"""Audit bounded administrator edits to business data.

Revision ID: 009_admin_data_change_audit
Revises: 008_email_tables
"""

from alembic import op


revision = "009_admin_data_change_audit"
down_revision = "008_email_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE admin_meta.data_change_audit (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            request_id UUID NOT NULL,
            actor_user_id BIGINT
                REFERENCES auth.users(id)
                ON DELETE RESTRICT,
            actor_label TEXT NOT NULL CHECK (btrim(actor_label) <> ''),
            datasource_id BIGINT
                REFERENCES admin_meta.data_sources(id)
                ON DELETE SET NULL,
            table_name TEXT NOT NULL
                CHECK (table_name IN ('orders', 'production_log', 'workshops')),
            row_key JSONB NOT NULL
                CHECK (jsonb_typeof(row_key) = 'object'),
            before_json JSONB NOT NULL
                CHECK (jsonb_typeof(before_json) = 'object'),
            after_json JSONB NOT NULL
                CHECK (jsonb_typeof(after_json) = 'object'),
            changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (actor_user_id IS NOT NULL OR actor_label = 'sql-related-app-local-admin')
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_data_change_audit_actor_time
        ON admin_meta.data_change_audit (actor_user_id, changed_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_data_change_audit_table_time
        ON admin_meta.data_change_audit (table_name, changed_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_data_change_audit_request
        ON admin_meta.data_change_audit (request_id, id)
        """
    )
    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
            REVOKE ALL ON admin_meta.data_change_audit FROM PUBLIC;
            REVOKE ALL ON SEQUENCE admin_meta.data_change_audit_id_seq
                FROM PUBLIC;
            FOREACH role_name IN ARRAY ARRAY[
                'factory_reader', 'factory_user', 'factory_agent'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL ON admin_meta.data_change_audit FROM %I',
                        role_name
                    );
                    EXECUTE format(
                        'REVOKE ALL ON SEQUENCE '
                        'admin_meta.data_change_audit_id_seq FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'factory_admin') THEN
                GRANT USAGE ON SCHEMA admin_meta TO factory_admin;
                GRANT SELECT, INSERT
                    ON admin_meta.data_change_audit TO factory_admin;
                GRANT USAGE, SELECT
                    ON SEQUENCE admin_meta.data_change_audit_id_seq
                    TO factory_admin;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_meta.data_change_audit")
