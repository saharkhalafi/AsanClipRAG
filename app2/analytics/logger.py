# app2/analytics/logger.py
from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime
from typing import Any
from uuid import UUID

import numpy as np

from app2.db.session import SessionLocal
from app2.repositories.observability_repository import ObservabilityRepository


class ObservabilityLogger:
    def __init__(self, db=None):
        # Keep db arg for backward compatibility; logging uses its own session.
        self.logger = logging.getLogger("app2.observability")

    # ── Serialization helpers ──────────────────────────────────────────────────

    def _jsonable(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return value
        if isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {str(k): self._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._jsonable(v) for v in value]
        return str(value)

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    # ── Derived field defaults ─────────────────────────────────────────────────

    def _fill_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        query_text = str(
            data.get("query_normalized") or data.get("query_raw") or ""
        ).strip()

        if "query_hash" not in data:
            data["query_hash"] = self._hash_query(query_text)
        if "query_length" not in data:
            data["query_length"] = len(query_text)
        if "token_count" not in data:
            data["token_count"] = len(query_text.split())
        if "char_count" not in data:
            data["char_count"] = len(query_text)
        if "estimated_input_tokens" not in data:
            data["estimated_input_tokens"] = len(query_text.split())
        if "estimated_output_tokens" not in data:
            data["estimated_output_tokens"] = 0
        if "total_tokens" not in data:
            data["total_tokens"] = (
                data["estimated_input_tokens"] + data["estimated_output_tokens"]
            )
        if "fallback_used" not in data:
            data["fallback_used"] = bool(
                data.get("retry_triggered") or data.get("bm25_used")
            )
        if "retrieval_quality_score" not in data:
            rq = data.get("retrieval_quality") or {}
            data["retrieval_quality_score"] = float(rq.get("retrieval_quality", 0.0))
        if "semantic_best_score" not in data:
            semantic = data.get("semantic") or {}
            data["semantic_best_score"] = float(semantic.get("best_score", 0.0))
        if "semantic_best_field" not in data:
            semantic = data.get("semantic") or {}
            data["semantic_best_field"] = semantic.get("best_field")
        if "cache_hit" not in data:
            data["cache_hit"] = False
        if "cache_layer" not in data:
            data["cache_layer"] = None
        if "blocked" not in data:
            data["blocked"] = False

        return data

    # ── Public API ─────────────────────────────────────────────────────────────

    def log_search_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._jsonable(payload)
        data = self._fill_defaults(data)

        db = SessionLocal()
        try:
            repo = ObservabilityRepository(db)
            row = repo.create_log(data)
            if row is None:
                self.logger.error(
                    "Failed to persist retrieval log for request %s",
                    data.get("request_id"),
                )
                return {"ok": False, "error": "db_write_failed"}

            self.logger.info(
                "Logged search event %s for request %s",
                row.id,
                data.get("request_id"),
            )
            return {"ok": True, "id": row.id}
        except Exception:
            self.logger.exception("Failed to write observability log")
            return {"ok": False, "error": "db_write_failed"}
        finally:
            db.close()
