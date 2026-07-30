"""Idempotently ingest product CSV data into PostgreSQL.

Semantic changes invalidate the previous embedding and enqueue that product for
the embedding job. Unchanged rows do not receive unnecessary database writes.
"""

from __future__ import annotations

import argparse
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

from app2.ingestion import build_product_rag_text, product_content_hash

REQUIRED_COLUMNS = {"id", "name"}

UPSERT_SQL = text(
    """
    INSERT INTO asanclipproducts (
        id, name, short_description, description, rag_text,
        product_type, occasion, platform, tag_status, embedding_status, url,
        content_hash, ingestion_run_id, embedding_attempts
    ) VALUES (
        :id, :name, :short_description, :description, :rag_text,
        :product_type, :occasion, :platform, COALESCE(:tag_status, 'done'), 'pending', :url,
        :content_hash, :ingestion_run_id, 0
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        short_description = EXCLUDED.short_description,
        description = EXCLUDED.description,
        rag_text = EXCLUDED.rag_text,
        product_type = EXCLUDED.product_type,
        occasion = EXCLUDED.occasion,
        platform = EXCLUDED.platform,
        tag_status = CASE
            WHEN :tag_status_provided THEN EXCLUDED.tag_status
            ELSE asanclipproducts.tag_status
        END,
        url = EXCLUDED.url,
        content_hash = EXCLUDED.content_hash,
        ingestion_run_id = EXCLUDED.ingestion_run_id,
        updated_at = now()
    WHERE ROW(
        asanclipproducts.name,
        asanclipproducts.short_description,
        asanclipproducts.description,
        asanclipproducts.rag_text,
        asanclipproducts.product_type,
        asanclipproducts.occasion,
        asanclipproducts.platform,
        asanclipproducts.url,
        asanclipproducts.content_hash
    ) IS DISTINCT FROM ROW(
        EXCLUDED.name,
        EXCLUDED.short_description,
        EXCLUDED.description,
        EXCLUDED.rag_text,
        EXCLUDED.product_type,
        EXCLUDED.occasion,
        EXCLUDED.platform,
        EXCLUDED.url,
        EXCLUDED.content_hash
    )
    OR (
        :tag_status_provided
        AND asanclipproducts.tag_status IS DISTINCT FROM EXCLUDED.tag_status
    )
    RETURNING (xmax = 0) AS inserted
    """
)


def _clean(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    result = str(value).strip()
    return result or None


def clean_row(row: Mapping[str, Any], run_id: str) -> dict[str, Any]:
    try:
        product_id = int(row["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid product id: {row.get('id')!r}") from exc

    payload: dict[str, Any] = {
        "id": product_id,
        "name": _clean(row.get("name")),
        "short_description": _clean(row.get("short_description")),
        "description": _clean(row.get("description")),
        "product_type": _clean(row.get("product_type")),
        "occasion": _clean(row.get("occasion")),
        "platform": _clean(row.get("platform")),
        "tag_status": _clean(row.get("tag_status")),
        "tag_status_provided": "tag_status" in row and _clean(row.get("tag_status")) is not None,
        "url": _clean(row.get("url")),
        "ingestion_run_id": run_id,
    }
    if not payload["name"]:
        raise ValueError(f"Product id={product_id} has an empty name")

    payload["rag_text"] = build_product_rag_text(payload)
    payload["content_hash"] = product_content_hash(payload)
    return payload


def ingest_csv(
    csv_path: str,
    database_url: str,
    *,
    chunk_size: int = 500,
    run_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int | str]:
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    run_id = run_id or os.getenv("INGESTION_RUN_ID") or str(uuid.uuid4())
    engine = create_engine(database_url, pool_pre_ping=True)
    stats = {"read": 0, "inserted": 0, "updated": 0, "unchanged": 0}
    seen_ids: set[int] = set()

    for frame in pd.read_csv(path, chunksize=chunk_size):
        missing = REQUIRED_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        payloads: list[dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            payload = clean_row(row, run_id)
            if payload["id"] in seen_ids:
                raise ValueError(f"Duplicate product id in CSV: {payload['id']}")
            seen_ids.add(payload["id"])
            payloads.append(payload)
        stats["read"] += len(payloads)

        if dry_run:
            continue

        with engine.begin() as conn:
            for payload in payloads:
                result = conn.execute(UPSERT_SQL, payload).mappings().first()
                if result is None:
                    stats["unchanged"] += 1
                elif result["inserted"]:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1

        print(
            "Ingestion progress "
            f"read={stats['read']} inserted={stats['inserted']} "
            f"updated={stats['updated']} unchanged={stats['unchanged']}"
        )

    engine.dispose()
    result: dict[str, int | str] = {**stats, "run_id": run_id}
    print(f"Ingestion complete: {result}")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Local or mounted CSV path")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    ingest_csv(
        args.csv,
        database_url,
        chunk_size=args.chunk_size,
        run_id=args.run_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()