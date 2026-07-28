# app2/bootstrap.py
"""One-time startup warm-up for latency-sensitive services."""
from __future__ import annotations

import logging
import os

from app2.config.constants import EMBEDDING_DIMENSION, FAISS_INDEX_PATH
from app2.db.session import SessionLocal
from app2.metadata.metadata_loader import MetadataLoader
from app2.retrieval.faiss_index import get_faiss_index

logger = logging.getLogger("app2.bootstrap")


def warm_application() -> None:
    """Load caches and indexes before serving traffic."""
    _warm_metadata()
    _warm_faiss()
    _warm_embedding_client()


def _warm_metadata() -> None:
    try:
        db = SessionLocal()
        try:
            meta = MetadataLoader(db).load()
            logger.info(
                "Metadata cache warmed: %d types, %d occasions, %d platforms, %d names",
                len(meta.get("product_types", [])),
                len(meta.get("occasions", [])),
                len(meta.get("platforms", [])),
                len(meta.get("product_names", [])),
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Metadata warm-up skipped: %s", exc)


def _warm_faiss() -> None:
    try:
        index = get_faiss_index()
        if index.index is None:
            logger.warning(
                "FAISS index not found at %s — vector search will use pgvector",
                FAISS_INDEX_PATH,
            )
            return
        logger.info(
            "FAISS index loaded: %s vectors (dim=%d)",
            index.index.ntotal,
            EMBEDDING_DIMENSION,
        )
    except Exception as exc:
        logger.warning("FAISS warm-up skipped: %s", exc)


def _warm_embedding_client() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        logger.info("GEMINI_API_KEY not set — skipping embedding warm-up")
        return
    try:
        from app2.embedding.embedding_service import get_embedding_service

        service = get_embedding_service()
        # Prime Gemini client + Redis connection without a paid embed call.
        _ = service.cache.enabled
        logger.info("Embedding service client ready")
    except Exception as exc:
        logger.warning("Embedding warm-up skipped: %s", exc)


def faiss_index_status() -> dict:
    """Lightweight health info for /ready."""
    try:
        index = get_faiss_index()
        if index.index is None:
            return {"loaded": False, "path": FAISS_INDEX_PATH, "vectors": 0}
        return {
            "loaded": True,
            "path": FAISS_INDEX_PATH,
            "vectors": int(index.index.ntotal),
            "dimension": EMBEDDING_DIMENSION,
        }
    except Exception as exc:
        return {"loaded": False, "path": FAISS_INDEX_PATH, "error": str(exc)}
