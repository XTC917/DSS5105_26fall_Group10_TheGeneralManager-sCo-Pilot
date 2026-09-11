"""Data Management API: upload / data sources / read-only query.

Merged from SQL_related_app/backend/routers/{upload,datasource,query}.py
into the main FastAPI app. All state lives in the shared data/factory.db;
metadata tables are created by FactoryDB.ensure_admin_tables().
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile

from backend.config import DATA_DIR
from backend.services.data_admin import assert_allowed_table, quote_table
from backend.services.database import get_db
from backend.services.file_importer import FileImporter
from backend.services.schema_service import schema_service
from pydantic import BaseModel

UPLOAD_DIR = DATA_DIR / "uploads"
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

_importer = FileImporter()

upload_router = APIRouter(prefix="/api/admin", tags=["Upload"])
datasource_router = APIRouter(prefix="/api/admin/datasources", tags=["Data Sources"])
query_router = APIRouter(prefix="/api/query", tags=["Data Query"])


class QueryRequest(BaseModel):
    question: str | None = None
    sql: str | None = None


def _safe_upload_path(filename: str) -> Path:
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file format: {ext or '(none)'}, allowed: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS)),
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR / f"{uuid4().hex}{ext}"


async def _read_limited(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            400,
            f"File too large: {len(content) / (1024 * 1024):.1f}MB, "
            f"max: {MAX_FILE_SIZE / (1024 * 1024):.0f}MB",
        )
    if not content:
        raise HTTPException(400, "Uploaded file is empty")
    return content


@upload_router.post("/upload/preview")
async def preview_file(file: UploadFile = File(...)):
    original_name = file.filename or "upload.csv"
    temp_path = _safe_upload_path(original_name)
    try:
        content = await _read_limited(file)
        temp_path.write_bytes(content)
        preview_result = _importer.preview_file(str(temp_path), original_name=original_name)
        preview_result["file_size"] = len(content)
        return preview_result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Preview failed: {exc}") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


@upload_router.post("/upload/import")
async def import_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    table_name: str = Form(...),
    if_exists: str = Form("replace"),
):
    original_name = file.filename or "upload.csv"
    try:
        table_name = assert_allowed_table(table_name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if if_exists not in {"replace", "append"}:
        raise HTTPException(400, "if_exists must be 'replace' or 'append'")

    temp_path = _safe_upload_path(original_name)
    try:
        content = await _read_limited(file)
        temp_path.write_bytes(content)
        preview = _importer.preview_file(str(temp_path), original_name=original_name)
        upload_id = _importer.create_upload_record(
            Path(original_name).name, len(content), preview.get("total_rows", 0)
        )
        background_tasks.add_task(
            _process_import_task,
            temp_path=str(temp_path),
            upload_id=upload_id,
            table_name=table_name,
            if_exists=if_exists,
            original_filename=Path(original_name).name,
        )
        return {
            "success": True,
            "message": "File received, importing in background...",
            "upload_id": upload_id,
            "table_name": table_name,
            "total_rows": preview.get("total_rows", 0),
            "columns": preview.get("columns", []),
        }
    except HTTPException:
        if temp_path.exists():
            temp_path.unlink()
        raise
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(400, f"Import failed: {exc}") from exc


@upload_router.get("/upload/status/{upload_id}")
async def get_import_status(upload_id: int):
    with get_db().connect() as conn:
        upload = conn.execute(
            """
            SELECT id, file_name, file_type, total_rows, status,
                   error_message, uploaded_by, created_at, completed_at
            FROM upload_history WHERE id = ?
            """,
            (upload_id,),
        ).fetchone()
        if not upload:
            raise HTTPException(404, "Upload record not found")
        details = conn.execute(
            """
            SELECT file_name, table_name, total_rows, success_rows,
                   failed_rows, status, error_message, created_at, completed_at
            FROM import_details WHERE upload_id = ?
            """,
            (upload_id,),
        ).fetchall()
        result = dict(upload)
        result["details"] = [dict(row) for row in details]
        return result


def _process_import_task(
    temp_path: str,
    upload_id: int,
    table_name: str,
    if_exists: str,
    original_filename: str,
):
    try:
        total_rows, success_rows, error = _importer.import_file(
            temp_path, table_name, if_exists
        )
        if error:
            _importer.create_import_detail(
                upload_id,
                original_filename,
                table_name,
                total_rows,
                success_rows,
                error,
            )
            _importer.update_upload_record(upload_id, "failed", error, total_rows)
        else:
            _importer.create_import_detail(
                upload_id,
                original_filename,
                table_name,
                total_rows,
                success_rows,
                None,
            )
            _importer.register_data_source(
                table_name,
                original_filename,
                f"Imported from {original_filename}, {success_rows} records",
            )
            _importer.update_upload_record(upload_id, "success", None, total_rows)
    except Exception as exc:
        _importer.update_upload_record(upload_id, "failed", str(exc))
    finally:
        path = Path(temp_path)
        if path.exists():
            path.unlink()


@datasource_router.get("/")
async def list_datasources():
    with get_db().connect() as conn:
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


@datasource_router.get("/{datasource_id}")
async def get_datasource(datasource_id: int):
    with get_db().connect() as conn:
        row = conn.execute(
            "SELECT * FROM data_sources WHERE id = ?",
            (datasource_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Data source not found")
        return dict(row)


@datasource_router.delete("/{datasource_id}")
async def delete_datasource(
    datasource_id: int,
    drop_table: bool = Query(False),
):
    """Deactivate the catalog row. The three business tables are never dropped.

    drop_table=true clears rows in the allowlisted table instead of DROP TABLE.
    """
    db = get_db()
    with db.connect() as conn:
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
            count_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM {quote_table(table_name)}"
            ).fetchone()
            row_count = int(count_row["cnt"]) if count_row else None
        else:
            conn.execute(
                """
                UPDATE data_sources
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (datasource_id,),
            )
            row_count = None
        conn.commit()
        return {
            "success": True,
            "message": "Data source cleared" if drop_table else "Data source deactivated",
            "row_count": row_count,
        }


@datasource_router.get("/{datasource_id}/data")
async def get_datasource_data(
    datasource_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = get_db()
    with db.connect() as conn:
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
        columns = [
            {
                "cid": r["cid"],
                "name": r["name"],
                "type": r["type"],
                "notnull": r["notnull"],
                "dflt_value": r["dflt_value"],
                "pk": r["pk"],
            }
            for r in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
        ]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "columns": columns,
            "data": [dict(item) for item in data],
        }


@query_router.get("/schema")
async def get_schema():
    return {"success": True, "schema": schema_service.get_live_schema()}


@query_router.post("/execute")
async def execute_query(request: QueryRequest):
    if not request.sql:
        raise HTTPException(400, "SQL statement is required")
    try:
        results = schema_service.execute_query(request.sql)
        return {
            "success": True,
            "data": results[:100],
            "total": len(results),
            "sql": request.sql,
            "message": (
                f"Returning first 100 of {len(results)} results"
                if len(results) > 100
                else None
            ),
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc), "sql": request.sql}
