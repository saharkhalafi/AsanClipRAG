from typing import Any, Dict, List

from sqlalchemy import func
from app2.db.models import RetrievalLog


class ObservabilityMetrics:
    def __init__(self, db):
        self.db = db

    def summary(self) -> Dict[str, Any]:
        total = self.db.query(func.count(RetrievalLog.id)).scalar() or 0
        blocked = (
            self.db.query(func.count(RetrievalLog.id))
            .filter(RetrievalLog.blocked.is_(True))
            .scalar()
            or 0
        )
        cache_hits = (
            self.db.query(func.count(RetrievalLog.id))
            .filter(RetrievalLog.cache_hit.is_(True))
            .scalar()
            or 0
        )

        avg_latency = (
            self.db.query(func.avg(RetrievalLog.latency_total_ms)).scalar() or 0.0
        )
        avg_quality = (
            self.db.query(func.avg(RetrievalLog.retrieval_quality_score)).scalar()
            or 0.0
        )
        retry_count = (
            self.db.query(func.count(RetrievalLog.id))
            .filter(RetrievalLog.retry_triggered.is_(True))
            .scalar()
            or 0
        )
        fallback_count = (
            self.db.query(func.count(RetrievalLog.id))
            .filter(RetrievalLog.fallback_used.is_(True))
            .scalar()
            or 0
        )

        return {
            "total_queries": total,
            "blocked_queries": blocked,
            "blocked_rate": (blocked / total) if total else 0.0,
            "cache_hits": cache_hits,
            "cache_hit_rate": (cache_hits / total) if total else 0.0,
            "avg_latency_ms": float(avg_latency),
            "avg_retrieval_quality": float(avg_quality),
            "retry_rate": (retry_count / total) if total else 0.0,
            "fallback_rate": (fallback_count / total) if total else 0.0,
        }

    def export_intent_dataset_rows(self, limit: int = 10_000) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(RetrievalLog)
            .order_by(RetrievalLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "request_id": r.request_id,
                "query_raw": r.query_raw,
                "query_normalized": r.query_normalized,
                "query_hash": r.query_hash,
                "blocked": r.blocked,
                "block_reason": r.block_reason,
                "firewall_reason": r.firewall_reason,
                "semantic_best_field": r.semantic_best_field,
                "semantic_best_score": r.semantic_best_score,
                "mode": r.mode,
                "route_reason": r.route_reason,
                "retrieval_quality_score": r.retrieval_quality_score,
                "candidate_count": r.candidate_count,
                "retry_triggered": r.retry_triggered,
                "fallback_used": r.fallback_used,
                "result_count": r.result_count,
                "top_result_id": r.top_result_id,
                "top_result_score": r.top_result_score,
                "manual_intent_label": r.manual_intent_label,
                "manual_relevance_label": r.manual_relevance_label,
                # Cache fields 
                "cache_hit": r.cache_hit,
                "cache_layer": r.cache_layer,
            }
            for r in rows
        ]