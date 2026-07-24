"""
app2/api/routes.py
──────────────────
Request flow with Rate Limiting and Observability
"""
from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app2.db.session import get_db
from app2.services.search_orchestrator import SearchOrchestrator
from app2.metadata.metadata_loader import MetadataLoader
from app2.embedding.embedding_service import EmbeddingService
from app2.firewall.semantic_intent import SemanticIntentDetector
from app2.firewall.query_firewall import QueryFirewall
from app2.analytics.event_builder import SearchEventBuilder
from app2.analytics.logger import ObservabilityLogger

# Exception Handling
from app2.exceptions import ValidationError

router = APIRouter()
api_logger = logging.getLogger("app2.api")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)


# ── Request schema ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str


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
        embedder=EmbeddingService(),
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
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-Id"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    request_id = uuid4().hex
    query      = req.query
    obs_logger = ObservabilityLogger()

    t_total = perf_counter()

    try:
        # ── 0. Metadata — ONE DB round-trip ────────────────────
        meta = MetadataLoader(db).load()

        # ── 1. Firewall (always runs) ──────────────────────────────────────────────
        t_fw      = perf_counter()
        firewall  = _build_firewall(meta=meta, db=db)
        fw_result = firewall.check(query)
        fw_latency = round((perf_counter() - t_fw) * 1000, 2)

        # ── 2a. Blocked path ───────────────────────────────────────────────────────
        if not fw_result.get("allowed", False):
            total_latency = round((perf_counter() - t_total) * 1000, 2)

            payload = SearchEventBuilder.from_firewall_block(
                query_raw     = query,
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
                "query":   query,
                "results": [],
            }

        # ── 2b. Search path ────────────────────────────────────────────────────────
        orchestrator  = SearchOrchestrator(db=db, meta=meta)
        result        = orchestrator.search(query)
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
        # لاگ ValidationError هم ذخیره شود
        total_latency = round((perf_counter() - t_total) * 1000, 2)

        payload = SearchEventBuilder.from_firewall_block(
            query_raw     = query,
            fw_context    = {"reason": str(e), "allowed": False},
            request_id    = request_id,
            fw_latency    = 0,
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

    except Exception as e:
        #manage unexpected errors golbally
        raise