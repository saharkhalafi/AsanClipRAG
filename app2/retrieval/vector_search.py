# app2/retrieval/vector_search.py
from sqlalchemy import text
from typing import List, Dict, Any, Optional
import numpy as np

from app2.retrieval.faiss_index import FaissIndex
from app2.exceptions import DatabaseError, ValidationError   # ← جدید

class VectorSearchService:

    def __init__(self, db_session):
        self.db = db_session
        self.faiss = FaissIndex(dimension=768)
        self.use_faiss = True

    # =====================================================
    # VECTOR SEARCH (PRODUCTION READY)
    # =====================================================
    def search(
        self,
        query_vector: Optional[np.ndarray],
        limit: int = 150,
        where_clause: str = "",
        params: Optional[Dict[str, Any]] = None,
        candidate_ids: Optional[List[int]] = None,
        mode: str = "vector",
    ) -> List[Dict[str, Any]]:

        if query_vector is None:
            return []

        try:
            query_vector = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)
        except Exception as e:
            raise ValidationError("Invalid query vector") from e   # ← تغییر

        params = dict(params or {})

        # -----------------------------
        # 1. FAISS SEARCH
        # -----------------------------
        if self.use_faiss and self.faiss.index is not None:
            try:
                results = self.faiss.search(query_vector[0], k=limit * 2)
                if candidate_ids:
                    results = [r for r in results if r[0] in candidate_ids]
                return self._format_results(results, mode)
            except Exception as e:
                # fallback به PGVector
                pass

        # -----------------------------
        # 2. FALLBACK: PGVector
        # -----------------------------
        base_where = [
            "tag_status = 'done'",
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
                embedding_vector <-> CAST(:query_vector AS vector) AS distance
            FROM asanclipproducts
            WHERE {final_where}
            ORDER BY embedding_vector <-> CAST(:query_vector AS vector)
            LIMIT :limit
        """)

        params["query_vector"] = query_vector[0].tolist()
        params["limit"] = limit

        try:
            rows = self.db.execute(sql, params).fetchall()
        except Exception as e:
            raise DatabaseError("Vector search query failed") from e   # ← تغییر

        if not rows:
            return []

        results = []
        for r in rows:
            row = r._mapping
            distance = float(row.get("distance") or 1.0)
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

    def _format_results(self, faiss_results: List[tuple], mode: str) -> List[Dict]:
        if not faiss_results:
            return []

        results = []
        for product_id, similarity in faiss_results:
            results.append({
                "id": product_id,
                "vector_score": float(similarity),
                "source": "vector",
                "mode": mode,
            })
        return results