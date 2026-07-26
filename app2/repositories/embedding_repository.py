# app2/repositories/embedding_repository.py
from app2.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository):
    def save_embedding(self, text: str, embedding: list):
        # اگر بعداً نیاز به ذخیره embedding در دیتابیس داشتی
        pass
