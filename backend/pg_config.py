"""Central PostgreSQL configuration for the integrated main backend."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def postgres_dsn(*, admin: bool = False) -> str:
    if os.getenv("DATABASE_URL") and not admin:
        return os.environ["DATABASE_URL"]
    user = os.getenv("PG_ADMIN_USER" if admin else "PGUSER", "factory_admin" if admin else "factory_agent")
    password = os.getenv("PG_ADMIN_PASSWORD" if admin else "PGPASSWORD", "")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE", "factory_copilot_db")
    auth = f"{user}:{password}@" if password else f"{user}@"
    return f"postgresql://{auth}{host}:{port}/{database}"


PG_SCHEMA = os.getenv("PGSCHEMA", "app")
ADMIN_META_SCHEMA = os.getenv("PG_ADMIN_META_SCHEMA", "admin_meta")
COPILOT_SCHEMA = os.getenv("PG_COPILOT_SCHEMA", "copilot")
AUTH_SCHEMA = os.getenv("PG_AUTH_SCHEMA", "auth")
PG_CONNECT_TIMEOUT = int(os.getenv("PGCONNECT_TIMEOUT", "5"))
PG_STATEMENT_TIMEOUT_MS = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "30000"))
PG_READ_STATEMENT_TIMEOUT_MS = int(os.getenv("PG_READ_STATEMENT_TIMEOUT_MS", "5000"))
