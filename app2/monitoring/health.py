# app2/monitoring/health.py
import logging

from app2.core.settings import get_settings
from app2.db.session import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["monitoring"])
logger = logging.getLogger("app2.health")

settings = get_settings()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "asanclip-rag",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1")).scalar()

        from app2.bootstrap import faiss_index_status

        return {
            "status": "ready",
            "database": "connected",
            "cache": "enabled" if settings.ENABLE_CACHE else "disabled",
            "faiss": faiss_index_status(),
        }
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail="service_not_ready") from exc
