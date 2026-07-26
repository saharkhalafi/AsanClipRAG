from typing import Any


class RouteDecision:
    def __init__(
        self,
        mode: str,
        reason: str = "",
        signals: dict[str, Any] | None = None
    ):
        self.mode = mode
        self.reason = reason
        self.signals = signals or {}


class QueryRouter:

    def route(
        self,
        query: str,
        retrieval_quality: dict[str, Any],
        filters: dict[str, Any],
        lexical_signal: dict[str, Any] | None = None
    ) -> RouteDecision:

        # -----------------------------
        # SAFE EXTRACTION
        # -----------------------------
        quality_decision = str(retrieval_quality.get("decision", "hybrid")).lower()
        signals = retrieval_quality.get("signals", {})

        top1 = float(signals.get("top1", 0.0))
        margin = float(signals.get("margin", 0.0))
        density = float(signals.get("density", 0.0))
        entropy = float(signals.get("entropy", 1.0))
        overlap = float(signals.get("overlap", 0.0))
        stability = float(signals.get("stability", 0.0))

        lexical = float((lexical_signal or {}).get("top_score", 0.0))

        has_metadata = any(filters.get(k) for k in [
            "occasion",
            "platform",
            "product_type"
        ])

        # -------------------------------------------------
        # 1) HARD LOCK: if quality model says VECTOR, trust it
        # -------------------------------------------------
        if quality_decision == "vector":
            return RouteDecision(
                mode="vector",
                reason="retrieval_quality_says_vector",
                signals={
                    "quality_decision": quality_decision,
                    "top1": top1,
                    "margin": margin,
                    "overlap": overlap,
                    "entropy": entropy,
                    "lexical": lexical,
                    "density": density,
                    "stability": stability
                }
            )

        # -------------------------------------------------
        # 2) HARD LOCK: if quality model says FALLBACK
        # -------------------------------------------------
        if quality_decision == "fallback":
            return RouteDecision(
                mode="fallback",
                reason="retrieval_quality_says_fallback",
                signals={
                    "quality_decision": quality_decision,
                    "top1": top1,
                    "margin": margin,
                    "lexical": lexical
                }
            )

        # -------------------------------------------------
        # 3) If quality says HYBRID, allow hybrid
        #    but only when lexical is actually meaningful.
        # -------------------------------------------------
        if quality_decision == "hybrid":
            if lexical >= 0.55 or (not has_metadata and lexical >= 0.40):
                return RouteDecision(
                    mode="hybrid",
                    reason="quality_model_hybrid_with_lexical_support",
                    signals={
                        "quality_decision": quality_decision,
                        "top1": top1,
                        "margin": margin,
                        "lexical": lexical,
                        "overlap": overlap
                    }
                )

            # If lexical is weak, do not force hybrid
            return RouteDecision(
                mode="vector",
                reason="hybrid_quality_but_weak_lexical_fallback_to_vector",
                signals={
                    "quality_decision": quality_decision,
                    "top1": top1,
                    "margin": margin,
                    "lexical": lexical,
                    "overlap": overlap
                }
            )

        # -------------------------------------------------
        # 4) Safety fallback: strong vector-like signal
        # -------------------------------------------------
        if (
            top1 >= 0.65 and
            margin >= 0.02 and
            overlap >= 0.50 and
            entropy <= 0.98 and
            lexical < 0.50
        ):
            return RouteDecision(
                mode="vector",
                reason="strong_semantic_match",
                signals={
                    "top1": top1,
                    "margin": margin,
                    "overlap": overlap,
                    "entropy": entropy,
                    "lexical": lexical
                }
            )

        # -------------------------------------------------
        # 5) Strong lexical only if vector is weak
        # -------------------------------------------------
        if lexical >= 0.70 and top1 < 0.60:
            return RouteDecision(
                mode="lexical",
                reason="bm25_dominant_signal",
                signals={
                    "top1": top1,
                    "lexical": lexical,
                    "entropy": entropy
                }
            )

        # -------------------------------------------------
        # 6) Default
        # -------------------------------------------------
        return RouteDecision(
            mode="vector",
            reason="default_vector",
            signals={
                "top1": top1,
                "margin": margin,
                "lexical": lexical,
                "overlap": overlap
            }
        )
