# app2/firewall/query_validator.py
import re
from dataclasses import dataclass


@dataclass
class QueryValidationResult:
    ok: bool
    score: float
    reason: str


class QueryValidator:

    def __init__(self):
        self.danger_patterns = [
            r"\bdelete\b",
            r"\bdrop\b",
            r"\btruncate\b",
            r"\bپاک\s*کن\b",
            r"\bحذف\s*کن\b",
            r"\bshutdown\b",
            r"\bformat\b",
        ]

        self.instruction_patterns = [
            r"\bبعد\b",
            r"\bسپس\b",
            r"\bthen\b",
            r"\bafter that\b",
        ]

    def _has_danger(self, query: str) -> bool:
        q = query.lower()
        return any(re.search(p, q) for p in self.danger_patterns)

    def _instruction_noise(self, query: str) -> float:
        q = query.lower()
        hits = sum(1 for p in self.instruction_patterns if re.search(p, q))
        return min(hits / 2, 1.0)

    def validate(self, query: str) -> QueryValidationResult:
        q = query.strip().lower()

        score = 1.0
        reason = "ok"

        if self._has_danger(q):
            return QueryValidationResult(
                ok=False,
                score=0.0,
                reason="dangerous_instruction_detected"
            )

        noise = self._instruction_noise(q)
        score -= noise * 0.4

        if len(q) < 4:
            return QueryValidationResult(
                ok=False,
                score=0.1,
                reason="too_short"
            )

        if re.search(r"(.)\1{4,}", q):
            score -= 0.35
            reason = "repetition_noise"

        score = max(0.0, min(score, 1.0))

        ok = score >= 0.40   # relaxed

        return QueryValidationResult(
            ok=ok,
            score=score,
            reason=reason if ok else "low_query_quality"
        )
