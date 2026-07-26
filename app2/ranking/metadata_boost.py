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

    # -------------------------------------------------
    # MAIN FUNCTION: re-rank results
    # -------------------------------------------------
    def boost(
        self,
        results: list[dict[str, Any]],
        filters: dict[str, Any],
        query: str = ""
    ) -> list[dict[str, Any]]:

        boosted = []

        for r in results:

            base_score = self._get_base_score(r)

            bonus = self._compute_bonus(r, filters, query)

            r["final_score"] = base_score + bonus
            r["metadata_boost"] = bonus

            boosted.append(r)

        # sort by final score
        boosted.sort(key=lambda x: x["final_score"], reverse=True)

        return boosted

    # -------------------------------------------------
    # base score from vector + lexical
    # -------------------------------------------------
    def _get_base_score(self, r: dict[str, Any]) -> float:

        # distance → similarity
        if r.get("distance") is not None:
            vector_score = 1 / (1 + r["distance"])
        else:
            vector_score = 0.0

        # lexical fallback gets small base
        if r.get("source") == "lexical":
            vector_score = max(vector_score, 0.2)

        return vector_score

    # -------------------------------------------------
    # metadata boost logic
    # -------------------------------------------------
    def _compute_bonus(
        self,
        r: dict[str, Any],
        filters: dict[str, Any],
        query: str
    ) -> float:

        bonus = 0.0

        # -------------------------
        # product_type match
        # -------------------------
        if filters.get("product_type") and r.get("product_type"):

            if r["product_type"] in filters["product_type"]:
                bonus += 0.15

        # -------------------------
        # occasion match
        # -------------------------
        if filters.get("occasion") and r.get("occasion"):

            if r["occasion"] in filters["occasion"]:
                bonus += 0.15

        # -------------------------
        # platform match
        # -------------------------
        if filters.get("platform") and r.get("platform"):

            if r["platform"] == filters["platform"]:
                bonus += 0.10

        # -------------------------
        # query heuristic boost (VERY useful for Persian)
        # -------------------------
        if r.get("name") and r["name"] in query:
            bonus += 0.05

        return bonus
