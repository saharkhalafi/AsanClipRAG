#app2/firewall/injection_detector.py

from typing import Any


class InjectionDetector:
    def __init__(self):
        self.patterns = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "ignore previous",
            "system prompt",
            "developer message",
            "reveal database",
            "show database",
            "dump database",
            "print secrets",
            "bypass filter",
            "override rules",
            "jailbreak",
            "prompt injection",
            "دستورهای قبلی را نادیده بگیر",
            "نادیده بگیر",
            "پرامپت سیستم",
            "دیتابیس را نشان بده",
            "پایگاه داده را نشان بده",
        ]

    def check(self, query: str) -> dict[str, Any]:
        q = (query or "").lower()

        for p in self.patterns:
            if p.lower() in q:
                return {
                    "ok": False,
                    "reason": "prompt_injection_detected",
                    "pattern": p,
                }

        return {"ok": True, "reason": "ok"}
