from sqlalchemy import text


class MetadataLoader:

    def __init__(self, db):
        self.db = db

    def _load_distinct(self, column: str):
        rows = self.db.execute(
            text(f"""
                SELECT DISTINCT {column}
                FROM asanclipproducts
                WHERE {column} IS NOT NULL
                  AND TRIM({column}) <> ''
            """)
        ).fetchall()

        return [
            r[0].strip()
            for r in rows
            if r and r[0]
        ]

    def load(self):
        return {
            "product_types": self._load_distinct("product_type"),
            "occasions": self._load_distinct("occasion"),
            "platforms": self._load_distinct("platform"),
            "product_names": self._load_distinct("name"),
        }
