"""Install the reviewed LangGraph 3.1.2 checkpoint schema via Alembic.

Revision ID: 005_checkpoint_memory
Revises: 004_conversation_history

Reuses LangGraph's schema and version ledger. Ordinary indexes are sufficient
inside this transaction; application startup must never run setup()/DDL.
"""

from alembic import op
from langgraph.checkpoint.postgres import PostgresSaver
import re

revision = "005_checkpoint_memory"
down_revision = "004_conversation_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for version, migration in enumerate(PostgresSaver.MIGRATIONS):
        statement = migration.replace("CREATE INDEX CONCURRENTLY", "CREATE INDEX")
        statement = re.sub(r"\b(checkpoints|checkpoint_blobs|checkpoint_writes|checkpoint_migrations)\b",
                           r"copilot.\1", statement)
        op.execute(statement)
        op.execute(f"INSERT INTO copilot.checkpoint_migrations (v) VALUES ({version}) ON CONFLICT DO NOTHING")
    op.execute("""
        DO $$
        DECLARE role_name text;
        DECLARE table_name text;
        BEGIN
            FOREACH table_name IN ARRAY ARRAY[
                'checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations'
            ] LOOP
                EXECUTE format('REVOKE ALL ON TABLE copilot.%I FROM PUBLIC', table_name);
                FOREACH role_name IN ARRAY ARRAY['factory_reader', 'factory_user', 'factory_agent'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                        EXECUTE format('REVOKE ALL ON TABLE copilot.%I FROM %I', table_name, role_name);
                    END IF;
                END LOOP;
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE copilot.%I TO factory_admin', table_name);
            END LOOP;
        END $$
    """)


def downgrade() -> None:
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"):
        op.execute(f"DROP TABLE IF EXISTS copilot.{table}")
