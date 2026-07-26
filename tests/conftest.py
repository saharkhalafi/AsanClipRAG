# tests/conftest.py
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load local .env before app imports (session.py requires DATABASE_URL at import time).
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/asanclip_test",
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENABLE_CACHE", "false")
os.environ.setdefault("ENABLE_PII_DETECTION", "false")

# When pytest runs on the host, Docker Compose service names are not resolvable.
_db_url = os.environ.get("DATABASE_URL", "")
if "@postgres:" in _db_url:
    os.environ["DATABASE_URL"] = _db_url.replace("@postgres:5432", "@localhost:5433")

from app2.db.base import Base  # noqa: E402
from app2.exceptions import ValidationError  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: tests that need GEMINI_API_KEY")


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    # Values are set at import time above; keep fixture for clarity/extension.
    yield


@pytest.fixture(scope="session", autouse=True)
def _stub_embedding_without_api_key():
    """Allow CI to run without GEMINI_API_KEY by stubbing embeddings."""
    if os.getenv("GEMINI_API_KEY"):
        yield
        return

    from app2.embedding import embedding_service as es_mod

    class StubEmbeddingService:
        def embed(self, text: str) -> np.ndarray:
            if text is None or not isinstance(text, str) or not text.strip():
                raise ValidationError("empty_embedding_input")
            seed = abs(hash(text.strip())) % (2**32)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(3072, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm == 0:
                vec[0] = 1.0
                norm = 1.0
            return vec / norm

    es_mod.EmbeddingService = StubEmbeddingService
    es_mod._embedding_service = None
    yield


@pytest.fixture(scope="session")
def db_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in environment variables")

    engine = create_engine(database_url)

    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    except OperationalError as exc:
        pytest.skip(f"PostgreSQL not available for integration tests: {exc}")

    Base.metadata.create_all(engine)

    yield engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_client(db_engine):
    from app2.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)
