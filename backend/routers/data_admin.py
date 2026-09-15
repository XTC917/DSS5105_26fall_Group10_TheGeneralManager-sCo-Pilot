"""Main PostgreSQL Data Management API."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from psycopg import sql

from backend.pg_config import ADMIN_META_SCHEMA, PG_SCHEMA
from backend.services.auth import require_admin
from backend.services.data_admin import assert_allowed_table
from backend.services.file_importer import FileImporter
from backend.services.pg_database import connect
from backend.services.schema_service import schema_service

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
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
        raise HTTPException(400, f"Unsupported file format: {ext or '(none)'}")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR / f"{uuid4().hex}{ext}"


async def _read_limited(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, "Uploaded file exceeds the 100MB limit")
    if not content:
        raise HTTPException(400, "Uploaded file is empty")
    return content


@upload_router.post("/upload/preview")
async def preview_file(file: UploadFile = File(...), _admin=Depends(require_admin)):
    path = _safe_upload_path(file.filename or "upload.csv")
    try:
        content = await _read_limited(file)
        path.write_bytes(content)
        result = _importer.preview_file(str(path), file.filename)
        result["file_size"] = len(content)
        return result
    finally:
        path.unlink(missing_ok=True)


@upload_router.post("/upload/import")
async def import_file(background_tasks: BackgroundTasks, _admin=Depends(require_admin),
                      file: UploadFile = File(...), table_name: str = Form(...),
                      if_exists: str = Form("replace")):
    try:
        table_name = assert_allowed_table(table_name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if if_exists not in {"replace", "append"}:
        raise HTTPException(400, "if_exists must be 'replace' or 'append'")
    path = _safe_upload_path(file.filename or "upload.csv")
    try:
        content = await _read_limited(file)
        path.write_bytes(content)
        name = Path(file.filename or "upload.csv").name
        preview = _importer.preview_file(str(path), name)
        upload_id = _importer.create_upload_record(name, len(content), preview["total_rows"])
        background_tasks.add_task(_process_import_task, str(path), upload_id, table_name, if_exists, name)
        return {"success": True, "message": "File received, importing in background...", "upload_id": upload_id, "table_name": table_name, "total_rows": preview["total_rows"], "columns": preview["columns"]}
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _process_import_task(path: str, upload_id: int, table_name: str, if_exists: str, filename: str):
    try:
        total, success, error = _importer.import_file(path, table_name, if_exists)
        _importer.create_import_detail(upload_id, filename, table_name, total, success, error)
        _importer.update_upload_record(upload_id, "failed" if error else "success", error, total)
        if not error:
            _importer.register_data_source(table_name, filename, f"Imported from {filename}, {success} records")
    except Exception as exc:
        _importer.update_upload_record(upload_id, "failed", str(exc))
    finally:
        Path(path).unlink(missing_ok=True)


@upload_router.get("/upload/status/{upload_id}")
async def get_import_status(upload_id: int, _admin=Depends(require_admin)):
    with connect(admin=True) as conn:
        upload = conn.execute(f"SELECT id,file_name,file_type,total_rows,status,error_message,uploaded_by,created_at,completed_at FROM {ADMIN_META_SCHEMA}.upload_history WHERE id=%s", (upload_id,)).fetchone()
        if upload is None:
            raise HTTPException(404, "Upload record not found")
        details = conn.execute(f"SELECT file_name,table_name,total_rows,success_rows,failed_rows,status,error_message,created_at,completed_at FROM {ADMIN_META_SCHEMA}.import_details WHERE upload_id=%s", (upload_id,)).fetchall()
    result = dict(upload)
    result["details"] = [dict(row) for row in details]
    return result


@datasource_router.get("/")
async def list_datasources(_admin=Depends(require_admin)):
    with connect(admin=True) as conn:
        rows = conn.execute(f"SELECT id,source_name,table_name,original_file,description,is_active,row_count,created_at,updated_at FROM {ADMIN_META_SCHEMA}.data_sources ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@datasource_router.get("/{datasource_id}")
async def get_datasource(datasource_id: int, _admin=Depends(require_admin)):
    with connect(admin=True) as conn:
        row = conn.execute(f"SELECT * FROM {ADMIN_META_SCHEMA}.data_sources WHERE id=%s", (datasource_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Data source not found")
    return dict(row)


@datasource_router.delete("/{datasource_id}")
async def delete_datasource(datasource_id: int, _admin=Depends(require_admin), drop_table: bool = Query(False)):
    with connect(admin=True) as conn, conn.transaction():
        row = conn.execute(f"SELECT table_name FROM {ADMIN_META_SCHEMA}.data_sources WHERE id=%s", (datasource_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Data source not found")
        table = assert_allowed_table(row["table_name"])
        count = None
        if drop_table:
            conn.execute(sql.SQL("DELETE FROM {}.{}").format(sql.Identifier(PG_SCHEMA), sql.Identifier(table)))
            conn.execute(f"UPDATE {ADMIN_META_SCHEMA}.data_sources SET row_count=0,is_active=FALSE,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (datasource_id,))
            count = 0
        else:
            conn.execute(f"UPDATE {ADMIN_META_SCHEMA}.data_sources SET is_active=FALSE,updated_at=CURRENT_TIMESTAMP WHERE id=%s", (datasource_id,))
    return {"success": True, "message": "Data source cleared" if drop_table else "Data source deactivated", "row_count": count}


@datasource_router.get("/{datasource_id}/data")
async def get_datasource_data(datasource_id: int, _admin=Depends(require_admin), limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    with connect(admin=True) as conn:
        row = conn.execute(f"SELECT table_name FROM {ADMIN_META_SCHEMA}.data_sources WHERE id=%s", (datasource_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Data source not found")
        table = assert_allowed_table(row["table_name"])
        ident = sql.Identifier(PG_SCHEMA, table)
        cur = conn.execute(sql.SQL("SELECT * FROM {} LIMIT %s OFFSET %s").format(ident), (limit, offset))
        data = cur.fetchall()
        total = conn.execute(sql.SQL("SELECT COUNT(*) AS total FROM {}").format(ident)).fetchone()["total"]
    return {"table_name": table, "columns": [{"name": c.name} for c in cur.description], "data": [dict(row) for row in data], "total": total, "limit": limit, "offset": offset}


@query_router.get("/schema")
async def get_schema(_user=Depends(require_admin)):
    return {"success": True, "schema": schema_service.get_live_schema()}


@query_router.post("/execute")
async def execute_query(request: QueryRequest, _user=Depends(require_admin)):
    if not request.sql:
        raise HTTPException(400, "SQL statement is required")
    try:
        results = schema_service.execute_query(request.sql)
        truncated = len(results) > 100
        return {"success": True, "data": results[:100], "total": min(len(results), 100), "truncated": truncated, "sql": request.sql}
    except ValueError as exc:
        return {"success": False, "error": str(exc), "sql": request.sql}
