from typing import Any

from sqlalchemy.orm import Session

from app2.db.models import RetrievalLog


class ObservabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_log(self, payload: dict[str, Any]) -> RetrievalLog:
        row = RetrievalLog(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_recent(self, limit: int = 100) -> list[RetrievalLog]:
        return (
            self.db.query(RetrievalLog)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
            .all()
        )
