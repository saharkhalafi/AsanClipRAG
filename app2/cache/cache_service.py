# app2/cache/cache_service.py

import pickle
import hashlib
import logging
from typing import Any, Optional, Dict

import redis
from app2.core.settings import get_settings

logger = logging.getLogger("app2.cache")


class CacheService:
    def __init__(self):
        self.settings = get_settings()
        self.enabled: bool = self.settings.ENABLE_CACHE
        self.redis: Optional[redis.Redis] = None

        if self.enabled:
            try:
                self.redis = redis.from_url(
                    self.settings.REDIS_URL,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                    decode_responses=False
                )
                self.redis.ping()
                logger.info("✅ Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable, cache disabled: {e}")
                self.enabled = False
                self.redis = None

    def _make_key(self, prefix: str, identifier: str) -> str:
        qhash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:32]
        return f"{self.settings.CACHE_PREFIX}{prefix}:{qhash}"

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled or self.redis is None:
            return None

        try:
            data = self.redis.get(key)
            if isinstance(data, (bytes, bytearray)):
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if not self.enabled or self.redis is None:
            return

        try:
            data = pickle.dumps(value)
            ttl_value: int = ttl if ttl is not None else 3600
            self.redis.setex(key, ttl_value, data)
        except Exception as e:
            logger.debug(f"Cache set error: {e}")

    # ----------------------------
    # Query Result Cache
    # ----------------------------
    def get_search_result(self, raw_query: str, top_k: int = 20) -> Optional[Dict]:
        key = self._make_key("search", f"{raw_query}|k={top_k}")
        return self.get(key)

    def set_search_result(self, raw_query: str, result: Dict, top_k: int = 20) -> None:
        key = self._make_key("search", f"{raw_query}|k={top_k}")
        self.set(key, result, self.settings.REDIS_TTL_SEARCH)

    # ----------------------------
    # Embedding Cache
    # ----------------------------
    def get_embedding(self, text: str) -> Optional[list]:
        key = self._make_key("embed", text)
        return self.get(key)

    def set_embedding(self, text: str, embedding: list) -> None:
        key = self._make_key("embed", text)
        self.set(key, embedding, self.settings.REDIS_TTL_EMBEDDING)