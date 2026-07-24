# app2/firewall/abuse_detector.py
import re
import unicodedata
from typing import Dict, Any


class AbuseDetector:
    def __init__(self, max_length: int = 300):
        self.max_length = max_length

    def _latin_vowel_ratio(self, word: str) -> float:
        vowels = set("aeiou")
        letters = [c for c in word.lower() if c.isalpha()]
        if not letters:
            return 0.0
        return sum(1 for c in letters if c in vowels) / len(letters)

    def check(self, query: str) -> Dict[str, Any]:
        q = (query or "").strip()

        # ─────────────────────────────
        # 1. empty
        # ─────────────────────────────
        if not q:
            return {"ok": False, "reason": "empty_query"}

        # ─────────────────────────────
        # 2. length
        # ─────────────────────────────
        if len(q) > self.max_length:
            return {"ok": False, "reason": "too_long"}

        # ─────────────────────────────
        # 3. emoji spam (IMPORTANT: BEFORE repeat check)
        # ─────────────────────────────
        emoji_count = sum(1 for ch in q if unicodedata.category(ch) == "So")
        if emoji_count >= 8:
            return {"ok": False, "reason": "emoji_spam"}

        # ─────────────────────────────
        # 4. repeated chars spam
        # ─────────────────────────────
        if re.search(r"(.)\1{4,}", q):
            return {"ok": False, "reason": "spam_repeated_chars"}

        # ─────────────────────────────
        # 5. punctuation-only spam
        # ─────────────────────────────
        if re.fullmatch(r"[\s\?\!\.\،\؟\…]+", q):
            return {"ok": False, "reason": "punctuation_spam"}

        # ─────────────────────────────
        # 6. latin gibberish
        # ─────────────────────────────
        latin_words = re.findall(r"\b[a-z]{4,}\b", q, flags=re.IGNORECASE)
        if len(latin_words) >= 2 and all(
            self._latin_vowel_ratio(w) < 0.2 for w in latin_words
        ):
            return {"ok": False, "reason": "latin_gibberish"}

        # ─────────────────────────────
        # 7. low entropy spam
        # ─────────────────────────────
        cleaned = re.sub(r"\s+", "", q)
        if len(cleaned) >= 12 and len(set(cleaned)) <= 4:
            return {"ok": False, "reason": "low_entropy_spam"}

        # ─────────────────────────────
        # 8. OK
        # ─────────────────────────────
        return {"ok": True, "reason": "ok"}