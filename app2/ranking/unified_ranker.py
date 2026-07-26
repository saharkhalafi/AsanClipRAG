from typing import Any

from app2.ranking.score_normalizer import ScoreNormalizer


class UnifiedRanker:

    def __init__(self):
        self.norm = ScoreNormalizer()

    def rank(
        self,
        results: list[dict[str, Any]],
        query_signals: dict[str, Any]
    ) -> list[dict[str, Any]]:

        ranked = []

        for r in results:

            vector_score = self.norm.normalize_vector(r.get("distance", 1.0))

            lexical_score = r.get("lexical_score", 0.0)

            metadata_score = r.get("metadata_boost", 0.0)

            # 🔥 CRITICAL: query-product overlap boost
            query_tokens = set(query_signals.get("tokens", []))
            name_tokens = set((r.get("name") or "").split())

            overlap = len(query_tokens & name_tokens) / max(len(query_tokens), 1)

            # FINAL SCORE (REAL PRODUCTION STYLE)
            final_score = (
                0.45 * vector_score +
                0.25 * lexical_score +
                0.20 * metadata_score +
                0.10 * overlap
            )

            r["vector_score"] = vector_score
            r["lexical_score"] = lexical_score
            r["overlap_score"] = overlap
            r["final_score"] = final_score

            ranked.append(r)

        return sorted(ranked, key=lambda x: x["final_score"], reverse=True)
