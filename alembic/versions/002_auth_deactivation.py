"""Auth account lifecycle: DEACTIVATED self-service + ADMIN user listing.

Revision ID: 002_auth_deactivation
Revises: 001_initial_auth

- Extends auth.users.status to include DEACTIVATED (self-service soft delete).
  DISABLED remains the ADMIN-disables-other-account semantic.
- Adds deactivated_at / deactivated_by for audit attribution.
  No DELETE FROM auth.users is performed; username UNIQUE stays reserved.
"""
from alembic import op

revision = "002_auth_deactivation"
down_revision = "001_initial_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE auth.users DROP CONSTRAINT IF EXISTS users_status_check")
    op.execute(
        "ALTER TABLE auth.users ADD CONSTRAINT users_status_check "
        "CHECK (status IN ('PENDING', 'ACTIVE', 'REJECTED', 'DISABLED', 'DEACTIVATED'))"
    )
    op.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS deactivated_by BIGINT")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_deactivated_by_fkey') THEN "
        "ALTER TABLE auth.users ADD CONSTRAINT users_deactivated_by_fkey "
        "FOREIGN KEY (deactivated_by) REFERENCES auth.users(id); "
        "END IF; END $$"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auth.users DROP CONSTRAINT IF EXISTS users_deactivated_by_fkey")
    op.execute("ALTER TABLE auth.users DROP COLUMN IF EXISTS deactivated_by")
    op.execute("ALTER TABLE auth.users DROP COLUMN IF EXISTS deactivated_at")
    op.execute("ALTER TABLE auth.users DROP CONSTRAINT IF EXISTS users_status_check")
    op.execute(
        "ALTER TABLE auth.users ADD CONSTRAINT users_status_check "
        "CHECK (status IN ('PENDING', 'ACTIVE', 'REJECTED', 'DISABLED'))"
    )
