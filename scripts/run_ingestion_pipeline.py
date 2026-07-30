"""Run ingestion, embedding, and FAISS publication under one database lock."""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, text

from scripts.build_faiss_index import build_faiss_index
from scripts.generate_embeddings import generate_embeddings
from scripts.ingest_products import ingest_csv

PIPELINE_LOCK_NAME = "asanclip:ingestion-pipeline"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional CSV path; omit to process rows changed directly in PostgreSQL",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--embedding-batch-size", type=int, default=50)
    parser.add_argument("--min-vectors", type=int, default=100)
    parser.add_argument("--retry-errors", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    lock_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )
    with lock_engine.connect() as lock_connection:
        acquired = bool(
            lock_connection.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:name))"),
                {"name": PIPELINE_LOCK_NAME},
            ).scalar_one()
        )
        if not acquired:
            raise RuntimeError("Another ingestion pipeline is already running")

        try:
            if args.csv:
                print(f"Pipeline {args.run_id}: ingestion started")
                ingest_csv(
                    args.csv,
                    database_url,
                    chunk_size=args.chunk_size,
                    run_id=args.run_id,
                )
            else:
                print(f"Pipeline {args.run_id}: no CSV supplied; ingestion skipped")

            print(f"Pipeline {args.run_id}: embedding started")
            embedding_stats = generate_embeddings(
                database_url,
                batch_size=args.embedding_batch_size,
                retry_errors=args.retry_errors,
            )
            if embedding_stats["failed"] or embedding_stats["remaining"]:
                raise RuntimeError(f"Embedding queue is not clean: {embedding_stats}")

            print(f"Pipeline {args.run_id}: FAISS build started")
            build_faiss_index(
                database_url,
                args.output,
                min_vectors=args.min_vectors,
                expected_model=os.getenv("EMBEDDING_MODEL"),
            )
            print(f"Pipeline {args.run_id}: completed successfully")
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:name))"),
                {"name": PIPELINE_LOCK_NAME},
            )
    lock_engine.dispose()


if __name__ == "__main__":
    main()
