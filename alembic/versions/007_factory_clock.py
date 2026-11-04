"""Store the demo factory date separately for each account."""

from alembic import op

revision = "007_factory_clock"
down_revision = "006_chat_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE copilot.factory_clocks (
            user_id BIGINT PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            factory_date DATE NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE copilot.factory_clocks")
