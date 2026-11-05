"""Add indexed keyword search for persisted conversation history.

Revision ID: 007_conversation_search_indexes
Revises: 006_chat_attempts
"""

from alembic import op


revision = "007_conversation_search_indexes"
down_revision = "006_chat_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX idx_copilot_conversations_title_trgm
        ON copilot.conversations USING GIN (title gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_copilot_chat_turns_question_trgm
        ON copilot.chat_turns USING GIN (question gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_copilot_chat_turns_answer_trgm
        ON copilot.chat_turns USING GIN (answer gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS copilot.idx_copilot_chat_turns_answer_trgm")
    op.execute("DROP INDEX IF EXISTS copilot.idx_copilot_chat_turns_question_trgm")
    op.execute("DROP INDEX IF EXISTS copilot.idx_copilot_conversations_title_trgm")
