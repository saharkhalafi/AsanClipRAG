"""Build an API-compatible FAISS index from a consistent PostgreSQL snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy import create_engine, text

from app2.config.constants import EMBEDDING_DIMENSION, FAISS_INDEX_PATH
from app2.retrieval.faiss_index import FaissIndex

SELECT_SQL = text(
    """
    SELECT id, embedding_vector, embedding_model, updated_at
    FROM asanclipproducts
    WHERE embedding_vector IS NOT NULL
      AND tag_status = 'done'
      AND embedding_status = 'done'
    ORDER BY id
    """
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_snapshot(database_url: str, dimension: int) -> tuple[np.ndarray, list[int], dict[str, Any]]:
    engine = create_engine(database_url, pool_pre_ping=True)
    ids: list[int] = []
    vectors: list[np.ndarray] = []
    models: set[str] = set()
    missing_model_count = 0
    latest_update: datetime | None = None

    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('asanclip:faiss-build'))"))
            for row in conn.execute(SELECT_SQL):
                vector = np.asarray(row.embedding_vector, dtype=np.float32)
                if vector.ndim != 1 or vector.shape[0] != dimension:
                    raise ValueError(
                        f"Product id={row.id} has embedding shape {vector.shape}; "
                        f"expected ({dimension},)"
                    )
                if not np.isfinite(vector).all():
                    raise ValueError(f"Product id={row.id} has a non-finite embedding")
                ids.append(int(row.id))
                vectors.append(vector)
                if row.embedding_model:
                    models.add(str(row.embedding_model))
                else:
                    missing_model_count += 1
                if row.updated_at and (latest_update is None or row.updated_at > latest_update):
                    latest_update = row.updated_at

    engine.dispose()
    if not vectors:
        raise RuntimeError("No completed product embeddings are available")
    if len(models) > 1 or (models and missing_model_count):
        raise RuntimeError(
            "FAISS source contains mixed embedding models; run the embedding job to completion"
        )
    matrix = np.vstack(vectors).astype(np.float32, copy=False)
    metadata = {
        "embedding_models": sorted(models),
        "missing_embedding_model_count": missing_model_count,
        "source_latest_updated_at": latest_update.isoformat() if latest_update else None,
    }
    return matrix, ids, metadata


def build_faiss_index(
    database_url: str,
    output_path: str,
    *,
    dimension: int = EMBEDDING_DIMENSION,
    min_vectors: int = 1,
    expected_model: str | None = None,
) -> dict[str, Any]:
    if min_vectors < 1:
        raise ValueError("min_vectors must be at least 1")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    vectors, ids, source_metadata = _load_snapshot(database_url, dimension)
    if expected_model and source_metadata["embedding_models"] != [expected_model]:
        raise RuntimeError(
            "FAISS source model mismatch: "
            f"got {source_metadata['embedding_models']}, expected {[expected_model]}"
        )
    if len(ids) < min_vectors:
        raise RuntimeError(f"Only {len(ids)} vectors found; minimum required is {min_vectors}")
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate product IDs found in FAISS source query")

    with tempfile.TemporaryDirectory(prefix="asanclip-faiss-") as temp_dir:
        temp_index = Path(temp_dir) / output.name
        FaissIndex(dimension=dimension, index_path=str(temp_index)).build_index(vectors, ids)
        temp_map = temp_index.with_suffix(".pkl")

        final_map = output.with_suffix(".pkl")
        shutil.copy2(temp_map, final_map)
        shutil.copy2(temp_index, output)

    manifest = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_path": output.name,
        "mapping_path": output.with_suffix(".pkl").name,
        "vector_count": len(ids),
        "dimension": dimension,
        "index_sha256": _sha256(output),
        "mapping_sha256": _sha256(output.with_suffix(".pkl")),
        "min_product_id": min(ids),
        "max_product_id": max(ids),
        **source_metadata,
    }
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Verify that the exact files consumed by the API can be loaded.
    verification = FaissIndex(dimension=dimension, index_path=str(output))
    verification.load_index()
    if verification.index is None or int(verification.index.ntotal) != len(ids):
        raise RuntimeError("FAISS artifact verification failed")

    print(f"FAISS build complete: {json.dumps(manifest, ensure_ascii=False)}")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=os.getenv("FAISS_OUT", FAISS_INDEX_PATH),
        help="Index path; the .pkl mapping and manifest are written beside it",
    )
    parser.add_argument("--dimension", type=int, default=EMBEDDING_DIMENSION)
    parser.add_argument("--min-vectors", type=int, default=1)
    parser.add_argument("--expected-model", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    build_faiss_index(
        database_url,
        args.output,
        dimension=args.dimension,
        min_vectors=args.min_vectors,
        expected_model=args.expected_model,
    )


if __name__ == "__main__":
    main()