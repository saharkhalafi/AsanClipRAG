# tests/test_embedding_service.py
import os

import numpy as np
import pytest
from app2.embedding.embedding_service import EmbeddingService, get_embedding_service
from app2.exceptions import ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def service():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    return get_embedding_service()


def test_embedding_valid_text(service):
    result = service.embed("سلام این یک تست است")
    assert isinstance(result, np.ndarray)
    assert result.shape[0] > 100


def test_embedding_empty_text_raises(service):
    with pytest.raises(ValidationError):
        service.embed("")
