from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from config import Config, assert_allowed_table, quote_column, quote_table
from db import get_connection, get_table_count, table_exists


class FileImporter:
    def detect_file_type(self, file_path: str) -> str:
        from pathlib import Path

        ext = Path(file_path).suffix.lower()
        if ext == ".csv":
            return "csv"
        if ext in {".xlsx", ".xls"}:
            return "excel"
        return "unknown"

    def read_file(self, file_path: str) -> pd.DataFrame:
        file_type = self.detect_file_type(file_path)
        if file_type == "csv":
            encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin1"]
            last_error: Optional[Exception] = None
            for encoding in encodings:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError as exc:
                    last_error = exc
            raise ValueError(f"Unable to detect CSV file encoding: {last_error}")
        if file_type == "excel":
            return pd.read_excel(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")

    def preview_file(self, file_path: str, original_name: Optional[str] = None) -> Dict[str, Any]:
        from pathlib import Path

        df = self.read_file(file_path)
        df_display = df.where(pd.notnull(df), None)
        file_name = Path(original_name or file_path).name
        suggested_table = None
        lower_name = file_name.lower()
        for pattern, table in Config.FILE_TABLE_MAPPING.items():
            if pattern.lower() in lower_name:
                suggested_table = table
                break
        return {
            "success": True,
            "file_name": file_name,
            "file_type": self.detect_file_type(file_path),
            "total_rows": int(len(df)),
            "total_cols": int(len(df.columns)),
            "columns": [str(c) for c in df.columns],
            "preview_data": df_display.head(10).to_dict(orient="records"),
            "sample_types": df.dtypes.astype(str).to_dict(),
            "null_counts": df.isnull().sum().astype(int).to_dict(),
            "suggested_table": suggested_table,
        }

    def import_file(
        self,
        file_path: str,
        table_name: str,
        if_exists: str = "replace",
    ) -> Tuple[int, int, Optional[str]]:
        try:
            table_name = assert_allowed_table(table_name)
            if if_exists not in {"replace", "append"}:
                return 0, 0, "if_exists must be 'replace' or 'append'"
            if not table_exists(table_name):
                return 0, 0, "Database is not initialized. Run python init_db.py"

            df = self.read_file(file_path)
            if df.empty:
                return 0, 0, "File is empty"

            df = self._prepare_frame(df, table_name)
            total_rows = len(df)
            success_rows = self._write_rows(df, table_name, if_exists)
            self._update_data_source_count(table_name)
            return total_rows, success_rows, None
        except Exception as exc:
            return 0, 0, str(exc)

    def _prepare_frame(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        df = df.dropna(how="all")
        df.columns = [str(col).strip() for col in df.columns]
        schema = Config.TABLE_SCHEMAS[table_name]
        required = [
            col
            for col in schema["columns"]
            if col not in schema.get("nullable_columns", [])
        ]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(
                f"File is missing required columns for {table_name}: {', '.join(missing)}"
            )

        extra = [col for col in df.columns if col not in schema["columns"]]
        if extra:
            df = df.drop(columns=extra)

        for col in schema["columns"]:
            if col not in df.columns:
                df[col] = np.nan

        df = df[schema["columns"]]
        nullable = set(schema.get("nullable_columns", []))

        for col in schema.get("date_columns", []):
            df[col] = df[col].replace("", np.nan)
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = parsed.dt.strftime("%Y-%m-%d")
            df.loc[parsed.isna(), col] = None

        for col in schema.get("int_columns", []):
            df[col] = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            if col not in nullable:
                df[col] = df[col].fillna(0)
            df[col] = df[col].apply(lambda v: None if pd.isna(v) else int(v))

        for col in schema.get("float_columns", []):
            df[col] = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            if col not in nullable:
                df[col] = df[col].fillna(0)
            df[col] = df[col].apply(lambda v: None if pd.isna(v) else float(v))

        for col in df.columns:
            if col in schema.get("date_columns", []):
                continue
            if col in schema.get("int_columns", []):
                continue
            if col in schema.get("float_columns", []):
                continue
            df[col] = df[col].replace(["", "NULL"], np.nan)
            if col not in nullable:
                df[col] = df[col].where(pd.notnull(df[col]), "")
            else:
                df[col] = df[col].where(pd.notnull(df[col]), None)

        return df

    def _write_rows(self, df: pd.DataFrame, table_name: str, if_exists: str) -> int:
        columns: Sequence[str] = list(df.columns)
        table_sql = quote_table(table_name)
        col_sql = ", ".join(quote_column(table_name, col) for col in columns)
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = (
            f"INSERT OR REPLACE INTO {table_sql} ({col_sql}) VALUES ({placeholders})"
        )

        records = [
            tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]
        # Convert datetime/date leftovers to ISO strings
        cleaned = []
        for row in records:
            converted = []
            for value in row:
                if isinstance(value, datetime):
                    converted.append(value.date().isoformat())
                elif isinstance(value, date):
                    converted.append(value.isoformat())
                else:
                    converted.append(value)
            cleaned.append(tuple(converted))

        conn = get_connection()
        try:
            conn.execute("BEGIN")
            if if_exists == "replace":
                conn.execute(f"DELETE FROM {table_sql}")
            conn.executemany(insert_sql, cleaned)
            conn.commit()
            return len(cleaned)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _update_data_source_count(self, table_name: str) -> None:
        count = get_table_count(table_name)
        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE data_sources
                SET row_count = ?, updated_at = CURRENT_TIMESTAMP, is_active = 1
                WHERE table_name = ?
                """,
                (count, table_name),
            )
            conn.commit()
        finally:
            conn.close()

    def create_upload_record(
        self, file_name: str, file_size: int, total_rows: int = 0
    ) -> int:
        del file_size
        conn = get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO upload_history
                    (file_name, file_type, total_rows, status, created_at)
                VALUES (?, ?, ?, 'processing', CURRENT_TIMESTAMP)
                """,
                (file_name, self.detect_file_type(file_name), total_rows),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def update_upload_record(
        self,
        upload_id: int,
        status: str,
        error_message: Optional[str] = None,
        total_rows: Optional[int] = None,
    ) -> None:
        conn = get_connection()
        try:
            if total_rows is not None:
                conn.execute(
                    """
                    UPDATE upload_history
                    SET status = ?, error_message = ?, total_rows = ?,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, error_message, total_rows, upload_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE upload_history
                    SET status = ?, error_message = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, error_message, upload_id),
                )
            conn.commit()
        finally:
            conn.close()

    def create_import_detail(
        self,
        upload_id: int,
        file_name: str,
        table_name: str,
        total_rows: int,
        success_rows: int,
        error_message: Optional[str] = None,
    ) -> None:
        conn = get_connection()
        try:
            status = "success" if error_message is None else "failed"
            conn.execute(
                """
                INSERT INTO import_details (
                    upload_id, file_name, table_name, total_rows,
                    success_rows, failed_rows, status, error_message,
                    completed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    upload_id,
                    file_name,
                    table_name,
                    total_rows,
                    success_rows,
                    max(total_rows - success_rows, 0),
                    status,
                    error_message,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def register_data_source(
        self,
        table_name: str,
        original_file: str,
        description: Optional[str] = None,
    ) -> None:
        table_name = assert_allowed_table(table_name)
        meta = Config.DATA_SOURCES[table_name]
        count = get_table_count(table_name)
        conn = get_connection()
        try:
            conn.execute(
                """
                INSERT INTO data_sources (
                    source_name, table_name, original_file, description,
                    row_count, is_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(table_name) DO UPDATE SET
                    source_name = excluded.source_name,
                    original_file = excluded.original_file,
                    description = excluded.description,
                    row_count = excluded.row_count,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    meta["source_name"],
                    table_name,
                    original_file,
                    description or meta["description"],
                    count,
                ),
            )
            conn.commit()
        finally:
            conn.close()
