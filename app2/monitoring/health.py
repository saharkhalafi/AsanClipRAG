# app2/monitoring/health.py
import os

from app2.core.settings import get_settings
from app2.db.session import get_db
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(tags=["monitoring"])

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

        log_stats = db.execute(
            text(
                """
                SELECT
                    count(*) AS total,
                    max(id) AS latest_id,
                    max(created_at) AS latest_created_at
                FROM retrieval_logs
                """
            )
        ).mappings().one()

        server_addr = db.execute(text("SELECT inet_server_addr()")).scalar()

        from app2.bootstrap import faiss_index_status

        return {
            "status": "ready",
            "database": "connected",
            "database_url": os.getenv("DATABASE_URL", ""),
            "postgres_server_addr": str(server_addr),
            "retrieval_logs_count": int(log_stats["total"] or 0),
            "retrieval_logs_latest_id": log_stats["latest_id"],
            "retrieval_logs_latest_created_at": (
                log_stats["latest_created_at"].isoformat()
                if log_stats["latest_created_at"]
                else None
            ),
            "cache": "enabled" if settings.ENABLE_CACHE else "disabled",
            "faiss": faiss_index_status(),
            "hint": (
                "Compare retrieval_logs_count with your SQL client. "
                "Docker Postgres is exposed on host port 5433, not 5432."
            ),
        }
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}
