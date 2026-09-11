from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from schema_service import schema_service

router = APIRouter(prefix="/api/query", tags=["Data Query"])


class QueryRequest(BaseModel):
    question: Optional[str] = None
    sql: Optional[str] = None


@router.get("/schema")
async def get_schema():
    return {"success": True, "schema": schema_service.get_live_schema()}


@router.post("/execute")
async def execute_query(request: QueryRequest):
    if not request.sql:
        raise HTTPException(400, "SQL statement is required")
    try:
        results = schema_service.execute_query(request.sql)
        truncated = len(results) > 100
        visible_results = results[:100]
        return {
            "success": True,
            "data": visible_results,
            "total": len(visible_results),
            "truncated": truncated,
            "sql": request.sql,
            "message": (
                "Returning the first 100 rows; more rows may exist"
                if truncated
                else None
            ),
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc), "sql": request.sql}
