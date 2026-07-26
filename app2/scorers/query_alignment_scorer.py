# app2/scorers/query_alignment_scorer.py
import re
from typing import Any, Dict, List, Optional


class QueryAlignmentScorer:
    """مسئول محاسبه boost alignment بین query و نتایج"""

    @staticmethod
    def _extract_tokens(text: str) -> List[str]:
        if not text:
            return []
        tokens = re.findall(r"[\w\u0600-\u06FF]+", text.lower())
        return [t for t in tokens if len(t) >= 3 and not t.isdigit()]

    @staticmethod
    def _result_blob(item: Dict[str, Any]) -> str:
        parts = [
            item.get("name"),
            item.get("short_description"),
            item.get("description"),
            item.get("rag_text"),
            item.get("product_type"),
            item.get("occasion"),
            item.get("platform"),
        ]
        return " ".join(str(p or "") for p in parts).lower()

    @staticmethod
    def score(
        query: str,
        item: Dict[str, Any],
        semantic: Optional[Dict[str, Any]] = None
    ) -> float:
        """محاسبه alignment boost"""
        q_tokens = QueryAlignmentScorer._extract_tokens(query)
        if not q_tokens:
            return 0.0

        query_text = query.lower()
        blob = QueryAlignmentScorer._result_blob(item)

        hit_score = 0.0
        hit_count = 0

        for token in q_tokens:
            if token in blob:
                hit_count += 1
                if len(token) >= 10:
                    hit_score += 0.18
                elif len(token) >= 8:
                    hit_score += 0.15
                elif len(token) >= 6:
                    hit_score += 0.11
                elif len(token) >= 4:
                    hit_score += 0.07
                else:
                    hit_score += 0.04

        token_ratio = hit_count / max(len(q_tokens), 1)

        # Field bonus
        field_bonus = 0.0
        name_value = str(item.get("name") or "").lower().strip()
        occasion_value = str(item.get("occasion") or "").lower().strip()
        product_type_value = str(item.get("product_type") or "").lower().strip()
        platform_value = str(item.get("platform") or "").lower().strip()

        if name_value and name_value in query_text:
            field_bonus += 0.08
        if occasion_value and occasion_value in query_text:
            field_bonus += 0.20
        if product_type_value and product_type_value in query_text:
            field_bonus += 0.12
        if platform_value and platform_value in query_text:
            field_bonus += 0.05

        # Semantic bonus
        semantic_matches = (semantic or {}).get("matches", {}) or {}
        for field, bonus in [("occasions", 0.18), ("product_types", 0.10),
                           ("product_names", 0.08), ("platforms", 0.04)]:
            if field in semantic_matches:
                val = str(semantic_matches[field].get("value") or "").lower().strip()
                if val and val in blob:
                    field_bonus += bonus

        boost = (0.15 * token_ratio) + hit_score + field_bonus
        return float(min(0.35, boost))

    @staticmethod
    def apply_boost(
        results: List[Dict[str, Any]],
        query: str,
        semantic: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """اعمال boost به همه نتایج"""
        boosted = []
        for item in results:
            boost = QueryAlignmentScorer.score(query, item, semantic)
            new_item = dict(item)
            new_item["query_alignment_boost"] = round(boost, 6)
            base_score = float(new_item.get("final_score", new_item.get("vector_score", 0.0)))
            new_item["final_score"] = base_score + boost
            boosted.append(new_item)

        boosted.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        return boosted
