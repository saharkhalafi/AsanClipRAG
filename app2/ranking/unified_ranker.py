import re
from typing import Any

from app2.ranking.score_normalizer import ScoreNormalizer


class UnifiedRanker:

    def __init__(self):
        self.norm = ScoreNormalizer()

    @staticmethod
    def _query_tokens(tokens: list[str]) -> set[str]:
        expanded: set[str] = set()
        for token in tokens:
            token = token.strip().lower()
            if len(token) >= 3 and not token.isdigit():
                expanded.add(token)
        return expanded

    @staticmethod
    def _name_tokens(name: str) -> set[str]:
        if not name:
            return set()
        return {
            t for t in re.findall(r"[\w\u0600-\u06FF]+", name.lower())
            if len(t) >= 2
        }

    def rank(
        self,
        results: list[dict[str, Any]],
        query_signals: dict[str, Any]
    ) -> list[dict[str, Any]]:

        max_bm25 = max((float(r.get("bm25_score", 0.0)) for r in results), default=0.0) or 1.0
        query_tokens = self._query_tokens(query_signals.get("tokens", []))
        ranked = []

        for r in results:

            vector_score = self.norm.normalize_vector(r.get("distance", 1.0))

            lexical_score = float(r.get("lexical_score", 0.0))
            if lexical_score <= 0.0 and r.get("bm25_score") is not None:
                lexical_score = min(1.0, float(r["bm25_score"]) / max_bm25)

            metadata_score = float(r.get("metadata_boost", 0.0))

            name_tokens = self._name_tokens(r.get("name") or "")
            blob_tokens = name_tokens | self._name_tokens(
                " ".join(
                    str(r.get(field) or "")
                    for field in ("rag_text", "occasion", "product_type", "platform")
                )
            )

            overlap = len(query_tokens & blob_tokens) / max(len(query_tokens), 1)

            final_score = (
                0.40 * vector_score +
                0.30 * lexical_score +
                0.20 * metadata_score +
                0.10 * overlap
            )

            r["vector_score"] = vector_score
            r["lexical_score"] = lexical_score
            r["overlap_score"] = overlap
            r["final_score"] = final_score

            ranked.append(r)

        return sorted(ranked, key=lambda x: x["final_score"], reverse=True)
