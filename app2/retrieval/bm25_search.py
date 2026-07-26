from typing import Any, Dict, List, Optional

from app2.retrieval.hybrid_filter import HybridFilterBuilder
from sqlalchemy import text


class BM25SearchService:
    """
    BM25 / full-text search as a secondary signal.

    Rules:
    - vector remains primary
    - BM25 is used only when orchestrator decides it is useful
    - filters are shared with other retrieval layers
    """

    def __init__(self, db_session):
        self.db = db_session
        self.filter_builder = HybridFilterBuilder()

    def search(
        self,
        query: str,
        limit: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        candidate_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:

        filters = filters or {}

        # shared SQL filters
        where_clause, filter_params = self.filter_builder.build_sql_filters(filters)

        params: Dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        params.update(filter_params)

        where_parts = ["tag_status = 'done'"]

        if where_clause:
            where_parts.append(f"({where_clause})")

        if candidate_ids:
            where_parts.append("id = ANY(:candidate_ids)")
            params["candidate_ids"] = candidate_ids

        # Full-text search over the most important text columns.
        # 'simple' is safer for mixed Persian/English content than language-specific configs.
        sql = text(f"""
            SELECT
                id,
                name,
                short_description,
                description,
                product_type,
                occasion,
                platform,
                rag_text,
                ts_rank_cd(
                    to_tsvector(
                        'simple',
                        COALESCE(name, '') || ' ' ||
                        COALESCE(short_description, '') || ' ' ||
                        COALESCE(description, '') || ' ' ||
                        COALESCE(rag_text, '')
                    ),
                    plainto_tsquery('simple', :query)
                ) AS bm25_score
            FROM asanclipproducts
            WHERE
                {" AND ".join(where_parts)}
                AND to_tsvector(
                    'simple',
                    COALESCE(name, '') || ' ' ||
                    COALESCE(short_description, '') || ' ' ||
                    COALESCE(description, '') || ' ' ||
                    COALESCE(rag_text, '')
                ) @@ plainto_tsquery('simple', :query)
            ORDER BY bm25_score DESC
            LIMIT :limit
        """)

        rows = self.db.execute(sql, params).fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            results.append({
                "id": r._mapping["id"],
                "name": r._mapping["name"],
                "short_description": r._mapping["short_description"],
                "description": r._mapping["description"],
                "rag_text": r._mapping["rag_text"],
                "product_type": r._mapping["product_type"],
                "occasion": r._mapping["occasion"],
                "platform": r._mapping["platform"],
                "bm25_score": float(r._mapping["bm25_score"] or 0.0),
                "source": "bm25",
            })

        return results
