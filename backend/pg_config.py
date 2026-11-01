"""Central PostgreSQL configuration for the integrated main backend."""
from __future__ import annotations

import os

from dotenv import load_dotenv

from backend.config import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env", override=True)


def postgres_dsn(*, admin: bool = False) -> str:
    if admin:
        admin_url = os.getenv("PG_ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL_UNPOOLED")
        if admin_url:
            return admin_url
    elif os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    elif os.getenv("DATABASE_URL_UNPOOLED"):
        return os.environ["DATABASE_URL_UNPOOLED"]

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
