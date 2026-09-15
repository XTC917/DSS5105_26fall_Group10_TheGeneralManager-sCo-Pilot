"""Authentication and administrator user-management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.auth import CurrentUser, authenticate, deactivate_self, get_current_user, public_user, register_user, require_admin
from backend.services.pg_database import connect
from backend.pg_config import AUTH_SCHEMA

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/api/admin/users", tags=["User Management"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    confirm_password: str
    account_type: str
    email: str | None = None
    admin_code: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(request: RegisterRequest):
    user = register_user(
        username=request.username,
        password=request.password,
        confirm_password=request.confirm_password,
        account_type=request.account_type,
        admin_code=request.admin_code,
    )
    if request.email:
        with connect(admin=True) as conn, conn.transaction():
            conn.execute(f"UPDATE {AUTH_SCHEMA}.users SET email = %s WHERE id = %s", (request.email, user["id"]))
            user["email"] = request.email
    return {"user": user, "message": "Your account is awaiting administrator approval." if user["status"] == "PENDING" else "Account created."}


@router.post("/login")
def login(request: LoginRequest):
    user, token = authenticate(request.username, request.password)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"user": user.__dict__}


@router.delete("/me")
def deactivate_me(user: CurrentUser = Depends(get_current_user)):
    """Self-service deactivation (soft delete: ACTIVE -> DEACTIVATED)."""
    return {"user": deactivate_self(user), "message": "Your account has been deactivated."}


@users_router.get("/")
def list_users(_: CurrentUser = Depends(require_admin)):
    """ADMIN-only user list for the User Management page (no secrets)."""
    with connect(admin=True) as conn:
        rows = conn.execute(
            f"SELECT * FROM {AUTH_SCHEMA}.users ORDER BY created_at"
        ).fetchall()
    return {"items": [public_user(dict(row)) for row in rows]}


@users_router.get("/pending")
def pending_users(_: CurrentUser = Depends(require_admin)):
    with connect(admin=True) as conn:
        rows = conn.execute(f"SELECT * FROM {AUTH_SCHEMA}.users WHERE status = 'PENDING' ORDER BY created_at").fetchall()
    return {"items": [public_user(dict(row)) for row in rows]}


def _set_status(user_id: int, new_status: str, admin: CurrentUser) -> dict:
    if user_id == admin.id:
        raise HTTPException(400, "An administrator cannot change their own status here")
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(f"SELECT * FROM {AUTH_SCHEMA}.users WHERE id = %s", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "User not found")
        if new_status == "ACTIVE":
            conn.execute(f"UPDATE {AUTH_SCHEMA}.users SET status=%s, approved_at=CURRENT_TIMESTAMP, approved_by=%s WHERE id=%s", (new_status, admin.id, user_id))
        else:
            conn.execute(f"UPDATE {AUTH_SCHEMA}.users SET status=%s WHERE id=%s", (new_status, user_id))
        updated = conn.execute(f"SELECT * FROM {AUTH_SCHEMA}.users WHERE id = %s", (user_id,)).fetchone()
    return public_user(dict(updated))


@users_router.post("/{user_id}/approve")
def approve(user_id: int, admin: CurrentUser = Depends(require_admin)):
    return {"user": _set_status(user_id, "ACTIVE", admin)}


@users_router.post("/{user_id}/reject")
def reject(user_id: int, admin: CurrentUser = Depends(require_admin)):
    return {"user": _set_status(user_id, "REJECTED", admin)}


@users_router.post("/{user_id}/disable")
def disable(user_id: int, admin: CurrentUser = Depends(require_admin)):
    return {"user": _set_status(user_id, "DISABLED", admin)}
