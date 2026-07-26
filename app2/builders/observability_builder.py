# app2/builders/observability_builder.py
import uuid
from typing import Any


class ObservabilityBuilder:
    @staticmethod
    def build(
        raw_query: str,
        query: str,
        filters: dict,
        semantic: dict,
        quality: dict,
        retrieval: dict,
        results: list[dict],
        timings: dict,
        latency_total_ms: float,
        final_mode: str,
        extra: dict | None = None
    ) -> dict[str, Any]:
        payload = {
            "request_id": str(uuid.uuid4()),
            "query_raw": raw_query,
            "query_normalized": query,
            "query_length": len(query),
            "token_count": len(query.split()),
            "char_count": len(query),
            "filters": filters,
            "semantic": semantic,
            "semantic_best_field": semantic.get("best_field"),
            "semantic_best_score": float(semantic.get("best_score", 0.0)),
            "retrieval_quality": quality,
            "retrieval_quality_score": float(quality.get("retrieval_quality", 0.0)),
            "mode": final_mode,
            "route_reason": getattr(retrieval.get("route"), "reason", None) if retrieval.get("route") else None,
            "candidate_count": len(retrieval.get("candidate_ids", []) or []),
            "retry_triggered": retrieval.get("retry_triggered", False),
            "attempt_count": len(retrieval.get("attempt_history", [])),
            "attempt_history": retrieval.get("attempt_history", []),
            "bm25_used": bool(final_mode in {"hybrid", "lexical"}),
            "fallback_used": bool(retrieval.get("retry_triggered") or final_mode in {"hybrid", "lexical"}),
            "result_count": len(results),
            "top_result_id": results[0].get("id") if results else None,
            "top_result_score": float(results[0].get("final_score", 0.0)) if results else None,
            "top_results": results[:5],
            "latency_total_ms": latency_total_ms,
            "latency_breakdown_ms": timings,
            "latency_firewall_ms": timings.get("firewall_ms"),
            "latency_preprocess_ms": timings.get("preprocess_ms"),
            "latency_metadata_ms": timings.get("metadata_ms"),
            "latency_semantic_ms": timings.get("semantic_ms"),
            "latency_embedding_ms": timings.get("embedding_ms"),
            "latency_candidate_ms": timings.get("candidate_ms"),
            "latency_retrieval_ms": timings.get("retrieval_ms"),
            "latency_ranking_ms": timings.get("ranking_ms"),
            "latency_alignment_ms": timings.get("alignment_boost_ms"),
            "estimated_input_tokens": len(query.split()),
            "estimated_output_tokens": 0,
            "total_tokens": len(query.split()),
            "model_version": "search_orchestrator_v1",
            "embedding_model": "embedding_service_default",
            "retrieval_version": "retrieval_orchestrator_v1",
            "cache_hit": False,
            "cache_layer": None,
            "extra": extra or {},
        }
        return payload
