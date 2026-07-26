# tests/test_embedding_service.py
import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def service():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    from app2.embedding.embedding_service import get_embedding_service

    return get_embedding_service()


def test_embedding_valid_text(service):
    import numpy as np

    result = service.embed("سلام این یک تست است")
    assert isinstance(result, np.ndarray)
    assert result.shape[0] > 100


def test_embedding_empty_text_raises(service):
    from app2.exceptions import ValidationError

    with pytest.raises(ValidationError):
        service.embed("")
