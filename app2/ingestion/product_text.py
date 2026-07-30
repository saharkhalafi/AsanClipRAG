from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

SEMANTIC_FIELDS = (
    "name",
    "short_description",
    "description",
    "product_type",
    "occasion",
    "platform",
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_product_rag_text(product: Mapping[str, Any]) -> str:
    """Build stable Persian retrieval text from semantic product fields."""
    labels = (
        ("product_type", "نوع"),
        ("occasion", "مناسبت"),
        ("platform", "پلتفرم"),
    )
    parts: list[str] = []
    for field, label in labels:
        value = _clean(product.get(field))
        if value:
            parts.append(f"{label}: {value}")

    for field in ("name", "short_description", "description"):
        value = _clean(product.get(field))
        if value:
            parts.append(value)
    return " | ".join(parts)


def product_content_hash(product: Mapping[str, Any]) -> str:
    """Hash only fields that affect embeddings and retrieval semantics."""
    canonical = {
        field: _clean(product.get(field))
        for field in SEMANTIC_FIELDS
    }
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
