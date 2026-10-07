"""Persist per-user Manager conversation history.

Revision ID: 004_conversation_history
Revises: 002_auth_deactivation
"""

from alembic import op


revision = "004_conversation_history"
down_revision = "002_auth_deactivation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE copilot.conversations (
            id UUID PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES auth.users(id),
            title TEXT NOT NULL DEFAULT 'New conversation',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_copilot_conversations_user_updated
        ON copilot.conversations (user_id, updated_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE TABLE copilot.chat_turns (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            conversation_id UUID NOT NULL
                REFERENCES copilot.conversations(id)
                ON DELETE CASCADE,
            turn_number INTEGER NOT NULL CHECK (turn_number > 0),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chat_turns_conversation_turn_unique
                UNIQUE (conversation_id, turn_number)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_copilot_chat_turns_conversation_id
        ON copilot.chat_turns (conversation_id, id DESC)
        """
    )
    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
            REVOKE ALL ON copilot.conversations, copilot.chat_turns FROM PUBLIC;
            REVOKE ALL ON SEQUENCE copilot.chat_turns_id_seq FROM PUBLIC;
            FOREACH role_name IN ARRAY ARRAY['factory_reader', 'factory_user', 'factory_agent']
            LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                    EXECUTE format(
                        'REVOKE ALL ON copilot.conversations, copilot.chat_turns FROM %I',
                        role_name
                    );
                    EXECUTE format(
                        'REVOKE ALL ON SEQUENCE copilot.chat_turns_id_seq FROM %I',
                        role_name
                    );
                END IF;
            END LOOP;
        END $$
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON copilot.conversations, copilot.chat_turns
        TO factory_admin
        """
    )
    op.execute(
        """
        GRANT USAGE, SELECT
        ON SEQUENCE copilot.chat_turns_id_seq
        TO factory_admin
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS copilot.chat_turns")
    op.execute("DROP TABLE IF EXISTS copilot.conversations")
