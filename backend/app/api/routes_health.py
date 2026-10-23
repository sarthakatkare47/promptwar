from datetime import datetime, timezone
from fastapi import APIRouter
from app.config import settings
from app.db.connection import get_connection
from app.schemas.api import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health():
    db_status = "ok"
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        db_status = "error"

    gemini_key = settings.GEMINI_API_KEY.get_secret_value()
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version="0.1.0",
        extractor=settings.EXTRACTOR,
        gemini_configured=bool(gemini_key),
        database=db_status,
        time=datetime.now(timezone.utc).isoformat(),
    )
