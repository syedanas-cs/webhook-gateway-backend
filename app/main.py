from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings
from app.core.database import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

@app.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    # Execute a lightweight query to test PostgreSQL connection
    result = await db.execute(text("SELECT 1"))
    db_status = "connected" if result.scalar() == 1 else "disconnected"

    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "version": settings.VERSION,
    }