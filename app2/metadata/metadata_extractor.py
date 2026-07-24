from typing import List, Dict, Any
import re


class MetadataExtractor:

    def __init__(
        self,
        product_types: List[str],
        occasions: List[str],
        platforms: List[str],
    ):
        self.product_types = product_types
        self.occasions = occasions
        self.platforms = platforms

    # --------------------------------------------------
    # NORMALIZATION
    # --------------------------------------------------

    def _normalize(self, text: str) -> str:
        if not text:
            return ""

        text = text.lower()

        # normalize Persian variants
        text = text.replace("ي", "ی")
        text = text.replace("ك", "ک")

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # --------------------------------------------------
    # TOKENIZATION (IMPORTANT FIX)
    # --------------------------------------------------

    def _tokens(self, text: str) -> set:
        return set(re.findall(r"[\w\u0600-\u06FF]+", text))

    # --------------------------------------------------
    # SMART MATCHER (FIXED CORE)
    # --------------------------------------------------

    def _score_match(self, q: str, v: str) -> float:

        # exact match
        if v == q:
            return 1.0

        # containment (strong)
        if v in q:
            return 0.9

        if q in v and len(q) >= 3:
            return 0.8

        # token overlap (VERY IMPORTANT FIX)
        q_tokens = self._tokens(q)
        v_tokens = self._tokens(v)

        if not q_tokens or not v_tokens:
            return 0.0

        overlap = len(q_tokens & v_tokens) / len(q_tokens)

        return overlap

    # --------------------------------------------------
    # FIND MATCHES (IMPROVED)
    # --------------------------------------------------

    def _find_matches(
        self,
        query: str,
        values: List[str]
    ) -> List[str]:

        q = self._normalize(query)

        scored = []

        for value in values:
            if not value:
                continue

            v = self._normalize(value)

            score = self._score_match(q, v)

            if score > 0.55:   # threshold (important fix)
                scored.append((value, score))

        # sort by score DESC
        scored.sort(key=lambda x: x[1], reverse=True)

        # return values only
        return [s[0] for s in scored]

    # --------------------------------------------------
    # MAIN EXTRACTION
    # --------------------------------------------------

    def extract(self, query: str) -> Dict[str, Any]:

        q = self._normalize(query)

        filters: Dict[str, Any] = {}

        product_types = self._find_matches(q, self.product_types)
        occasions = self._find_matches(q, self.occasions)
        platforms = self._find_matches(q, self.platforms)

        # --------------------------------------------------
        # PRIORITY SYSTEM (VERY IMPORTANT FIX)
        # --------------------------------------------------

        # platform should NOT override everything
        # occasion is usually primary intent (e.g. "ولنتاین")

        if occasions:
            filters["occasion"] = occasions[0]

        if product_types:
            filters["product_type"] = product_types[0]

        if platforms:
            filters["platform"] = platforms[0]

        # --------------------------------------------------
        # SAFETY: avoid noisy platform-only match
        # --------------------------------------------------

        # if only platform matched, require stronger signal
        if (
            "platform" in filters
            and len(filters) == 1
        ):
            # reduce false positives like "اینستاگرام"
            if len(q) < 8:
                return {}

        return filters