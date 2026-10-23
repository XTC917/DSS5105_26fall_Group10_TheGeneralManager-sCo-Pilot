"""Record successful and failed authenticated chat attempts.

Revision ID: 006_chat_attempts
Revises: 005_checkpoint_memory
"""

from alembic import op


revision = "006_chat_attempts"
down_revision = "005_checkpoint_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE copilot.chat_attempts (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            conversation_id UUID NOT NULL
                REFERENCES copilot.conversations(id)
                ON DELETE CASCADE,
            question TEXT NOT NULL CHECK (btrim(question) <> ''),
            clarification_reply BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL DEFAULT 'IN_PROGRESS'
                CHECK (status IN ('IN_PROGRESS', 'SUCCEEDED', 'FAILED')),
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ,
            duration_ms BIGINT CHECK (duration_ms IS NULL OR duration_ms >= 0),
            turn_id BIGINT REFERENCES copilot.chat_turns(id) ON DELETE SET NULL,
            error_code TEXT,
            error_message TEXT,
            CONSTRAINT chat_attempts_state_consistency CHECK (
                (
                    status = 'IN_PROGRESS'
                    AND completed_at IS NULL
                    AND duration_ms IS NULL
                    AND turn_id IS NULL
                    AND error_code IS NULL
                    AND error_message IS NULL
                )
                OR
                (
                    status = 'SUCCEEDED'
                    AND completed_at IS NOT NULL
                    AND duration_ms IS NOT NULL
                    AND turn_id IS NOT NULL
                    AND error_code IS NULL
                    AND error_message IS NULL
                )
                OR
                (
                    status = 'FAILED'
                    AND completed_at IS NOT NULL
                    AND duration_ms IS NOT NULL
                    AND turn_id IS NULL
                    AND error_code IS NOT NULL
                    AND error_message IS NOT NULL
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_copilot_chat_attempts_conversation_started
        ON copilot.chat_attempts (conversation_id, started_at DESC, id DESC)
        """
    )
    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
            REVOKE ALL ON copilot.chat_attempts FROM PUBLIC;
            REVOKE ALL ON SEQUENCE copilot.chat_attempts_id_seq FROM PUBLIC;
            FOREACH role_name IN ARRAY ARRAY[
                'factory_reader', 'factory_user', 'factory_agent'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL ON copilot.chat_attempts FROM %I', role_name
                    );
                    EXECUTE format(
                        'REVOKE ALL ON SEQUENCE copilot.chat_attempts_id_seq FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'factory_admin') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON copilot.chat_attempts TO factory_admin;
                GRANT USAGE, SELECT
                    ON SEQUENCE copilot.chat_attempts_id_seq TO factory_admin;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS copilot.chat_attempts")
