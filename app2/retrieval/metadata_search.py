from typing import Any, Dict, List, Optional
import re

from sqlalchemy import text


class MetadataSearchService:

    def __init__(self, db_session):
        self.db = db_session

    # =====================================================
    # TOKEN EXTRACTION
    # =====================================================

    def _extract_tokens(self, query: str) -> List[str]:
        """
        Generic tokenization:
        - no hardcoded keywords
        - keeps only meaningful tokens
        - ignores very short tokens that are usually noise
        """
        if not query:
            return []

        raw_tokens = re.findall(r"[\w\u0600-\u06FF]+", query.lower())
        return [
            token.strip()
            for token in raw_tokens
            if len(token.strip()) >= 3 and not token.isdigit()
        ]

    def _token_weight(self, token: str) -> float:
        """
        Longer tokens are usually more informative.
        This is generic, not hardcoded to any keyword list.
        """
        length = len(token)
        if length >= 10:
            return 1.00
        if length >= 8:
            return 0.90
        if length >= 6:
            return 0.75
        if length >= 4:
            return 0.55
        return 0.35

    # =====================================================
    # MAIN SEARCH
    # =====================================================

    def search(
        self,
        filters: Dict[str, Any],
        query: str,
        semantic: Optional[Dict[str, Any]] = None,
        limit: int = 500,
    ) -> List[int]:

        semantic = semantic or {}
        semantic_matches = semantic.get("matches", {}) or {}
        tokens = self._extract_tokens(query)

        # -------------------------------------------------
        # If there is truly no signal, use fallback
        # -------------------------------------------------
        if not tokens and not semantic_matches:
            return self._fallback_name_search(query=query, limit=limit)

        params: Dict[str, Any] = {
            "limit": limit
        }

        score_terms: List[str] = []
        where_terms: List[str] = []

        # =====================================================
        # 1. QUERY TOKEN SCORING
        # =====================================================
        # We score every row based on how much of the query text
        # appears in name / rag_text / metadata fields.
        #
        # This is what makes:
        #   ولنتاین + اینستاگرام
        # rank above
        #   فقط اینستاگرام
        #
        # without any hardcoded keyword dictionary.
        # =====================================================

        for i, token in enumerate(tokens[:8]):
            key = f"tok_{i}"
            params[key] = f"%{token}%"
            token_weight = self._token_weight(token)

            score_terms.append(f"""
                CASE
                    WHEN COALESCE(name, '') ILIKE :{key} THEN {1.80 * token_weight:.3f}
                    WHEN COALESCE(rag_text, '') ILIKE :{key} THEN {1.45 * token_weight:.3f}
                    WHEN COALESCE(occasion, '') ILIKE :{key} THEN {1.30 * token_weight:.3f}
                    WHEN COALESCE(product_type, '') ILIKE :{key} THEN {1.05 * token_weight:.3f}
                    WHEN COALESCE(platform, '') ILIKE :{key} THEN {0.75 * token_weight:.3f}
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

        # =====================================================
        # 2. SEMANTIC MATCH BOOSTS
        # =====================================================
        # These are not hardcoded keywords.
        # They are generic field weights for DB-driven fields.
        # =====================================================

        semantic_specs = [
            ("occasions", "occasion", 2.80),
            ("product_types", "product_type", 1.90),
            ("product_names", "name", 1.35),
            ("platforms", "platform", 0.85),
        ]

        for i, (semantic_key, column_name, base_weight) in enumerate(semantic_specs):
            match = semantic_matches.get(semantic_key)
            if not match:
                continue

            value = match.get("value")
            if not value:
                continue

            key = f"sem_{i}"
            params[key] = f"%{value}%"

            score_terms.append(f"""
                CASE
                    WHEN COALESCE({column_name}, '') ILIKE :{key} THEN {base_weight:.3f}
                    WHEN COALESCE(name, '') ILIKE :{key} THEN {(base_weight * 0.60):.3f}
                    WHEN COALESCE(rag_text, '') ILIKE :{key} THEN {(base_weight * 0.50):.3f}
                    ELSE 0
                END
            """)

            where_terms.append(f"""
                (
                    COALESCE({column_name}, '') ILIKE :{key}
                    OR COALESCE(name, '') ILIKE :{key}
                    OR COALESCE(rag_text, '') ILIKE :{key}
                )
            """)

        # =====================================================
        # 3. FILTERS (SAFE SECONDARY HINTS)
        # =====================================================
        # We do NOT force platform to dominate.
        # Filters are only used as secondary hints if present.
        # =====================================================

        filter_specs = [
            ("occasion", "occasion", 1.20),
            ("product_type", "product_type", 0.95),
            ("platform", "platform", 0.55),
        ]

        for i, (filter_key, column_name, base_weight) in enumerate(filter_specs):
            value = filters.get(filter_key)
            if not value:
                continue

            key = f"flt_{i}"
            params[key] = f"%{value}%"

            score_terms.append(f"""
                CASE
                    WHEN COALESCE({column_name}, '') ILIKE :{key} THEN {base_weight:.3f}
                    WHEN COALESCE(name, '') ILIKE :{key} THEN {(base_weight * 0.55):.3f}
                    WHEN COALESCE(rag_text, '') ILIKE :{key} THEN {(base_weight * 0.45):.3f}
                    ELSE 0
                END
            """)

            where_terms.append(f"""
                (
                    COALESCE({column_name}, '') ILIKE :{key}
                    OR COALESCE(name, '') ILIKE :{key}
                    OR COALESCE(rag_text, '') ILIKE :{key}
                )
            """)

        # =====================================================
        # 4. FINAL FALLBACK
        # =====================================================

        if not score_terms:
            return self._fallback_name_search(query=query, limit=limit)

        score_sql = " + ".join(score_terms)
        where_sql = " OR ".join(f"({x})" for x in where_terms) if where_terms else "TRUE"

        sql = text(f"""
            SELECT id
            FROM (
                SELECT
                    id,
                    ({score_sql}) AS relevance_score
                FROM asanclipproducts
                WHERE ({where_sql})
            ) scored
            ORDER BY relevance_score DESC, id DESC
            LIMIT :limit
        """)

        rows = self.db.execute(sql, params).fetchall()

        if not rows:
            return self._fallback_name_search(query=query, limit=limit)

        return [row._mapping["id"] for row in rows]

    # =====================================================
    # NAME/RAG FALLBACK
    # =====================================================

    def _fallback_name_search(self, query: str, limit: int) -> List[int]:
        tokens = self._extract_tokens(query)

        if not tokens:
            return []

        params: Dict[str, Any] = {
            "limit": limit
        }

        score_terms: List[str] = []
        where_terms: List[str] = []

        for i, token in enumerate(tokens[:8]):
            key = f"tok_{i}"
            params[key] = f"%{token}%"
            token_weight = self._token_weight(token)

            score_terms.append(f"""
                CASE
                    WHEN COALESCE(name, '') ILIKE :{key} THEN {1.80 * token_weight:.3f}
                    WHEN COALESCE(rag_text, '') ILIKE :{key} THEN {1.45 * token_weight:.3f}
                    ELSE 0
                END
            """)

            where_terms.append(f"""
                (
                    COALESCE(name, '') ILIKE :{key}
                    OR COALESCE(rag_text, '') ILIKE :{key}
                )
            """)

        sql = text(f"""
            SELECT id
            FROM (
                SELECT
                    id,
                    ({' + '.join(score_terms)}) AS relevance_score
                FROM asanclipproducts
                WHERE ({' OR '.join(where_terms)})
            ) scored
            ORDER BY relevance_score DESC, id DESC
            LIMIT :limit
        """)

        rows = self.db.execute(sql, params).fetchall()
        return [row._mapping["id"] for row in rows]