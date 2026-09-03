from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from config import Config, assert_allowed_table
from db import get_connection
from file_importer import FileImporter

router = APIRouter(prefix="/api/admin", tags=["Upload"])
importer = FileImporter()


def _safe_upload_path(filename: str) -> Path:
    ext = Path(filename or "").suffix.lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file format: {ext or '(none)'}, allowed: "
            + ", ".join(sorted(Config.ALLOWED_EXTENSIONS)),
        )
    Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return Config.UPLOAD_DIR / f"{uuid4().hex}{ext}"


async def _read_limited(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > Config.MAX_FILE_SIZE:
        raise HTTPException(
            400,
            f"File too large: {len(content) / (1024 * 1024):.1f}MB, "
            f"max: {Config.MAX_FILE_SIZE / (1024 * 1024):.0f}MB",
        )
    if not content:
        raise HTTPException(400, "Uploaded file is empty")
    return content


@router.post("/upload/preview")
async def preview_file(file: UploadFile = File(...)):
    original_name = file.filename or "upload.csv"
    temp_path = _safe_upload_path(original_name)
    try:
        content = await _read_limited(file)
        temp_path.write_bytes(content)
        preview_result = importer.preview_file(str(temp_path), original_name=original_name)
        preview_result["file_size"] = len(content)
        return preview_result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Preview failed: {exc}") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/upload/import")
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
        preview = importer.preview_file(str(temp_path), original_name=original_name)
        upload_id = importer.create_upload_record(
            Path(original_name).name, len(content), preview.get("total_rows", 0)
        )
        background_tasks.add_task(
            process_import_task,
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


@router.get("/upload/status/{upload_id}")
async def get_import_status(upload_id: int):
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def process_import_task(
    temp_path: str,
    upload_id: int,
    table_name: str,
    if_exists: str,
    original_filename: str,
):
    try:
        total_rows, success_rows, error = importer.import_file(
            temp_path, table_name, if_exists
        )
        if error:
            importer.create_import_detail(
                upload_id,
                original_filename,
                table_name,
                total_rows,
                success_rows,
                error,
            )
            importer.update_upload_record(upload_id, "failed", error, total_rows)
        else:
            importer.create_import_detail(
                upload_id,
                original_filename,
                table_name,
                total_rows,
                success_rows,
                None,
            )
            importer.register_data_source(
                table_name,
                original_filename,
                f"Imported from {original_filename}, {success_rows} records",
            )
            importer.update_upload_record(upload_id, "success", None, total_rows)
    except Exception as exc:
        importer.update_upload_record(upload_id, "failed", str(exc))
    finally:
        path = Path(temp_path)
        if path.exists():
            path.unlink()
