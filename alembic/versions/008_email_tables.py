"""Add durable email drafts and idempotent send-attempt records.

Revision ID: 008_email_tables
Revises: 007_conversation_search_indexes
"""

from alembic import op


revision = "008_email_tables"
down_revision = "007_conversation_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE copilot.email_drafts (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL
                REFERENCES auth.users(id)
                ON DELETE RESTRICT,
            conversation_id UUID
                REFERENCES copilot.conversations(id)
                ON DELETE SET NULL,
            order_id TEXT NOT NULL CHECK (btrim(order_id) <> ''),
            recipient_email TEXT
                CHECK (
                    recipient_email IS NULL
                    OR btrim(recipient_email) <> ''
                ),
            recipient_name TEXT,
            from_address TEXT
                CHECK (
                    from_address IS NULL
                    OR btrim(from_address) <> ''
                ),
            subject TEXT NOT NULL CHECK (btrim(subject) <> ''),
            body TEXT NOT NULL CHECK (btrim(body) <> ''),
            language TEXT NOT NULL CHECK (language IN ('zh', 'en')),
            audience TEXT NOT NULL DEFAULT 'unspecified'
                CHECK (audience IN ('unspecified', 'internal', 'customer')),
            template_id TEXT,
            version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
            content_hash TEXT
                CHECK (
                    content_hash IS NULL
                    OR content_hash ~ '^[0-9a-f]{64}$'
                ),
            status TEXT NOT NULL DEFAULT 'DRAFT'
                CHECK (
                    status IN (
                        'DRAFT',
                        'SENDING',
                        'SUBMITTED',
                        'UNKNOWN',
                        'FAILED',
                        'CANCELLED'
                    )
                ),
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE TABLE copilot.email_send_attempts (
            id UUID PRIMARY KEY,
            draft_id UUID NOT NULL
                REFERENCES copilot.email_drafts(id)
                ON DELETE RESTRICT,
            draft_version INTEGER NOT NULL CHECK (draft_version > 0),
            confirmed_by BIGINT NOT NULL
                REFERENCES auth.users(id)
                ON DELETE RESTRICT,
            confirmed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT NOT NULL
                CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            payload_snapshot JSONB NOT NULL
                CHECK (
                    jsonb_typeof(payload_snapshot) = 'object'
                    AND payload_snapshot ?& ARRAY[
                        'from', 'to', 'subject', 'text'
                    ]
                ),
            provider TEXT NOT NULL DEFAULT 'resend'
                CHECK (provider = 'resend'),
            idempotency_key TEXT NOT NULL UNIQUE
                CHECK (char_length(idempotency_key) BETWEEN 1 AND 256),
            provider_email_id TEXT,
            status TEXT NOT NULL DEFAULT 'SENDING'
                CHECK (status IN ('SENDING', 'SUBMITTED', 'UNKNOWN', 'FAILED')),
            request_count INTEGER NOT NULL DEFAULT 0
                CHECK (request_count >= 0),
            last_http_status INTEGER
                CHECK (last_http_status BETWEEN 100 AND 599),
            error_code TEXT,
            error_message TEXT,
            first_requested_at TIMESTAMPTZ,
            last_requested_at TIMESTAMPTZ,
            submitted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT email_send_one_per_version
                UNIQUE (draft_id, draft_version),
            CONSTRAINT email_send_submitted_record CHECK (
                status <> 'SUBMITTED'
                OR (
                    provider_email_id IS NOT NULL
                    AND btrim(provider_email_id) <> ''
                    AND submitted_at IS NOT NULL
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_email_drafts_user_created
        ON copilot.email_drafts (user_id, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_email_drafts_conversation
        ON copilot.email_drafts (conversation_id)
        WHERE conversation_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_email_send_pending
        ON copilot.email_send_attempts (status, updated_at)
        WHERE status IN ('SENDING', 'UNKNOWN')
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_email_send_provider_id
        ON copilot.email_send_attempts (provider, provider_email_id)
        WHERE provider_email_id IS NOT NULL
        """
    )
    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
            REVOKE ALL
                ON copilot.email_drafts, copilot.email_send_attempts
                FROM PUBLIC;
            FOREACH role_name IN ARRAY ARRAY[
                'factory_reader', 'factory_user', 'factory_agent'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL ON copilot.email_drafts, '
                        'copilot.email_send_attempts FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'factory_admin') THEN
                GRANT USAGE ON SCHEMA copilot TO factory_admin;
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON copilot.email_drafts, copilot.email_send_attempts
                    TO factory_admin;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS copilot.email_send_attempts")
    op.execute("DROP TABLE IF EXISTS copilot.email_drafts")
