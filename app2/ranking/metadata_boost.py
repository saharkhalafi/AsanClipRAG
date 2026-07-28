# app2/ranking/metadata_boost.py

from typing import Any


class MetadataBooster:

    def __init__(
        self,
        product_types=None,
        occasions=None,
        platforms=None
    ):
        self.product_types = set(product_types or [])
        self.occasions = set(occasions or [])
        self.platforms = set(platforms or [])

    @staticmethod
    def _field_matches(filter_val: str, row_val: str) -> bool:
        if not filter_val or not row_val:
            return False
        f = str(filter_val).strip().lower()
        r = str(row_val).strip().lower()
        if f == r:
            return True
        return f in r or r in f

    def boost(
        self,
        results: list[dict[str, Any]],
        filters: dict[str, Any],
        query: str = ""
    ) -> list[dict[str, Any]]:

        boosted = []
        query_lower = (query or "").lower()

        for r in results:

            base_score = self._get_base_score(r)
            bonus = self._compute_bonus(r, filters, query_lower)

            r["final_score"] = base_score + bonus
            r["metadata_boost"] = bonus

            boosted.append(r)

        boosted.sort(key=lambda x: x["final_score"], reverse=True)

        return boosted

    def _get_base_score(self, r: dict[str, Any]) -> float:

        if r.get("vector_score") is not None:
            return float(r["vector_score"])

        if r.get("distance") is not None:
            return max(0.0, 1.0 - float(r["distance"]))

        if r.get("bm25_score") is not None:
            return min(0.85, float(r["bm25_score"]))

        if r.get("source") in {"bm25", "lexical"}:
            return 0.25

        return 0.0

    def _compute_bonus(
        self,
        r: dict[str, Any],
        filters: dict[str, Any],
        query: str
    ) -> float:

        bonus = 0.0

        if filters.get("product_type") and r.get("product_type"):
            if self._field_matches(filters["product_type"], r["product_type"]):
                bonus += 0.15

        if filters.get("occasion") and r.get("occasion"):
            if self._field_matches(filters["occasion"], r["occasion"]):
                bonus += 0.18

        if filters.get("platform") and r.get("platform"):
            if self._field_matches(filters["platform"], r["platform"]):
                bonus += 0.10

        name_value = str(r.get("name") or "").lower().strip()
        if name_value and name_value in query:
            bonus += 0.05

        return bonus
