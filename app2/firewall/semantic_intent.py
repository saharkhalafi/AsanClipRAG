#app2/firewall/semantic_intent.py
from __future__ import annotations

import re
import numpy as np
from difflib import SequenceMatcher
from typing import Dict, List, Any, Optional
from sqlalchemy import text
from app2.exceptions import ValidationError


# =========================================================
# HELPERS
# =========================================================

def _normalize(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().lower()
    text = (
        text.replace("ي", "ی")
            .replace("ك", "ک")
            .replace("ة", "ه")
    )
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"[\w\u0600-\u06FF]+", _normalize(text))


def _similarity(a: str, b: str) -> float:
    a = _normalize(a)
    b = _normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# =========================================================
# QUERY NOISE / CHAT HELPERS
# =========================================================

# Conversational filler — stripped before catalog matching, NOT chat signals.
FILLER_TOKENS = frozenset({
    "چی", "چیه", "چیز", "چیزی", "داری", "دارید", "دارم", "دارین",
    "میخوام", "میخواهم", "میخوای", "میخوایم", "میخواهیم",
    "برای", "یه", "یک", "خوب", "بهترین", "لطفا", "لطفاً",
    "بده", "بفرست", "بفرستم", "بساز", "بسازم", "کن", "کنید",
    "کدوم", "چطور", "چجوری", "چگونه", "میشه", "میتونم", "میتونی",
    "خیلی", "خفن", "ساده", "شیک", "لطف", "لطفا", "لطفاً",
    "چند", "چقد", "چقدر", "هم", "رو", "را", "به", "از", "تو", "من",
    "ما", "شما", "اون", "اونا", "این", "اون", "که", "با", "و",
})

# Hostile / meta-chat directed at the bot — only block when catalog has no signal.
HOSTILE_CHAT_TOKENS = frozenset({
    "چرا", "مگه", "اصلا", "فکر", "فکرمی", "نظرت", "مشکلت", "حالت",
    "میگی", "میفهمی", "نمیفهمی", "احمق", "مسخره", "خراب", "اشتباه",
    "افتضاح", "فاجعه", "usable", "hallucinate", "contradictory",
    "نیستی", "بدی", "بد", "کیفیت", "overthink", "trust", "consistency",
    "production", "pipeline", "failure", "offtopic", "off-topic",
})


def _content_tokens(text: str) -> List[str]:
    return [t for t in _tokens(text) if t not in FILLER_TOKENS]


def _is_hostile_chat(query: str) -> bool:
    """True when the user is complaining to / about the bot, not searching."""
    tokens = set(_tokens(query))
    hostile_hits = tokens & HOSTILE_CHAT_TOKENS

    if len(hostile_hits) >= 3:
        return True

    # "تو" + complaint language is almost always meta-chat
    if "تو" in tokens and len(hostile_hits) >= 1:
        return True

    complaint_pairs = (
        ("چرا", "نمیفهمی"),
        ("چرا", "بد"),
        ("اصلا", "نمیفهمی"),
        ("اصلا", "بلد"),
        ("چرا", "کار"),
        ("چرا", "اشتباه"),
    )
    q = _normalize(query)
    for a, b in complaint_pairs:
        if a in q and b in q:
            return True

    return False


# =========================================================
# DETECTOR
# =========================================================

class SemanticIntentDetector:

    def __init__(
        self,
        catalog: Dict[str, List[str]],
        sparse_fields: Optional[List[str]] = None,
        fallback_label_field: str = "product_names",
        embedder=None,
        db=None
    ):
        self.catalog = {
            field: sorted({_normalize(v) for v in values if v and str(v).strip()})
            for field, values in catalog.items()
        }

        self.sparse_fields = set(sparse_fields or [])
        self.fallback_label_field = fallback_label_field
        self.embedder = embedder
        self.db = db

        self.field_weights = {
            "product_names": 1.25,
            "occasions": 1.20,
            "product_types": 1.00,
            "platforms": 0.80,
        }
        self.embedding_calls = 0

    # =====================================================
    # MAIN DETECT
    # =====================================================
    def detect(self, query: str) -> Dict[str, Any]:
        q = _normalize(query)
        q_tokens = set(_tokens(q))
        content_tokens = set(_content_tokens(q)) or q_tokens

        matches: Dict[str, Any] = {}
        best_field = None
        best_score = 0.0

        for field, values in self.catalog.items():
            weight = self.field_weights.get(field, 1.0)
            threshold = 0.52 if field in ("occasions", "product_types") else 0.60

            field_best_value = None
            field_best_score = 0.0

            for value in values:
                score = self._score(q, content_tokens, value) * weight
                if score > field_best_score:
                    field_best_score = score
                    field_best_value = value

            if field_best_value and field_best_score >= threshold:
                matches[field] = {
                    "value": field_best_value,
                    "score": round(field_best_score, 4)
                }

                if field_best_score > best_score:
                    best_score = field_best_score
                    best_field = field

        fallback = len(matches) == 0

        if fallback and self.fallback_label_field in self.catalog:
            best_name_score = 0.0
            best_name = None

            for name in self.catalog[self.fallback_label_field]:
                score = self._score(q, content_tokens, name)
                if score > best_name_score:
                    best_name_score = score
                    best_name = name

            if best_name and best_name_score >= 0.72:
                matches[self.fallback_label_field] = {
                    "value": best_name,
                    "score": round(best_name_score, 4)
                }
                best_field = self.fallback_label_field
                best_score = best_name_score
                fallback = False

        if best_score < 0.45:
            if _is_hostile_chat(query):
                return {
                    "ok": False,
                    "best_score": round(float(best_score), 4),
                    "matches": {},
                    "fallback_to_name": True,
                    "reason": "chat_like_query_blocked"
                }
            return {
                "ok": False,
                "best_score": round(float(best_score), 4),
                "matches": {},
                "fallback_to_name": True,
                "reason": "low_semantic_confidence"
            }

        return {
            "ok": True,
            "best_field": best_field,
            "best_score": round(float(best_score), 4),
            "matches": matches,
            "fallback_to_name": fallback,
        }

    # =====================================================
    # SCORING
    # =====================================================
    def _score(self, query: str, q_tokens: set, candidate: str) -> float:
        candidate = _normalize(candidate)
        cand_tokens = set(_tokens(candidate))

        if not query or not candidate:
            return 0.0

        if query == candidate:
            return 1.0

        # Multi-word catalog value fully present in query (e.g. "روز مادر")
        if len(cand_tokens) >= 2 and cand_tokens.issubset(q_tokens):
            return 0.92

        if candidate in query:
            return 0.88

        overlap = 0.0
        if q_tokens and cand_tokens:
            overlap = len(q_tokens & cand_tokens) / len(cand_tokens)

        fuzzy = _similarity(query, candidate)

        if overlap == 0:
            return fuzzy * 0.40

        return max(overlap * 0.70 + fuzzy * 0.30, overlap * 0.85)

    # =====================================================
    # RELEVANCE CHECK (UNCHANGED BUT CLEAN)
    # =====================================================
    def check_relevance(self, query: str, min_final_score: float = 0.50) -> Dict[str, Any]:
        q = _normalize(query)

        if not q or len(q) < 4:
            return {"ok": False, "reason": "empty_or_too_short", "score": 0.0}

        if not self.embedder or not self.db:
            return {"ok": True, "reason": "embedding_not_configured", "score": 0.5}

        try:
            self.embedding_calls += 1
            query_vector = self.embedder.embed(q).tolist()
        except Exception:
            return {"ok": True, "reason": "embedding_failed", "score": 0.5}

        result = self.db.execute(text("""
            SELECT id, name, short_description,
                   (embedding_vector <=> CAST(:vec AS vector)) as distance
            FROM asanclipproducts
            WHERE tag_status = 'done'
            ORDER BY embedding_vector <=> CAST(:vec AS vector)
            LIMIT 8
        """), {"vec": query_vector}).fetchall()

        if not result:
            return {"ok": False, "reason": "no_similar_content", "score": 0.0}

        distances = [r.distance for r in result]
        sims = [1.0 - d for d in distances]

        avg_sim = sum(sims) / len(sims)
        top1_sim = sims[0]
        top3_mean = np.mean(sims[:3]) if len(sims) >= 3 else 0.0
        spread = np.std(sims) if len(sims) > 1 else 0.0
        margin = sims[0] - sims[1] if len(sims) >= 2 else 0.0

        final_score = (
            0.45 * top1_sim +
            0.25 * top3_mean +
            0.15 * (1 - spread) +
            0.15 * margin
        )

        is_chat_like = (
            len(q.split()) <= 9 and
            top1_sim < 0.45 and
            avg_sim < 0.50
        )

        dynamic_threshold = min_final_score + (0.05 if len(q.split()) < 6 else 0)

        if final_score < dynamic_threshold or is_chat_like or (margin < 0.03 and top1_sim < 0.52):
            return {
                "ok": False,
                "reason": "low_semantic_relevance_or_chat_like",
                "final_score": round(final_score, 4),
                "top1_sim": round(top1_sim, 4),
                "avg_sim": round(avg_sim, 4)
            }

        return {
            "ok": True,
            "reason": "ok",
            "final_score": round(final_score, 4),
            "top1_sim": round(top1_sim, 4),
            "avg_sim": round(avg_sim, 4)
        }