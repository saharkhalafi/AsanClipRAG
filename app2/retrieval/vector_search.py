# app2/retrieval/vector_search.py
import logging
from typing import Any

import numpy as np
from app2.config.constants import EMBEDDING_DIMENSION
from app2.exceptions import DatabaseError, ValidationError
from app2.retrieval.faiss_index import get_faiss_index
from sqlalchemy import text

logger = logging.getLogger("app2.retrieval.vector")


class VectorSearchService:

    def __init__(self, db_session):
        self.db = db_session
        self.faiss = get_faiss_index(dimension=EMBEDDING_DIMENSION)
        self.use_faiss = True
        if self.faiss.index is not None:
            logger.debug(
                "Using FAISS index with %d vectors (dim=%d)",
                self.faiss.index.ntotal,
                EMBEDDING_DIMENSION,
            )
        else:
            logger.warning("FAISS index unavailable — falling back to pgvector")

    # =====================================================
    # VECTOR SEARCH (PRODUCTION READY)
    # =====================================================
    def search(
        self,
        query_vector: np.ndarray | None,
        limit: int = 150,
        where_clause: str = "",
        params: dict[str, Any] | None = None,
        candidate_ids: list[int] | None = None,
        mode: str = "vector",
    ) -> list[dict[str, Any]]:

        if query_vector is None:
            return []

        try:
            query_vector = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
        except Exception as e:
            raise ValidationError("Invalid query vector") from e

        params = dict(params or {})

        # -----------------------------
        # 1. FAISS SEARCH
        # -----------------------------
        if self.use_faiss and self.faiss.index is not None and not where_clause.strip():
            try:
                if candidate_ids:
                    k = min(500, max(limit * 4, len(candidate_ids) * 3))
                else:
                    k = min(500, limit * 3)
                results = self.faiss.search(query_vector[0], k=k)
                if candidate_ids:
                    candidate_set = set(candidate_ids)
                    results = [r for r in results if r[0] in candidate_set]
                hydrated = self._hydrate_faiss_results(results, mode, limit)
                if hydrated:
                    return hydrated
                logger.warning("FAISS returned no usable rows; using pgvector fallback")
            except Exception as exc:
                logger.warning("FAISS search failed, using pgvector: %s", exc)

        # -----------------------------
        # 2. FALLBACK: PGVector
        # -----------------------------
        base_where = [
            "tag_status = 'done'",
            "embedding_status = 'done'",
            "embedding_vector IS NOT NULL"
        ]

        if candidate_ids and len(candidate_ids) > 0:
            base_where.append("id = ANY(:candidate_ids)")
            params["candidate_ids"] = candidate_ids

        if where_clause and where_clause.strip():
            base_where.append(f"({where_clause})")

        final_where = " AND ".join(base_where)

        sql = text(f"""
            SELECT
                id,
                name,
                short_description,
                description,
                rag_text,
                product_type,
                occasion,
                platform,
                CAST(embedding_vector AS halfvec(3072))
                    <=> CAST(:query_vector AS halfvec(3072)) AS distance
            FROM asanclipproducts
            WHERE {final_where}
            ORDER BY CAST(embedding_vector AS halfvec(3072))
                <=> CAST(:query_vector AS halfvec(3072))
            LIMIT :limit
        """)

        params["query_vector"] = query_vector[0].tolist()
        params["limit"] = limit

        try:
            rows = self.db.execute(sql, params).fetchall()
        except Exception as e:
            raise DatabaseError("Vector search query failed") from e

        if not rows:
            return []

        results = []
        for r in rows:
            row = r._mapping
            raw_distance = row.get("distance")
            distance = 1.0 if raw_distance is None else float(raw_distance)
            vector_score = max(0.0, 1.0 - distance)

            results.append({
                "id": row["id"],
                "name": row["name"],
                "short_description": row.get("short_description"),
                "description": row.get("description"),
                "rag_text": row.get("rag_text"),
                "product_type": row.get("product_type"),
                "occasion": row.get("occasion"),
                "platform": row.get("platform"),
                "distance": distance,
                "vector_score": vector_score,
                "source": "vector",
                "mode": mode,
            })

        return results

    def _hydrate_faiss_results(
        self,
        faiss_results: list[tuple[int, float]],
        mode: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Batch-load product rows for FAISS hits (preserves FAISS ranking)."""
        if not faiss_results:
            return []

        score_map = {pid: float(sim) for pid, sim in faiss_results}
        ids = list(score_map.keys())

        sql = text("""
            SELECT
                id,
                name,
                short_description,
                description,
                rag_text,
                product_type,
                occasion,
                platform
            FROM asanclipproducts
            WHERE id = ANY(:ids)
              AND tag_status = 'done'
              AND embedding_status = 'done'
        """)

        try:
            rows = self.db.execute(sql, {"ids": ids}).fetchall()
        except Exception as e:
            raise DatabaseError("FAISS hydration query failed") from e

        row_map = {row._mapping["id"]: row._mapping for row in rows}

        results: list[dict[str, Any]] = []
        for product_id, similarity in faiss_results:
            row = row_map.get(product_id)
            if row is None:
                continue

            distance = max(0.0, 1.0 - similarity)
            results.append({
                "id": row["id"],
                "name": row["name"],
                "short_description": row.get("short_description"),
                "description": row.get("description"),
                "rag_text": row.get("rag_text"),
                "product_type": row.get("product_type"),
                "occasion": row.get("occasion"),
                "platform": row.get("platform"),
                "distance": distance,
                "vector_score": similarity,
                "source": "vector",
                "mode": mode,
            })
            if len(results) >= limit:
                break

        return results
