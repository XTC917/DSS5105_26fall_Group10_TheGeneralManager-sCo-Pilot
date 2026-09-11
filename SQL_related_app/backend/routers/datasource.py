from fastapi import APIRouter, HTTPException, Query

from config import Config, assert_upload_table
from db import get_postgres_admin_connection
from psycopg import sql

router = APIRouter(prefix="/api/admin/datasources", tags=["Data Sources"])


@router.get("/")
async def list_datasources():
    conn = get_postgres_admin_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, source_name, table_name, original_file,
                   description, is_active, row_count,
                   created_at, updated_at
            FROM admin_meta.data_sources
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/{datasource_id}")
async def get_datasource(datasource_id: int):
    conn = get_postgres_admin_connection()
    try:
        row = conn.execute(
            "SELECT * FROM admin_meta.data_sources WHERE id = %s",
            (datasource_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Data source not found")
        return dict(row)
    finally:
        conn.close()


@router.delete("/{datasource_id}")
async def delete_datasource(
    datasource_id: int,
    drop_table: bool = Query(False),
):
    """Deactivate a data source and optionally clear its business-table rows.

    The catalog row and physical PostgreSQL table are always retained.
    """
    conn = get_postgres_admin_connection()
    try:
        row_count = None
        with conn.transaction():
            row = conn.execute(
                "SELECT table_name FROM admin_meta.data_sources WHERE id = %s",
                (datasource_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Data source not found")
            table_name = row["table_name"]
            try:
                table_name = assert_upload_table(table_name)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

            if drop_table:
                qualified_table = sql.Identifier(Config.PG_SCHEMA, table_name)
                conn.execute(
                    sql.SQL("DELETE FROM {}").format(qualified_table)
                )
                conn.execute(
                    """
                    UPDATE admin_meta.data_sources
                    SET row_count = 0, is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (datasource_id,),
                )
                row_count = 0
            else:
                conn.execute(
                    """
                    UPDATE admin_meta.data_sources
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (datasource_id,),
                )
            return {
                "success": True,
                "message": "Data source cleared" if drop_table else "Data source deactivated",
                "row_count": row_count,
        }
    finally:
        conn.close()


@router.get("/{datasource_id}/data")
async def get_datasource_data(
    datasource_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_postgres_admin_connection()
    try:
        row = conn.execute(
            "SELECT table_name FROM admin_meta.data_sources WHERE id = %s",
            (datasource_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Data source not found")
        table_name = row["table_name"]
        try:
            assert_upload_table(table_name)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        qualified_table = sql.Identifier(Config.PG_SCHEMA, table_name)
        data_query = sql.SQL(
            "SELECT * FROM {} LIMIT %s OFFSET %s"
        ).format(qualified_table)
        cursor = conn.execute(data_query, (limit, offset))
        data = cursor.fetchall()
        columns = [{"name": column.name} for column in cursor.description]
        count_query = sql.SQL(
            "SELECT COUNT(*) AS total FROM {}"
        ).format(qualified_table)
        total = conn.execute(count_query).fetchone()["total"]
        return {
            "table_name": table_name,
            "columns": columns,
            "data": data,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()
