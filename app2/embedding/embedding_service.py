# app2/services/embedding_service.py

import logging
import os
import time
from typing import Optional

import numpy as np
from google import genai
from httpx import ConnectError, ConnectTimeout
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app2.exceptions import DatabaseError, ValidationError

from ..cache.cache_service import CacheService

logger = logging.getLogger("app2.embedding")


def _is_transient_embedding_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectError, ConnectTimeout)):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        return False
    return status_code == 429 or status_code >= 500


class EmbeddingService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValidationError("GEMINI_API_KEY is not set")

        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.cache = CacheService()

    # 🚨 مهم: ValidationError داخل retry نباید باشد
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_random_exponential(multiplier=1.5, min=2, max=30),
        retry=retry_if_exception(_is_transient_embedding_error),
        reraise=True,
    )
    def _call_gemini(self, text: str):
        start_time = time.perf_counter()

        result = self.client.models.embed_content(
            model=self.model,
            contents=text
        )

        if not result or not result.embeddings:
            raise RuntimeError("Empty embedding response")

        embedding_obj = result.embeddings[0]
        values = getattr(embedding_obj, "values", None)

        if values is None:
            raise RuntimeError("Embedding values missing")

        embedding = np.array(values, dtype=np.float32)

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(f"Embedding successful | latency={latency}ms | text_len={len(text)}")

        return embedding

    def embed(self, text: str) -> np.ndarray:
        # =========================
        # 1. HARD VALIDATION (NO RETRY)
        # =========================
        if text is None or not isinstance(text, str):
            raise ValidationError("Input text must be a non-empty string")

        text = text.strip()

        # ❌ مهم: این باید قبل retry باشد
        if not text:
            raise ValidationError("empty_embedding_input")

        # =========================
        # 2. CACHE
        # =========================
        cached = self.cache.get_embedding(text)
        if cached:
            logger.debug(f"Embedding cache hit | text_len={len(text)}")
            return np.asarray(cached, dtype=np.float32)

        # =========================
        # 3. CALL MODEL
        # =========================
        try:
            embedding = self._call_gemini(text)

            # save cache
            self.cache.set_embedding(text, embedding.tolist())

            return embedding

        except (ConnectError, ConnectTimeout) as e:
            logger.warning(f"Network error: {e}")
            raise DatabaseError(
                "Temporary connection error to embedding service"
            ) from e

        except Exception as e:
            logger.error(f"Embedding failed: {e!s} | text: {text[:100]}...")
            raise DatabaseError(f"Embedding service failed: {e!s}") from e


# Lazy singleton — safe to import without GEMINI_API_KEY (CI / unit tests)
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
