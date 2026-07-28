import time

from sqlalchemy import text

from app2.config.constants import METADATA_CACHE_TTL_SECONDS


class MetadataLoader:
    _cache: dict | None = None
    _cache_ts: float = 0.0

    def __init__(self, db):
        self.db = db

    @classmethod
    def _cache_valid(cls) -> bool:
        if cls._cache is None:
            return False
        return (time.time() - cls._cache_ts) < METADATA_CACHE_TTL_SECONDS

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._cache = None
        cls._cache_ts = 0.0

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
        if self._cache_valid():
            return self._cache

        meta = {
            "product_types": self._load_distinct("product_type"),
            "occasions": self._load_distinct("occasion"),
            "platforms": self._load_distinct("platform"),
            "product_names": self._load_distinct("name"),
        }

        MetadataLoader._cache = meta
        MetadataLoader._cache_ts = time.time()
        return meta
