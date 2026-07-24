# tests/unit/test_services/test_embedding_service.py
import pytest
import numpy as np
from app2.embedding.embedding_service import embedding_service
from app2.exceptions import ValidationError

def test_embedding_valid_text():
    result = embedding_service.embed("سلام این یک تست است")
    assert isinstance(result, np.ndarray)
    assert result.shape[0] > 100


def test_embedding_empty_text_raises():
    with pytest.raises(ValidationError):
        embedding_service.embed("")   # بدون retry