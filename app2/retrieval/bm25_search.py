import re
from typing import Any

from app2.retrieval.hybrid_filter import HybridFilterBuilder
from app2.utils.query_synonyms import expand_query, normalize_variants
from sqlalchemy import text


class BM25SearchService:
    """
    BM25 / full-text search with Persian-friendly ILIKE fallback.
    """

    def __init__(self, db_session):
        self.db = db_session
        self.filter_builder = HybridFilterBuilder()

    @staticmethod
    def _extract_tokens(query: str) -> list[str]:
        tokens = re.findall(r"[\w\u0600-\u06FF]+", query.lower())
        return [t for t in tokens if len(t) >= 3 and not t.isdigit()]

    def search(
        self,
        query: str,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
        candidate_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:

        query = expand_query(normalize_variants(query))
        filters = filters or {}

        where_clause, filter_params = self.filter_builder.build_sql_filters(filters)

        params: dict[str, Any] = {
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

        if not rows:
            rows = self._ilike_fallback(query, where_parts, params, limit)

        results: list[dict[str, Any]] = []
        for r in rows:
            mapping = r._mapping
            results.append({
                "id": mapping["id"],
                "name": mapping["name"],
                "short_description": mapping.get("short_description"),
                "description": mapping.get("description"),
                "rag_text": mapping.get("rag_text"),
                "product_type": mapping.get("product_type"),
                "occasion": mapping.get("occasion"),
                "platform": mapping.get("platform"),
                "bm25_score": float(mapping.get("bm25_score") or 0.0),
                "source": "bm25",
            })

        return results

    def _ilike_fallback(
        self,
        query: str,
        where_parts: list[str],
        params: dict[str, Any],
        limit: int,
    ):
        tokens = self._extract_tokens(query)[:8]
        if not tokens:
            return []

        score_terms: list[str] = []
        where_terms: list[str] = []

        for i, token in enumerate(tokens):
            key = f"tok_{i}"
            params[key] = f"%{token}%"
            score_terms.append(f"""
                CASE
                    WHEN COALESCE(name, '') ILIKE :{key} THEN 2.0
                    WHEN COALESCE(rag_text, '') ILIKE :{key} THEN 1.6
                    WHEN COALESCE(occasion, '') ILIKE :{key} THEN 1.4
                    WHEN COALESCE(product_type, '') ILIKE :{key} THEN 1.1
                    ELSE 0
                END
            """)
            where_terms.append(f"""
                (
                    COALESCE(name, '') ILIKE :{key}
                    OR COALESCE(rag_text, '') ILIKE :{key}
                    OR COALESCE(occasion, '') ILIKE :{key}
                    OR COALESCE(product_type, '') ILIKE :{key}
                    OR COALESCE(platform, '') ILIKE :{key}
                )
            """)

        score_sql = " + ".join(score_terms)
        where_sql = " OR ".join(where_terms)

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
                ({score_sql}) AS bm25_score
            FROM asanclipproducts
            WHERE {" AND ".join(where_parts)}
              AND ({where_sql})
            ORDER BY bm25_score DESC
            LIMIT :limit
        """)

        return self.db.execute(sql, params).fetchall()
