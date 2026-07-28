# tests/unit/test_firewall/test_query_firewall.py
from unittest.mock import MagicMock

import pytest
from app2.exceptions import ValidationError
from app2.firewall.query_firewall import QueryFirewall


@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_semantic():
    detector = MagicMock()
    detector.detect.return_value = {
        "ok": True,
        "best_score": 0.75,
        "fallback_to_name": False,
    }
    detector.check_relevance.return_value = {"ok": True, "reason": "ok"}
    return detector


def test_firewall_allows_good_query(mock_db, mock_semantic):
    firewall = QueryFirewall(db=mock_db, semantic_detector=mock_semantic)
    result = firewall.check("ویدیو تولد مبارک")
    assert result["allowed"] is True


def test_firewall_blocks_all_relevance_failures(mock_db, mock_semantic):
    mock_semantic.check_relevance.return_value = {
        "ok": False,
        "reason": "low_semantic_relevance_or_chat_like",
        "top1_sim": 0.41,
        "final_score": 0.39,
    }
    firewall = QueryFirewall(db=mock_db, semantic_detector=mock_semantic)

    with pytest.raises(ValidationError) as exc_info:
        firewall.check("من خیلی تولد دوست دارم ولی هیچکس برام نمیگیره")

    assert exc_info.value.context.get("signals", {}).get("relevance", {}).get("ok") is False
    assert "low_semantic_relevance" in str(exc_info.value)
