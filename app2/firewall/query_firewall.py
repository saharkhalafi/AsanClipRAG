# app2/firewall/query_firewall.py
import re
from typing import Any

from app2.exceptions import ValidationError
from app2.firewall.abuse_detector import AbuseDetector
from app2.firewall.cost_controller import CostController
from app2.firewall.injection_detector import InjectionDetector
from app2.firewall.query_validator import QueryValidator
from app2.firewall.semantic_intent import SemanticIntentDetector


class QueryFirewall:

    def __init__(self, db, semantic_detector: SemanticIntentDetector):
        self.db = db
        self.abuse = AbuseDetector()
        self.injection = InjectionDetector()
        self.cost = CostController()
        self.query_validator = QueryValidator()
        self.semantic = semantic_detector

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

    def check(self, query: str) -> dict[str, Any]:
        query = self._normalize(query)

        signals: dict[str, Any] = {
            "abuse": None,
            "injection": None,
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

        # 3. Cost
        try:
            cost_result = self.cost.check(self.db, query)
        except Exception as e:
            cost_result = {"allowed": True, "reason": f"cost_failed:{e!s}", "cost_units": 0}

        signals["cost"] = cost_result
        if not cost_result.get("allowed", True):
            raise ValidationError(cost_result.get("reason", "cost_blocked"))

        # 4. Query Validator
        validation = self.query_validator.validate(query)
        signals["query_validation"] = {"score": validation.score, "reason": validation.reason}

        if not validation.ok:
            raise ValidationError(validation.reason)

        # 5. Junk
        if self._looks_like_junk(query):
            raise ValidationError("junk_query")

        # 6. Semantic Intent
        semantic_result = self.semantic.detect(query)
        signals["semantic"] = semantic_result

        semantic_score = float(semantic_result.get("best_score", 0.0))
        fallback = semantic_result.get("fallback_to_name", True)

        semantic_gate = semantic_score * (1.0 if not fallback else 0.85)
        if semantic_gate < 0.08:
            raise ValidationError("low_semantic_confidence")

        # 7. Relevance (relaxed for good queries)
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
