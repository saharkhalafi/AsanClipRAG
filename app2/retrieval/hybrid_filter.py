from typing import Any, Dict


class HybridFilterBuilder:

    def build_sql_filters(
        self,
        filters: Dict[str, Any]
    ):

        where_clauses = []
        params = {}

        # ------------------------------------------------
        # HARD FILTER
        # ------------------------------------------------
        if filters.get("platform"):
            where_clauses.append(
                "platform = :platform"
            )
            params["platform"] = filters["platform"]

        # ------------------------------------------------
        # SEMI-STRICT OCCASION
        # ------------------------------------------------
        if filters.get("occasion"):

            occasions = filters["occasion"]

            if not isinstance(occasions, list):
                occasions = [occasions]

            conditions = []

            for i, value in enumerate(occasions):

                key = f"occasion_{i}"

                conditions.append(f"""
                (
                    occasion ILIKE :{key}
                    OR name ILIKE :{key}
                    OR rag_text ILIKE :{key}
                )
                """)

                params[key] = f"%{value}%"

            where_clauses.append(
                "(" + " OR ".join(conditions) + ")"
            )

        # ------------------------------------------------
        # PRODUCT TYPE
        # ------------------------------------------------
        if filters.get("product_type"):

            pts = filters["product_type"]

            if not isinstance(pts, list):
                pts = [pts]

            conditions = []

            for i, value in enumerate(pts):

                key = f"pt_{i}"

                conditions.append(f"""
                (
                    product_type ILIKE :{key}
                    OR name ILIKE :{key}
                    OR rag_text ILIKE :{key}
                )
                """)

                params[key] = f"%{value}%"

            where_clauses.append(
                "(" + " OR ".join(conditions) + ")"
            )

        return (
            " AND ".join(where_clauses),
            params
        )
