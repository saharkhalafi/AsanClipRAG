# app2/firewall/query_firewall.py
import os
import re
from typing import Dict, Any, Optional

from app2.firewall.abuse_detector import AbuseDetector
from app2.firewall.injection_detector import InjectionDetector
from app2.firewall.cost_controller import CostController
from app2.firewall.semantic_intent import SemanticIntentDetector
from app2.firewall.query_validator import QueryValidator
from app2.firewall.Presidio import PIIDetector

from app2.exceptions import ValidationError


class QueryFirewall:

    def __init__(self, db, semantic_detector: SemanticIntentDetector):
        self.db = db
        self.abuse = AbuseDetector()
        self.injection = InjectionDetector()
        self.cost = CostController()
        self.query_validator = QueryValidator()
        self.semantic = semantic_detector
        self.pii_enabled = os.getenv("ENABLE_PII_DETECTION", "true").lower() in (
            "1",
            "true",
            "yes",
        )
        self._pii: Optional[PIIDetector] = None

    def _get_pii_detector(self) -> Optional[PIIDetector]:
        if not self.pii_enabled:
            return None
        if self._pii is None:
            self._pii = PIIDetector()
        return self._pii

    def _normalize(self, query: str) -> str:
        if not query:
            return ""
        return " ".join(query.strip().split())

    def _looks_like_junk(self, query: str) -> bool:
        q = query.lower().strip()
        if len(q.split()) <= 4:
            return False

        latin_words = re.findall(r"\b[a-z]{4,}\b", q, flags=re.IGNORECASE)
        if len(latin_words) >= 3:
            vowels = set("aeiou")
            ratios = []
            for w in latin_words:
                letters = [c for c in w if c.isalpha()]
                if not letters:
                    continue
                ratio = sum(1 for c in letters if c in vowels) / len(letters)
                ratios.append(ratio)
            if ratios and all(r < 0.18 for r in ratios):
                return True

        alpha_ratio = sum(c.isalpha() for c in q) / max(len(q), 1)
        if alpha_ratio < 0.32:
            return True

        return False

    def check(self, query: str) -> Dict[str, Any]:
        query = self._normalize(query)

        signals: Dict[str, Any] = {
            "abuse": None,
            "injection": None,
            "pii": None,
            "cost": None,
            "query_validation": None,
            "semantic": None,
            "relevance": None,
        }
        if not query or len(query) < 4:
            raise ValidationError("Query is empty or too short")

        # 1. Abuse
        abuse_result = self.abuse.check(query)
        signals["abuse"] = abuse_result
        if not abuse_result.get("ok", False):
            raise ValidationError(f"Abuse detected: {abuse_result.get('reason')}")

        # 2. Injection
        injection_result = self.injection.check(query)
        signals["injection"] = injection_result
        if not injection_result.get("ok", False):
            raise ValidationError("Prompt injection detected")

        # 3. PII (Presidio)
        pii_detector = self._get_pii_detector()
        if pii_detector is not None:
            pii_result = pii_detector.check(query)
            signals["pii"] = pii_result
            if not pii_result.get("ok", False):
                raise ValidationError("pii_detected")
        else:
            signals["pii"] = {"ok": True, "reason": "disabled"}

        # 4. Cost
        try:
            cost_result = self.cost.check(self.db, query)
        except Exception as e:
            cost_result = {"allowed": True, "reason": f"cost_failed:{str(e)}", "cost_units": 0}

        signals["cost"] = cost_result
        if not cost_result.get("allowed", True):
            raise ValidationError(cost_result.get("reason", "cost_blocked"))

        # 5. Query Validator
        validation = self.query_validator.validate(query)
        signals["query_validation"] = {"score": validation.score, "reason": validation.reason}

        if not validation.ok:
            raise ValidationError(validation.reason)

        # 6. Junk
        if self._looks_like_junk(query):
            raise ValidationError("junk_query")

        # 7. Semantic Intent
        semantic_result = self.semantic.detect(query)
        signals["semantic"] = semantic_result

        if not semantic_result.get("ok", True):
            reason = semantic_result.get("reason", "low_semantic_confidence")
            raise ValidationError(reason)

        semantic_score = float(semantic_result.get("best_score", 0.0))
        fallback = semantic_result.get("fallback_to_name", True)

        # 8. Relevance (relaxed for good queries)
        relevance = self.semantic.check_relevance(query, min_final_score=0.48)
        signals["relevance"] = relevance

        if not relevance.get("ok", True):
            reason = relevance.get("reason", "low_relevance")
            if reason in ("no_similar_content", "embedding_failed"):
                raise ValidationError(reason)

        return {
            "allowed": True,
            "reason": "ok",
            "fallback": fallback,
            "semantic_score": semantic_score,
            "signals": signals,
        }