# tests/conftest.py
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app2.db.base import Base
from app2.core.settings import get_settings
from app2.embedding.embedding_service import EmbeddingService

settings = get_settings()

@pytest.fixture(scope="session")
def db_engine():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in environment variables")

    engine = create_engine(DATABASE_URL)

    # فقط ایجاد جداول — حذف نکن
    Base.metadata.create_all(engine)

    yield engine

    # IMPORTANT: جداول را حذف نکن (برای محیط توسعه)
    # Base.metadata.drop_all(engine)   ← این خط را کامنت یا حذف کن


@pytest.fixture(scope="function")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()   # فقط rollback کن، drop نکن
    session.close()


@pytest.fixture(scope="function")
def embedding_service():
    return EmbeddingService()


@pytest.fixture(scope="function")
def test_client():
    from fastapi.testclient import TestClient
    from app2.main import app
    return TestClient(app)