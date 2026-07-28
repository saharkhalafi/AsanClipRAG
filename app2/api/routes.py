"""
app2/api/routes.py
──────────────────
Request flow with Rate Limiting and Observability
"""
from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from app2.analytics.event_builder import SearchEventBuilder
from app2.analytics.logger import ObservabilityLogger
from app2.db.session import get_db
from app2.embedding.embedding_service import get_embedding_service

# Exception Handling
from app2.exceptions import ValidationError
from app2.firewall.query_firewall import QueryFirewall
from app2.firewall.semantic_intent import SemanticIntentDetector, _normalize as semantic_normalize
from app2.metadata.metadata_loader import MetadataLoader
from app2.services.query_preprocessor import QueryPreprocessor
from app2.services.search_orchestrator import SearchOrchestrator
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

router = APIRouter()
api_logger = logging.getLogger("app2.api")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)

_query_preprocessor = QueryPreprocessor()


# ── Request schema ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


# ── Shared factory ─────────────────────────────────────────────────────────────

def _build_firewall(meta: dict, db: Session) -> QueryFirewall:
    semantic_detector = SemanticIntentDetector(
        catalog={
            "product_types":  meta["product_types"],
            "occasions":      meta["occasions"],
            "platforms":      meta["platforms"],
            "product_names":  meta["product_names"],
        },
        sparse_fields=["occasions", "platforms", "product_types"],
        fallback_label_field="product_names",
        embedder=get_embedding_service(),
        db=db
    )
    return QueryFirewall(db=db, semantic_detector=semantic_detector)


def _persist_search_log(obs_logger: ObservabilityLogger, payload: dict) -> None:
    result = obs_logger.log_search_event(payload)
    if result.get("ok"):
        print(
            f"Saved retrieval_log id={result['id']} "
            f"mode={payload.get('mode')} "
            f"query={str(payload.get('query_raw', ''))[:60]}"
        )
        return

    api_logger.error(
        "retrieval_logs write failed for request %s: %s",
        payload.get("request_id"),
        result.get("error"),
    )


# ── Search endpoint with Rate Limiting ───────────────────────────────────────────

@router.post("/search")
@limiter.limit("5/minute")
async def search(
    req: SearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    request_id = uuid4().hex
    query_raw  = req.query
    query      = query_raw
    fw_latency = 0.0
    obs_logger = ObservabilityLogger()

    t_total = perf_counter()

    try:
        # ── 0. Preprocess once (shared by firewall + search + embed cache) ──
        query = _query_preprocessor.normalize(query_raw)

        # ── 1. Metadata (in-memory TTL cache) ────────────────────
        meta = MetadataLoader(db).load()

        # ── 2. Firewall (always runs) ──────────────────────────────────────────────
        t_fw      = perf_counter()
        firewall  = _build_firewall(meta=meta, db=db)
        fw_result = firewall.check(query)
        fw_latency = round((perf_counter() - t_fw) * 1000, 2)

        # ── 2a. Blocked path ───────────────────────────────────────────────────────
        if not fw_result.get("allowed", False):
            total_latency = round((perf_counter() - t_total) * 1000, 2)

            payload = SearchEventBuilder.from_firewall_block(
                query_raw     = query_raw,
                fw_context    = fw_result,
                request_id    = request_id,
                fw_latency    = fw_latency,
                total_latency = total_latency,
                session_id    = x_session_id,
                user_id       = x_user_id,
            )
            _persist_search_log(obs_logger, payload)

            return {
                "request_id": request_id,
                "mode":    "blocked_by_firewall",
                "reason":  fw_result.get("reason", "blocked"),
                "signals": fw_result.get("signals", {}),
                "query":   query_raw,
                "results": [],
            }

        # ── 2b. Search path ────────────────────────────────────────────────────────
        # Match embed cache key used by firewall relevance (semantic normalize).
        search_query = semantic_normalize(fw_result.get("normalized_query", query))
        orchestrator  = SearchOrchestrator(db=db, meta=meta)
        result        = orchestrator.search(
            query_raw,
            normalized_query=search_query,
            query_vector=fw_result.get("query_vector"),
            top_k=req.top_k,
        )
        total_latency = round((perf_counter() - t_total) * 1000, 2)

        payload = SearchEventBuilder.from_result(
            result        = result,
            fw_context    = fw_result,
            request_id    = request_id,
            fw_latency    = fw_latency,
            total_latency = total_latency,
            session_id    = x_session_id,
            user_id       = x_user_id,
        )
        _persist_search_log(obs_logger, payload)

        result.pop("observability", None)

        return {
            **result,
            "request_id":      request_id,
            "firewall":        fw_result.get("signals", {}),
            "firewall_reason": fw_result.get("reason", "ok"),
        }

    except ValidationError as e:
        total_latency = round((perf_counter() - t_total) * 1000, 2)
        ctx = getattr(e, "context", {}) or {}

        payload = SearchEventBuilder.from_firewall_block(
            query_raw     = query_raw,
            fw_context    = {
                "reason": str(e),
                "allowed": False,
                "signals": ctx.get("signals", {}),
                "normalized_query": ctx.get("normalized_query", query),
            },
            request_id    = request_id,
            fw_latency    = fw_latency,
            total_latency = total_latency,
            session_id    = x_session_id,
            user_id       = x_user_id,
        )
        _persist_search_log(obs_logger, payload)

        return {
            "request_id": request_id,
            "mode": "validation_error",
            "reason": str(e),
            "results": [],
        }

    except Exception:
        #manage unexpected errors golbally
        raise
