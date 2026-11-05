"""Integration tests for bounded administrator row updates."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.pg_database import connect


def _workshop_source_and_row() -> tuple[int, dict]:
    with connect(admin=True) as connection:
        source = connection.execute(
            """
            SELECT id
            FROM admin_meta.data_sources
            WHERE table_name = 'workshops' AND is_active = TRUE
            """
        ).fetchone()
        row = connection.execute(
            """
            SELECT * FROM app.workshops
            ORDER BY workshop_id, makes
            LIMIT 1
            """
        ).fetchone()
    assert source is not None
    assert row is not None
    return source["id"], dict(row)


def test_admin_updates_one_row_and_records_before_after(admin_auth_headers):
    datasource_id, before = _workshop_source_and_row()
    note = f"{before['notes']} [bounded-update-test]"
    request_id = None

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/admin/datasources/{datasource_id}/rows",
                headers=admin_auth_headers,
                json={
                    "updates": [
                        {
                            "key": {
                                "workshop_id": before["workshop_id"],
                                "makes": before["makes"],
                            },
                            "changes": {"notes": note},
                        }
                    ]
                },
            )
        assert response.status_code == 200, response.text
        payload = response.json()
        request_id = payload["request_id"]
        assert payload["updated_count"] == 1
        assert payload["rows"][0]["notes"] == note

        with connect(admin=True) as connection:
            audit = connection.execute(
                """
                SELECT actor_user_id, actor_label, row_key, before_json, after_json
                FROM admin_meta.data_change_audit
                WHERE request_id = %s
                """,
                (request_id,),
            ).fetchone()
        assert audit["actor_user_id"] == 1
        assert audit["actor_label"] == "user:1"
        assert audit["row_key"] == {
            "workshop_id": before["workshop_id"],
            "makes": before["makes"],
        }
        assert audit["before_json"]["notes"] == before["notes"]
        assert audit["after_json"]["notes"] == note
    finally:
        with connect(admin=True) as connection, connection.transaction():
            connection.execute(
                """
                UPDATE app.workshops SET notes = %s
                WHERE workshop_id = %s AND makes = %s
                """,
                (before["notes"], before["workshop_id"], before["makes"]),
            )
            if request_id is not None:
                connection.execute(
                    "DELETE FROM admin_meta.data_change_audit WHERE request_id = %s",
                    (request_id,),
                )


def test_batch_rolls_back_when_any_row_is_missing(admin_auth_headers):
    datasource_id, before = _workshop_source_and_row()

    with TestClient(app) as client:
        response = client.patch(
            f"/api/admin/datasources/{datasource_id}/rows",
            headers=admin_auth_headers,
            json={
                "updates": [
                    {
                        "key": {
                            "workshop_id": before["workshop_id"],
                            "makes": before["makes"],
                        },
                        "changes": {"notes": "must be rolled back"},
                    },
                    {
                        "key": {
                            "workshop_id": "MISSING-WORKSHOP",
                            "makes": before["makes"],
                        },
                        "changes": {"notes": "does not exist"},
                    },
                ]
            },
        )
    assert response.status_code == 404

    with connect(admin=True) as connection:
        after = connection.execute(
            """
            SELECT notes FROM app.workshops
            WHERE workshop_id = %s AND makes = %s
            """,
            (before["workshop_id"], before["makes"]),
        ).fetchone()
    assert after["notes"] == before["notes"]


def test_row_update_rejects_employee_and_primary_key_change(
    admin_auth_headers,
    employee_auth_headers,
):
    datasource_id, before = _workshop_source_and_row()
    body = {
        "updates": [
            {
                "key": {
                    "workshop_id": before["workshop_id"],
                    "makes": before["makes"],
                },
                "changes": {"workshop_id": "NOT-ALLOWED"},
            }
        ]
    }

    with TestClient(app) as client:
        employee = client.patch(
            f"/api/admin/datasources/{datasource_id}/rows",
            headers=employee_auth_headers,
            json=body,
        )
        admin = client.patch(
            f"/api/admin/datasources/{datasource_id}/rows",
            headers=admin_auth_headers,
            json=body,
        )

    assert employee.status_code == 403
    assert admin.status_code == 422
    assert "Primary-key columns cannot be changed" in admin.json()["detail"]
