from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from db import get_connection
from routers import datasource, query, upload

app = FastAPI(
    title="Factory Data Management System",
    description="CSV/Excel upload into a SQLite database for the three Track 1 tables",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(datasource.router)
app.include_router(query.router)

Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@app.get("/")
async def root():
    return {
        "message": "Factory Data Management System API",
        "version": "1.1.0",
        "docs": "/docs",
        "tables": list(Config.ALLOWED_TABLES),
    }


@app.get("/health")
async def health_check():
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return {"status": "healthy", "database": str(Config.DB_PATH.name)}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
