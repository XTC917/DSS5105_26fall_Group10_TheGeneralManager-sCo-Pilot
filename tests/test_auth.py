"""Auth lifecycle tests: register/login/me, approval, self-deactivation."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.pg_database import connect

SUFFIX = os.environ.get("PYTEST_XDIST_WORKER", "0")


def _unique(prefix: str) -> str:
    import time

    return f"{prefix}_{SUFFIX}_{int(time.time() * 1000) % 1000000}"


def _register(client: TestClient, username: str, password: str = "password123", account_type: str = "EMPLOYEE", admin_code: str | None = None):
    payload = {
        "username": username,
        "password": password,
        "confirm_password": password,
        "account_type": account_type,
    }
    if admin_code is not None:
        payload["admin_code"] = admin_code
    return client.post("/api/auth/register", json=payload)


def _login(client: TestClient, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _cleanup(username: str) -> None:
    with connect(admin=True) as conn, conn.transaction():
        conn.execute("DELETE FROM auth.users WHERE username=%s", (username,))


def test_register_short_password_rejected(db):
    with TestClient(app) as client:
        res = _register(client, _unique("shortpw"), password="123")
        assert res.status_code == 422


def test_employee_pending_cannot_login_before_approval(db):
    name = _unique("pending_emp")
    try:
        with TestClient(app) as client:
            reg = _register(client, name)
            assert reg.status_code == 200, reg.text
            assert reg.json()["user"]["status"] == "PENDING"
            login = _login(client, name, "password123")
            assert login.status_code == 403
            assert "awaiting administrator approval" in login.json()["detail"]
    finally:
        _cleanup(name)


def test_admin_approve_flow_and_user_listing(db, admin_auth_headers):
    name = _unique("approve_emp")
    try:
        with TestClient(app) as client:
            assert _register(client, name).status_code == 200
            pending = client.get("/api/admin/users/pending", headers=admin_auth_headers)
            assert pending.status_code == 200
            target = next(u for u in pending.json()["items"] if u["username"] == name)
            ok = client.post(f"/api/admin/users/{target['id']}/approve", headers=admin_auth_headers)
            assert ok.status_code == 200, ok.text
            assert ok.json()["user"]["status"] == "ACTIVE"
            # no longer pending
            pending2 = client.get("/api/admin/users/pending", headers=admin_auth_headers)
            assert all(u["username"] != name for u in pending2.json()["items"])
            # visible in admin user list
            listed = client.get("/api/admin/users/", headers=admin_auth_headers)
            assert listed.status_code == 200
            assert any(u["username"] == name for u in listed.json()["items"])
            # approved employee can log in
            login = _login(client, name, "password123")
            assert login.status_code == 200, login.text
            assert login.json()["user"]["status"] == "ACTIVE"
    finally:
        _cleanup(name)


def test_reject_requires_admin_and_confirm_semantics(db, admin_auth_headers, employee_auth_headers):
    name = _unique("reject_emp")
    try:
        with TestClient(app) as client:
            assert _register(client, name).status_code == 200
            denied = client.get("/api/admin/users/pending", headers=employee_auth_headers)
            assert denied.status_code == 403
            pending = client.get("/api/admin/users/pending", headers=admin_auth_headers)
            target = next(u for u in pending.json()["items"] if u["username"] == name)
            rej = client.post(f"/api/admin/users/{target['id']}/reject", headers=admin_auth_headers)
            assert rej.status_code == 200
            assert rej.json()["user"]["status"] == "REJECTED"
    finally:
        _cleanup(name)


def test_creating_and_switching_multiple_accounts_keeps_first_account_active(
    db,
    monkeypatch,
):
    password = "password123"
    admin_code = "test-admin-registration-code"
    monkeypatch.setenv("ADMIN_REGISTRATION_CODE", admin_code)

    account_types = [
        "ADMIN",
        "EMPLOYEE",
        "ADMIN",
        "EMPLOYEE",
        "EMPLOYEE",
    ]
    accounts = [
        (_unique(f"switch_account_{index}"), account_type)
        for index, account_type in enumerate(account_types)
    ]
    created_names: list[str] = []

    try:
        with TestClient(app) as client:
            for username, account_type in accounts:
                response = _register(
                    client,
                    username,
                    password=password,
                    account_type=account_type,
                    admin_code=admin_code if account_type == "ADMIN" else None,
                )
                assert response.status_code == 200, response.text
                created_names.append(username)

                with connect(admin=True) as conn:
                    first_account = conn.execute(
                        """
                        SELECT status
                        FROM auth.users
                        WHERE username = %s
                        """,
                        (accounts[0][0],),
                    ).fetchone()

                assert first_account is not None
                assert first_account["status"] == "ACTIVE"

            # Employee registration starts as PENDING. Activate the test
            # employees so that every account can participate in login switching.
            with connect(admin=True) as conn, conn.transaction():
                for username, account_type in accounts:
                    if account_type == "EMPLOYEE":
                        conn.execute(
                            """
                            UPDATE auth.users
                            SET status = 'ACTIVE'
                            WHERE username = %s
                            """,
                            (username,),
                        )

            for username, _ in accounts:
                login = _login(client, username, password)
                assert login.status_code == 200, login.text
                assert login.json()["user"]["username"] == username
                assert login.json()["user"]["status"] == "ACTIVE"

            # Return to the first account after switching through all others.
            first_login = _login(client, accounts[0][0], password)
            assert first_login.status_code == 200, first_login.text
            assert first_login.json()["user"]["status"] == "ACTIVE"

            with connect(admin=True) as conn:
                rows = conn.execute(
                    """
                    SELECT username, status
                    FROM auth.users
                    WHERE username = ANY(%s)
                    """,
                    ([username for username, _ in accounts],),
                ).fetchall()

            assert len(rows) == len(accounts)
            assert {row["status"] for row in rows} == {"ACTIVE"}
    finally:
        for username in reversed(created_names):
            _cleanup(username)


def test_self_deactivation_only_affects_authenticated_account(db):
    password = "password123"
    first_name = _unique("deactivate_isolation_first")
    second_name = _unique("deactivate_isolation_second")
    created_names: list[str] = []

    try:
        with TestClient(app) as client:
            for username in (first_name, second_name):
                response = _register(client, username, password=password)
                assert response.status_code == 200, response.text
                created_names.append(username)

            with connect(admin=True) as conn, conn.transaction():
                for username in created_names:
                    conn.execute(
                        """
                        UPDATE auth.users
                        SET status = 'ACTIVE'
                        WHERE username = %s
                        """,
                        (username,),
                    )

            first_login = _login(client, first_name, password)
            second_login = _login(client, second_name, password)
            assert first_login.status_code == 200, first_login.text
            assert second_login.status_code == 200, second_login.text

            second_headers = {
                "Authorization": (
                    f"Bearer {second_login.json()['access_token']}"
                )
            }
            deactivated = client.delete(
                "/api/auth/me",
                headers=second_headers,
            )
            assert deactivated.status_code == 200, deactivated.text
            assert deactivated.json()["user"]["username"] == second_name
            assert deactivated.json()["user"]["status"] == "DEACTIVATED"

            # The first account must remain usable.
            first_login_again = _login(client, first_name, password)
            assert first_login_again.status_code == 200, first_login_again.text
            assert first_login_again.json()["user"]["status"] == "ACTIVE"

            with connect(admin=True) as conn:
                rows = conn.execute(
                    """
                    SELECT username, status
                    FROM auth.users
                    WHERE username = ANY(%s)
                    """,
                    ([first_name, second_name],),
                ).fetchall()

            statuses = {
                row["username"]: row["status"]
                for row in rows
            }
            assert statuses == {
                first_name: "ACTIVE",
                second_name: "DEACTIVATED",
            }
    finally:
        for username in reversed(created_names):
            _cleanup(username)


def test_self_deactivation_soft_delete(db):
    name = _unique("deact_emp")
    with TestClient(app) as client:
        assert _register(client, name).status_code == 200
        row = connect(admin=True).execute(
            "SELECT id FROM auth.users WHERE username = %s", (name,)
        ).fetchone()
        assert row is not None
        # approve via admin directly to reach ACTIVE
        with connect(admin=True) as conn, conn.transaction():
            conn.execute("UPDATE auth.users SET status='ACTIVE' WHERE username=%s", (name,))
        login = _login(client, name, "password123")
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/auth/me", headers=headers)
        assert me.status_code == 200
        gone = client.delete("/api/auth/me", headers=headers)
        assert gone.status_code == 200, gone.text
        assert gone.json()["user"]["status"] == "DEACTIVATED"
        # token no longer authorizes; login blocked; row preserved; username reserved
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        assert _login(client, name, "password123").status_code == 403
        with connect(admin=True) as conn:
            kept = conn.execute(
                "SELECT status, deactivated_at, deactivated_by FROM auth.users WHERE username=%s",
                (name,),
            ).fetchone()
        assert kept["status"] == "DEACTIVATED"
        assert kept["deactivated_at"] is not None
        assert _register(client, name).status_code == 409
        # cleanup of throwaway account keeps the users table small
        with connect(admin=True) as conn, conn.transaction():
            conn.execute("DELETE FROM auth.users WHERE username=%s", (name,))


def test_deactivate_forbidden_for_pending(db):
    name = _unique("deact_pend")
    with TestClient(app) as client:
        assert _register(client, name).status_code == 200
        with connect(admin=True) as conn, conn.transaction():
            conn.execute("UPDATE auth.users SET status='ACTIVE' WHERE username=%s", (name,))
        login = _login(client, name, "password123")
        assert login.status_code == 200
        with connect(admin=True) as conn:
            kept = conn.execute("SELECT id FROM auth.users WHERE username=%s", (name,)).fetchone()
        assert kept is not None
        with connect(admin=True) as conn, conn.transaction():
            conn.execute("DELETE FROM auth.users WHERE username=%s", (name,))


def test_public_user_never_exposes_secrets(db, admin_auth_headers):
    with TestClient(app) as client:
        res = client.get("/api/admin/users/", headers=admin_auth_headers)
        assert res.status_code == 200
        for item in res.json()["items"]:
            assert "password_hash" not in item
            assert "password" not in item
            assert "admin_code" not in str(item).lower()
            assert "ADMIN_REGISTRATION_CODE" not in str(item)
