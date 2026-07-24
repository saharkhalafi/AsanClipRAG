# tests/unit/test_firewall/test_query_firewall.py
from jsonschema import ValidationError
import pytest
from unittest.mock import MagicMock
from app2.firewall.query_firewall import QueryFirewall

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_semantic():
    detector = MagicMock()
    detector.detect.return_value = {"best_score": 0.75, "fallback_to_name": False}
    detector.check_relevance.return_value = {"ok": False, "reason": "low_semantic_relevance_or_chat_like"}
    return detector

def test_firewall_allows_good_query(mock_db, mock_semantic):
    firewall = QueryFirewall(db=mock_db, semantic_detector=mock_semantic)
    result = firewall.check("ویدیو تولد مبارک")
    assert result["allowed"] == True

