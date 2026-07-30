"""Generate embeddings for the durable PostgreSQL embedding queue."""

from __future__ import annotations

import argparse
import os
import time
import uuid
from typing import Any

import numpy as np
from sqlalchemy import create_engine, text

from app2.config.constants import EMBEDDING_DIMENSION
from app2.embedding.embedding_service import get_embedding_service
from app2.ingestion import build_product_rag_text, product_content_hash

CLAIM_SQL = text(
    """
    WITH candidates AS (
        SELECT id
        FROM asanclipproducts
        WHERE (
              embedding_vector IS NULL
              OR embedding_model IS DISTINCT FROM :embedding_model
          )
          AND embedding_attempts < :max_attempts
          AND (
              embedding_status = 'pending'
              OR (
                  embedding_status = 'done'
                  AND embedding_model IS DISTINCT FROM :embedding_model
              )
              OR (:retry_errors AND embedding_status = 'error')
              OR (
                  embedding_status = 'processing'
                  AND embedding_claimed_at < now() - make_interval(mins => :stale_minutes)
              )
          )
        ORDER BY id
        FOR UPDATE SKIP LOCKED
        LIMIT :limit
    )
    UPDATE asanclipproducts AS product
    SET embedding_status = 'processing',
        embedding_claimed_at = now(),
        embedding_claim_token = :claim_token,
        embedding_attempts = product.embedding_attempts + 1,
        embedding_error = NULL
    FROM candidates
    WHERE product.id = candidates.id
    RETURNING
        product.id,
        product.name,
        product.short_description,
        product.description,
        product.product_type,
        product.occasion,
        product.platform,
        product.rag_text,
        product.content_hash,
        product.embedding_claim_token
    """
)

SUCCESS_SQL = text(
    """
    UPDATE asanclipproducts
    SET rag_text = :rag_text,
        content_hash = :new_content_hash,
        embedding_vector = CAST(:vector AS vector),
        embedding_model = :embedding_model,
        embedding_updated_at = now(),
        embedding_claimed_at = NULL,
        embedding_claim_token = NULL,
        embedding_attempts = 0,
        embedding_error = NULL,
        embedding_status = 'done',
        updated_at = now()
    WHERE id = :id
      AND content_hash IS NOT DISTINCT FROM :claimed_content_hash
      AND embedding_status = 'processing'
      AND embedding_claim_token = :claim_token
    """
)

FAILURE_SQL = text(
    """
    UPDATE asanclipproducts
    SET embedding_status = 'error',
        embedding_error = :error,
        embedding_claimed_at = NULL,
        embedding_claim_token = NULL,
        updated_at = now()
    WHERE id = :id
      AND content_hash IS NOT DISTINCT FROM :claimed_content_hash
      AND embedding_status = 'processing'
      AND embedding_claim_token = :claim_token
    """
)


def _claim_batch(
    engine: Any,
    *,
    limit: int,
    max_attempts: int,
    stale_minutes: int,
    retry_errors: bool,
    embedding_model: str,
) -> list[dict[str, Any]]:
    claim_token = str(uuid.uuid4())
    with engine.begin() as conn:
        return list(
            conn.execute(
                CLAIM_SQL,
                {
                    "limit": limit,
                    "max_attempts": max_attempts,
                    "stale_minutes": stale_minutes,
                    "retry_errors": retry_errors,
                    "embedding_model": embedding_model,
                    "claim_token": claim_token,
                },
            ).mappings()
        )


def generate_embeddings(
    database_url: str,
    *,
    batch_size: int = 50,
    max_products: int | None = None,
    max_attempts: int = 5,
    stale_minutes: int = 60,
    retry_errors: bool = False,
    delay_seconds: float = 0.0,
) -> dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    engine = create_engine(database_url, pool_pre_ping=True)
    embedder = get_embedding_service()
    model_name = getattr(embedder, "model", "unknown")
    stats = {
        "claimed": 0,
        "embedded": 0,
        "failed": 0,
        "superseded": 0,
        "remaining": 0,
    }

    while max_products is None or stats["claimed"] < max_products:
        remaining = batch_size
        if max_products is not None:
            remaining = min(remaining, max_products - stats["claimed"])
        rows = _claim_batch(
            engine,
            limit=remaining,
            max_attempts=max_attempts,
            stale_minutes=stale_minutes,
            retry_errors=retry_errors,
            embedding_model=model_name,
        )
        if not rows:
            break

        stats["claimed"] += len(rows)
        print(f"Claimed {len(rows)} products for embedding")

        for row in rows:
            product = dict(row)
            rag_text = build_product_rag_text(product)
            new_hash = product_content_hash(product)
            claimed_hash = product.get("content_hash")
            claim_token = product["embedding_claim_token"]
            try:
                if not rag_text:
                    raise ValueError("Product has no searchable text")
                vector = np.asarray(embedder.embed(rag_text), dtype=np.float32)
                if vector.ndim != 1 or vector.shape[0] != EMBEDDING_DIMENSION:
                    raise ValueError(
                        "Embedding dimension mismatch: "
                        f"got {vector.shape}, expected ({EMBEDDING_DIMENSION},)"
                    )
                if not np.isfinite(vector).all():
                    raise ValueError("Embedding contains NaN or infinite values")

                with engine.begin() as conn:
                    result = conn.execute(
                        SUCCESS_SQL,
                        {
                            "id": product["id"],
                            "rag_text": rag_text,
                            "new_content_hash": new_hash,
                            "claimed_content_hash": claimed_hash,
                            "vector": vector.tolist(),
                            "embedding_model": model_name,
                            "claim_token": claim_token,
                        },
                    )
                if result.rowcount == 1:
                    stats["embedded"] += 1
                else:
                    stats["superseded"] += 1
                    print(f"Skipped id={product['id']}; product changed while embedding")
            except Exception as exc:
                with engine.begin() as conn:
                    result = conn.execute(
                        FAILURE_SQL,
                        {
                            "id": product["id"],
                            "claimed_content_hash": claimed_hash,
                            "error": str(exc)[:2000],
                            "claim_token": claim_token,
                        },
                    )
                if result.rowcount == 1:
                    stats["failed"] += 1
                    print(f"Embedding failed id={product['id']}: {exc}")
                else:
                    stats["superseded"] += 1

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        print(f"Embedding progress: {stats}")

    with engine.connect() as conn:
        stats["remaining"] = int(
            conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM asanclipproducts
                    WHERE embedding_vector IS NULL
                       OR embedding_model IS DISTINCT FROM :embedding_model
                    """
                ),
                {"embedding_model": model_name},
            ).scalar_one()
        )
    engine.dispose()
    print(f"Embedding job complete: {stats}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--stale-minutes", type=int, default=60)
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    stats = generate_embeddings(
        database_url,
        batch_size=args.batch_size,
        max_products=args.max_products,
        max_attempts=args.max_attempts,
        stale_minutes=args.stale_minutes,
        retry_errors=args.retry_errors,
        delay_seconds=args.delay_seconds,
    )
    if stats["failed"] or stats["remaining"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()