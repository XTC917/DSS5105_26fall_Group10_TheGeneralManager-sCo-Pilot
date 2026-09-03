from fastapi import APIRouter, HTTPException, Query

from config import assert_allowed_table, quote_table
from db import get_connection, get_table_count, pragma_table_info

router = APIRouter(prefix="/api/admin/datasources", tags=["Data Sources"])


@router.get("/")
async def list_datasources():
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, source_name, table_name, original_file,
                   description, is_active, row_count,
                   created_at, updated_at
            FROM data_sources
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/{datasource_id}")
async def get_datasource(datasource_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM data_sources WHERE id = ?",
            (datasource_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Data source not found")
        return dict(row)
    finally:
        conn.close()


@router.delete("/{datasource_id}")
async def delete_datasource(
    datasource_id: int,
    drop_table: bool = Query(False),
):
    """Remove the catalog row. The three business tables are never dropped.

    drop_table=true clears rows in the allowlisted table instead of DROP TABLE.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT table_name FROM data_sources WHERE id = ?",
            (datasource_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Data source not found")
        table_name = row["table_name"]
        try:
            assert_allowed_table(table_name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        if drop_table:
            conn.execute(f"DELETE FROM {quote_table(table_name)}")
            conn.execute(
                """
                UPDATE data_sources
                SET row_count = 0, is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (datasource_id,),
            )
        else:
            conn.execute(
                """
                UPDATE data_sources
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (datasource_id,),
            )
        conn.commit()
        return {
            "success": True,
            "message": "Data source cleared" if drop_table else "Data source deactivated",
            "row_count": get_table_count(table_name) if drop_table else None,
        }
    finally:
        conn.close()


@router.get("/{datasource_id}/data")
async def get_datasource_data(
    datasource_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT table_name FROM data_sources WHERE id = ?",
            (datasource_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Data source not found")
        table_name = row["table_name"]
        try:
            assert_allowed_table(table_name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        quoted = quote_table(table_name)
        data = conn.execute(
            f"SELECT * FROM {quoted} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute(f"SELECT COUNT(*) AS total FROM {quoted}").fetchone()[
            "total"
        ]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "columns": pragma_table_info(table_name),
            "data": [dict(item) for item in data],
        }
    finally:
        conn.close()
