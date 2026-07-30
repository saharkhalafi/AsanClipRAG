from __future__ import annotations

import numpy as np
import pytest

from app2.ingestion import build_product_rag_text, product_content_hash
from app2.retrieval.faiss_index import FaissIndex
from scripts import build_faiss_index
from scripts.ingest_products import clean_row


def test_product_hash_changes_only_for_semantic_fields():
    product = {
        "name": "کلیپ تولد",
        "description": "متن نمونه",
        "product_type": "کلیپ",
        "url": "https://example.test/old",
    }
    original = product_content_hash(product)

    product["url"] = "https://example.test/new"
    assert product_content_hash(product) == original

    product["description"] = "متن جدید"
    assert product_content_hash(product) != original


def test_clean_row_builds_deterministic_rag_text_and_hash():
    payload = clean_row(
        {
            "id": "42",
            "name": " کلیپ تولد ",
            "description": " توضیح ",
            "product_type": "ویدیو",
            "occasion": "تولد",
        },
        "run-1",
    )

    assert payload["id"] == 42
    assert payload["rag_text"] == build_product_rag_text(payload)
    assert payload["rag_text"].startswith("نوع: ویدیو | مناسبت: تولد")
    assert len(payload["content_hash"]) == 64
    assert payload["ingestion_run_id"] == "run-1"


def test_clean_row_rejects_empty_name():
    with pytest.raises(ValueError, match="empty name"):
        clean_row({"id": 1, "name": None}, "run-1")


def test_faiss_builder_writes_loader_compatible_artifacts(monkeypatch, tmp_path):
    dimension = 4
    vectors = np.asarray(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    monkeypatch.setattr(
        build_faiss_index,
        "_load_snapshot",
        lambda database_url, requested_dimension: (
            vectors,
            [101, 202],
            {"embedding_models": ["test-model"], "source_latest_updated_at": None},
        ),
    )
    output = tmp_path / "faiss.index"

    manifest = build_faiss_index.build_faiss_index(
        "postgresql://unused",
        str(output),
        dimension=dimension,
        min_vectors=2,
    )

    assert output.exists()
    assert output.with_suffix(".pkl").exists()
    assert output.with_suffix(".manifest.json").exists()
    assert manifest["vector_count"] == 2
    assert manifest["dimension"] == dimension

    loaded = FaissIndex(dimension=dimension, index_path=str(output))
    loaded.load_index()
    assert loaded.search(vectors[0], k=1)[0][0] == 101
