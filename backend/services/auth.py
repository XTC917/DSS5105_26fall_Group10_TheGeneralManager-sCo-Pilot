"""Authentication services: Argon2id password hashing and signed bearer tokens."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation

from backend.pg_config import AUTH_SCHEMA
from backend.services.pg_database import connect

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)
_TOKEN_TTL_HOURS = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    email: str | None
    role: str
    status: str


def _jwt_secret() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters")
    return secret


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in (
        "id", "username", "email", "role", "status", "email_verified",
        "created_at", "approved_at", "approved_by", "last_login_at",
        "deactivated_at", "deactivated_by",
    )}


def register_user(*, username: str, password: str, confirm_password: str,
                  account_type: str, admin_code: str | None = None) -> dict[str, Any]:
    username = username.strip()
    if len(username) < 3:
        raise HTTPException(422, "Username must contain at least 3 characters")
    if password != confirm_password:
        raise HTTPException(422, "Password confirmation does not match")
    if len(password) < 8:
        raise HTTPException(422, "Password must contain at least 8 characters")
    requested = account_type.strip().upper()
    if requested not in {"ADMIN", "EMPLOYEE"}:
        raise HTTPException(422, "Account type must be ADMIN or EMPLOYEE")
    if requested == "ADMIN":
        expected = os.getenv("ADMIN_REGISTRATION_CODE", "")
        if not expected or not admin_code or admin_code != expected:
            raise HTTPException(403, "Invalid administrator security code")
        account_status = "ACTIVE"
    else:
        account_status = "PENDING"
    password_hash = _hasher.hash(password)
    try:
        with connect(admin=True) as conn, conn.transaction():
            row = conn.execute(
                f"""INSERT INTO {AUTH_SCHEMA}.users
                    (username, password_hash, role, status)
                    VALUES (%s, %s, %s, %s) RETURNING *""",
                (username, password_hash, requested, account_status),
            ).fetchone()
    except UniqueViolation as exc:
        raise HTTPException(409, "Username already exists") from exc
    return public_user(dict(row))


def authenticate(username: str, password: str) -> tuple[dict[str, Any], str]:
    with connect(admin=True) as conn:
        row = conn.execute(
            f"SELECT * FROM {AUTH_SCHEMA}.users WHERE username = %s", (username.strip(),)
        ).fetchone()
    if not row:
        raise HTTPException(401, "Invalid username or password")
    try:
        _hasher.verify(row["password_hash"], password)
    except VerifyMismatchError as exc:
        raise HTTPException(401, "Invalid username or password") from exc
    if row["status"] != "ACTIVE":
        messages = {
            "PENDING": "Your account is awaiting administrator approval.",
            "REJECTED": "Your registration was rejected.",
            "DISABLED": "Your account is disabled.",
            "DEACTIVATED": "This account has been deactivated.",
        }
        raise HTTPException(403, messages.get(row["status"], "Account is not active"))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(row["id"]), "role": row["role"], "iat": now,
        "exp": now + timedelta(hours=_TOKEN_TTL_HOURS),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm="HS256")
    with connect(admin=True) as conn, conn.transaction():
        conn.execute(f"UPDATE {AUTH_SCHEMA}.users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (row["id"],))
    return public_user(dict(row)), token


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, _jwt_secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired credentials") from exc
    with connect(admin=True) as conn:
        row = conn.execute(
            f"SELECT id, username, email, role, status FROM {AUTH_SCHEMA}.users WHERE id = %s",
            (user_id,),
        ).fetchone()
    if not row or row["status"] != "ACTIVE":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not active")
    return CurrentUser(**dict(row))


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def deactivate_self(user: CurrentUser) -> dict[str, Any]:
    """Voluntary self-service soft delete: ACTIVE -> DEACTIVATED.

    Preserves the row (username stays reserved, history stays attributable).
    Target is always derived from current_user; no user_id is accepted.
    """
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(
            f"SELECT id, status FROM {AUTH_SCHEMA}.users WHERE id = %s", (user.id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not active")
        if row["status"] != "ACTIVE":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is not active")
        conn.execute(
            f"UPDATE {AUTH_SCHEMA}.users SET status = 'DEACTIVATED', "
            f"deactivated_at = CURRENT_TIMESTAMP, deactivated_by = %s WHERE id = %s",
            (user.id, user.id),
        )
        updated = conn.execute(
            f"SELECT * FROM {AUTH_SCHEMA}.users WHERE id = %s", (user.id,)
        ).fetchone()
    return public_user(dict(updated))
