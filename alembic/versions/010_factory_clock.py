"""Store the one factory date chosen by an administrator."""

from alembic import op

revision = "010_factory_clock"
down_revision = "009_admin_data_change_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS copilot.factory_clocks (
            id SMALLINT PRIMARY KEY DEFAULT 1,
            factory_date DATE NOT NULL,
            CONSTRAINT factory_clocks_singleton CHECK (id = 1)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS copilot.factory_clocks")
