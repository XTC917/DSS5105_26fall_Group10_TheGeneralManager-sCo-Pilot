from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from psycopg import sql

from config import Config, assert_allowed_table, get_database_columns
from db import get_postgres_admin_connection, get_postgres_table_count, postgres_table_exists

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
        total_rows = 0
        try:
            table_name = assert_allowed_table(table_name)
            if if_exists not in {"replace", "append"}:
                return 0, 0, "if_exists must be 'replace' or 'append'"
            if not postgres_table_exists(table_name):
                return 0, 0, (f"PostgreSQL table {Config.PG_SCHEMA}.{table_name} does not exist")

            df = self.read_file(file_path)
            total_rows = len(df)
            if df.empty:
                return 0, 0, "File is empty"

            df = self._prepare_frame(df, table_name)
            total_rows = len(df)
            if df.empty:
                return 0, 0, "File contains no non-empty data rows"
            success_rows = self._write_rows(df, table_name, if_exists)
            return total_rows, success_rows, None
        except Exception as exc:
            return total_rows, 0, str(exc)

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
            numeric = pd.to_numeric(df[col].replace("", np.nan), errors="coerce",)
            non_integer = (numeric.dropna() % 1) != 0
            if non_integer.any():
                raise ValueError(f"Column {col} must contain integers")
            df[col] = numeric.apply(lambda value: None if pd.isna(value) else int(value))

        for col in schema.get("float_columns", []):
            df[col] = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            df[col] = df[col].apply(lambda value: None if pd.isna(value) else float(value))

        for col in df.columns:
            if col in schema.get("date_columns", []):
                continue
            if col in schema.get("int_columns", []):
                continue
            if col in schema.get("float_columns", []):
                continue
            df[col] = df[col].replace(["", "NULL"], np.nan)
            df[col] = df[col].where(pd.notnull(df[col]), None)

        missing_required = {
            column: int(df[column].isna().sum())
            for column in required
            if df[column].isna().any()
        }

        if missing_required:
            details = ", ".join(
                f"{column}={count}"
                for column, count in missing_required.items()
            )
            raise ValueError(
                f"Required columns contain missing or invalid values: {details}"
            )

        return df

    def _map_database_columns(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        table_name = assert_allowed_table(table_name)
        schema = Config.TABLE_SCHEMAS[table_name]
        mapping = schema.get("column_mapping", {})
        mapped_df = df.rename(columns=mapping)
        database_columns = get_database_columns(table_name)
        return mapped_df[database_columns]

    def _write_rows(self, df: pd.DataFrame, table_name: str, if_exists: str) -> int:
        table_name = assert_allowed_table(table_name)
        database_df = self._map_database_columns(df, table_name)
        columns = list(database_df.columns)

        qualified_table = sql.Identifier(Config.PG_SCHEMA, table_name)
        column_list = sql.SQL(", ").join(sql.Identifier(column) for column in columns)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)

        insert_query = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({})"
        ).format(qualified_table, column_list, placeholders)
        delete_query = sql.SQL("DELETE FROM {}").format(qualified_table)
        records = [
            tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in row)
            for row in database_df.itertuples(index=False, name=None)
        ]
        cleaned = []
        for row in records:
            converted = []
            for value in row:
                if isinstance(value, datetime):
                    converted.append(value.date())
                elif isinstance(value, date):
                    converted.append(value)
                else:
                    converted.append(value)
            cleaned.append(tuple(converted))

        conn = get_postgres_admin_connection()
        try:
            with conn.transaction():
                if if_exists == "replace":
                    conn.execute(delete_query)
                with conn.cursor() as cursor:
                    cursor.executemany(insert_query, cleaned)
                count_query = sql.SQL(
                    "SELECT COUNT(*) AS cnt FROM {}"
                ).format(qualified_table)
                actual_count = conn.execute(count_query).fetchone()["cnt"]
                update_row = conn.execute(
                    """
                    UPDATE admin_meta.data_sources
                    SET row_count = %s,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                    WHERE table_name = %s
                    RETURNING id
                    """,
                    (actual_count, table_name)
                ).fetchone()
                if update_row is None:
                    raise ValueError(f"Data source metadata not found for table: {table_name}")
            return len(cleaned)
        finally:
            conn.close()

    def create_upload_record(
        self, file_name: str, file_size: int, total_rows: int = 0
    ) -> int:
        del file_size
        conn = get_postgres_admin_connection()
        try:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO admin_meta.upload_history
                    (file_name, file_type, total_rows, status)
                VALUES (%s, %s, %s, 'processing')
                RETURNING id
                """,
                (file_name, self.detect_file_type(file_name), total_rows,),
                ).fetchone()
                if row is None:
                    raise ValueError("Upload history record was not created")
            return int(row["id"])
        finally:
            conn.close()

    def update_upload_record(
        self,
        upload_id: int,
        status: str,
        error_message: Optional[str] = None,
        total_rows: Optional[int] = None,
    ) -> None:
        allowed_statuses = {"pending", "processing", "success", "failed"}
        if status not in allowed_statuses:
            raise ValueError(f"Invalid upload status: {status}")
        conn = get_postgres_admin_connection()
        try:
            with conn.transaction():
                row = conn.execute(
                    """
                    UPDATE admin_meta.upload_history
                    SET status = %s, error_message = %s, total_rows = COALESCE(%s, total_rows),
                        completed_at = CASE
                            WHEN %s IN ('success', 'failed')
                            THEN CURRENT_TIMESTAMP
                            ELSE NULL
                        END
                    WHERE id = %s
                    RETURNING id
                    """,
                    (status, error_message, total_rows, status, upload_id),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Upload record not found: {upload_id}")
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
        table_name = assert_allowed_table(table_name)
        if total_rows < 0:
            raise ValueError("total_rows cannot be negative")
        if success_rows < 0 or total_rows < success_rows:
            raise ValueError("success_rows must be between 0 and total_rows")
        failed_rows = total_rows - success_rows
        status = "success" if error_message is None else "failed"
        conn = get_postgres_admin_connection()
        try:
            with conn.transaction():
                row = conn.execute(
                    """
                    INSERT INTO admin_meta.import_details (
                        upload_id, file_name, table_name, total_rows,
                        success_rows, failed_rows, status, error_message, completed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    RETURNING id
                     """,
                    (
                        upload_id,
                        file_name,
                        table_name,
                        total_rows,
                        success_rows,
                        failed_rows,
                        status,
                        error_message,
                    ),
                ).fetchone()
                if row is None:
                    raise ValueError(f"Import detail record was not created")
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
        count = get_postgres_table_count(table_name)
        conn = get_postgres_admin_connection()
        try:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO admin_meta.data_sources (
                        source_name, table_name, original_file, description,
                        row_count, is_active, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT(table_name) DO UPDATE SET
                        source_name = excluded.source_name,
                        original_file = excluded.original_file,
                        description = excluded.description,
                        row_count = excluded.row_count,
                        is_active = TRUE,
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
        finally:
            conn.close()
