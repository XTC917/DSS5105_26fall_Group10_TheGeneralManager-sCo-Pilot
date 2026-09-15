"""PostgreSQL CSV/Excel importer for the integrated main backend."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from psycopg import sql

from backend.pg_config import ADMIN_META_SCHEMA, PG_SCHEMA
from backend.services.pg_database import connect
from backend.services.data_admin import DATA_SOURCES_META, TABLE_SCHEMAS, assert_allowed_table


class FileImporter:
    def detect_file_type(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return "csv" if ext == ".csv" else "excel" if ext in {".xlsx", ".xls"} else "unknown"

    def read_file(self, file_path: str) -> pd.DataFrame:
        file_type = self.detect_file_type(file_path)
        if file_type == "csv":
            last_error: Optional[Exception] = None
            for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312", "latin1"):
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError as exc:
                    last_error = exc
            raise ValueError(f"Unable to detect CSV file encoding: {last_error}")
        if file_type == "excel":
            return pd.read_excel(file_path)
        raise ValueError(f"Unsupported file type: {file_type}")

    def preview_file(self, file_path: str, original_name: str | None = None) -> dict[str, Any]:
        df = self.read_file(file_path)
        # NaN 不是合法 JSON，必须先替换成 None，否则 /preview 会 500。
        display = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        preview_records = display.head(10).to_dict(orient="records")
        return {
            "success": True,
            "file_name": Path(original_name or file_path).name,
            "file_type": self.detect_file_type(file_path),
            "total_rows": int(len(df)), "total_cols": int(len(df.columns)),
            "columns": [str(c) for c in df.columns],
            "preview_data": preview_records,
            "sample_types": {str(k): str(v) for k, v in df.dtypes.astype(str).to_dict().items()},
            "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
        }

    def _prepare_frame(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        df = df.dropna(how="all").copy()
        df.columns = [str(c).strip() for c in df.columns]
        schema = TABLE_SCHEMAS[table_name]
        required = [c for c in schema["columns"] if c not in schema.get("nullable_columns", [])]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"File is missing required columns for {table_name}: {', '.join(missing)}")
        df = df.drop(columns=[c for c in df.columns if c not in schema["columns"]], errors="ignore")
        for col in schema["columns"]:
            if col not in df.columns:
                df[col] = np.nan
        df = df[schema["columns"]]
        nullable = set(schema.get("nullable_columns", []))
        for col in schema.get("date_columns", []):
            parsed = pd.to_datetime(df[col].replace("", np.nan), errors="coerce")
            df[col] = parsed.dt.date
            df.loc[parsed.isna(), col] = None
        for col in schema.get("int_columns", []):
            numeric = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            if (numeric.dropna() % 1 != 0).any():
                raise ValueError(f"Column {col} must contain integers")
            df[col] = numeric.apply(lambda v: None if pd.isna(v) else int(v))
        for col in schema.get("float_columns", []):
            numeric = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            df[col] = numeric.apply(lambda v: None if pd.isna(v) else float(v))
        for col in df.columns:
            if col in schema.get("date_columns", []) + schema.get("int_columns", []) + schema.get("float_columns", []):
                continue
            df[col] = df[col].replace(["", "NULL"], np.nan)
            df[col] = df[col].where(pd.notnull(df[col]), None)
        invalid = {c: int(df[c].isna().sum()) for c in required if df[c].isna().any()}
        if invalid:
            raise ValueError("Required columns contain missing or invalid values: " + ", ".join(f"{k}={v}" for k, v in invalid.items()))
        if table_name == "workshops":
            df["makes"] = df["makes"].astype(str).str.split("+", regex=False)
            df = df.explode("makes", ignore_index=True)
            df["makes"] = df["makes"].str.strip()
            if not set(df["makes"]) <= {"TOPS", "ACCESSORIES"}:
                raise ValueError("Workshop makes must be TOPS or ACCESSORIES")
            if df.duplicated(["workshop_id", "makes"]).any():
                raise ValueError("Duplicate workshop capability key")
            shared = [c for c in schema["columns"] if c not in {"workshop_id", "makes"}]
            if (df.groupby("workshop_id", dropna=False)[shared].nunique(dropna=False) > 1).any(axis=None):
                raise ValueError("Inconsistent shared workshop attributes")
        return df

    def _database_columns(self, table_name: str) -> list[str]:
        return ["production_date" if c == "date" else c for c in TABLE_SCHEMAS[table_name]["columns"]]

    def import_file(self, file_path: str, table_name: str, if_exists: str = "replace") -> tuple[int, int, str | None]:
        try:
            table_name = assert_allowed_table(table_name)
            if if_exists not in {"replace", "append"}:
                return 0, 0, "if_exists must be 'replace' or 'append'"
            df = self._prepare_frame(self.read_file(file_path), table_name)
            columns = self._database_columns(table_name)
            values = [tuple(None if isinstance(v, float) and np.isnan(v) else v for v in row) for row in df.itertuples(index=False, name=None)]
            table = sql.Identifier(PG_SCHEMA, table_name)
            query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(table, sql.SQL(",").join(map(sql.Identifier, columns)), sql.SQL(",").join(sql.Placeholder() for _ in columns))
            with connect(admin=True) as conn, conn.transaction():
                if if_exists == "replace":
                    conn.execute(sql.SQL("DELETE FROM {}").format(table))
                with conn.cursor() as cur:
                    cur.executemany(query, values)
                if table_name == "orders":
                    conn.execute(sql.SQL("""INSERT INTO {} (order_id,status,stage,date)
                        SELECT order_id,status,current_stage,last_activity_date FROM {}
                        ON CONFLICT (order_id,status,stage,date) DO NOTHING""").format(sql.Identifier(PG_SCHEMA, "snapshot"), table))
                count = conn.execute(sql.SQL("SELECT COUNT(*) AS c FROM {}").format(table)).fetchone()["c"]
                conn.execute(f"UPDATE {ADMIN_META_SCHEMA}.data_sources SET row_count=%s, is_active=TRUE, updated_at=CURRENT_TIMESTAMP WHERE table_name=%s", (count, table_name))
            return len(df), len(values), None
        except Exception as exc:
            return 0, 0, str(exc)

    def create_upload_record(self, file_name: str, file_size: int, total_rows: int = 0) -> int:
        del file_size
        with connect(admin=True) as conn, conn.transaction():
            row = conn.execute(f"INSERT INTO {ADMIN_META_SCHEMA}.upload_history (file_name,file_type,total_rows,status) VALUES (%s,%s,%s,'processing') RETURNING id", (file_name, self.detect_file_type(file_name), total_rows)).fetchone()
        return int(row["id"])

    def update_upload_record(self, upload_id: int, status: str, error_message: str | None = None, total_rows: int | None = None) -> None:
        with connect(admin=True) as conn, conn.transaction():
            conn.execute(f"UPDATE {ADMIN_META_SCHEMA}.upload_history SET status=%s,error_message=%s,total_rows=COALESCE(%s,total_rows),completed_at=CASE WHEN %s IN ('success','failed') THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=%s", (status, error_message, total_rows, status, upload_id))

    def create_import_detail(self, upload_id: int, file_name: str, table_name: str, total_rows: int, success_rows: int, error_message: str | None = None) -> None:
        status = "success" if error_message is None else "failed"
        with connect(admin=True) as conn, conn.transaction():
            conn.execute(f"INSERT INTO {ADMIN_META_SCHEMA}.import_details (upload_id,file_name,table_name,total_rows,success_rows,failed_rows,status,error_message,completed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)", (upload_id, file_name, table_name, total_rows, success_rows, max(total_rows-success_rows, 0), status, error_message))

    def register_data_source(self, table_name: str, original_file: str, description: str | None = None) -> None:
        meta = DATA_SOURCES_META[assert_allowed_table(table_name)]
        with connect(admin=True) as conn, conn.transaction():
            count = conn.execute(f"SELECT COUNT(*) AS c FROM {PG_SCHEMA}.{table_name}").fetchone()["c"]
            conn.execute(f"""INSERT INTO {ADMIN_META_SCHEMA}.data_sources
                (source_name,table_name,original_file,description,row_count,is_active,updated_at)
                VALUES (%s,%s,%s,%s,%s,TRUE,CURRENT_TIMESTAMP)
                ON CONFLICT(table_name) DO UPDATE SET original_file=excluded.original_file,
                description=excluded.description,row_count=excluded.row_count,is_active=TRUE,
                updated_at=CURRENT_TIMESTAMP""", (meta["source_name"], table_name, original_file, description or meta["description"], count))
