# app2/services/embedding_service.py

import os
import time
import logging
import numpy as np

from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from httpx import ConnectError, ConnectTimeout

from app2.cache.cache_service import CacheService
from app2.exceptions import ValidationError, DatabaseError

logger = logging.getLogger("app2.embedding")


class EmbeddingService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValidationError("GEMINI_API_KEY is not set")

        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-embedding-001"
        self.cache = CacheService()

    # 🚨 مهم: ValidationError داخل retry نباید باشد
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.5, min=2, max=15),
        retry=retry_if_exception_type((ConnectError, ConnectTimeout))
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
            logger.error(f"Embedding failed: {str(e)} | text: {text[:100]}...")
            raise DatabaseError(f"Embedding service failed: {str(e)}") from e


# Singleton
embedding_service = EmbeddingService()