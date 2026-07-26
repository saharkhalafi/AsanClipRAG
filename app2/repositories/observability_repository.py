# app2/repositories/observability_repository.py
import logging
from typing import Any

from app2.db.models import RetrievalLog
from app2.repositories.base import BaseRepository

logger = logging.getLogger("app2.observability")


class ObservabilityRepository(BaseRepository):

    def create_log(self, data: dict[str, Any]):
        """Safe log creation using a dedicated session."""
        clean_data = {}
        for key, value in data.items():
            if hasattr(RetrievalLog, key):
                clean_data[key] = value

        try:
            log = RetrievalLog(**clean_data)
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return log
        except Exception:
            self.db.rollback()
            logger.exception(
                "Failed to save retrieval log for request %s",
                data.get("request_id"),
            )
            return None

    def get_recent_logs(self, limit: int = 50):
        return self.db.query(RetrievalLog)\
            .order_by(RetrievalLog.created_at.desc())\
            .limit(limit)\
            .all()
