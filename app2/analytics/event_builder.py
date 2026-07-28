
from __future__ import annotations

from typing import Any


def _extract_cost(fw_context: dict[str, Any]) -> dict[str, Any]:
    """Pull cost sub-dict out of firewall signals."""
    cost = (fw_context.get("signals") or {}).get("cost") or {}
    return {
        "cost_allowed": cost.get("allowed"),
        "cost_reason":  cost.get("reason"),
        "cost_units":   cost.get("cost_units"),
        "used_today":   cost.get("used_today"),
        "daily_limit":  cost.get("daily_limit"),
    }


def _intent_features(
    fw_context: dict[str, Any],
    result: dict[str, Any] | None = None,
    query_raw: str = "",
) -> dict[str, Any]:
    """RIS-ready features stored in retrieval_logs.extra."""
    signals = fw_context.get("signals") or {}
    semantic = signals.get("semantic") or {}
    relevance = signals.get("relevance") or {}

    query_text = (
        fw_context.get("normalized_query")
        or (result or {}).get("query")
        or query_raw
        or ""
    )
    query_text = str(query_text).strip()

    top1_vector_sim = relevance.get("top1_sim")
    semantic_score = semantic.get("best_score")
    if semantic_score is None:
        semantic_score = fw_context.get("semantic_score")

    features: dict[str, Any] = {
        "semantic_score": semantic_score,
        "semantic_ok": semantic.get("ok"),
        "semantic_reason": semantic.get("reason"),
        "top1_vector_sim": top1_vector_sim,
        "relevance_final_score": relevance.get("final_score"),
        "relevance_avg_sim": relevance.get("avg_sim"),
        "relevance_ok": relevance.get("ok"),
        "relevance_reason": relevance.get("reason"),
        "query_length": len(query_text),
        "token_count": len(query_text.split()) if query_text else 0,
    }

    if result is not None:
        obs = result.get("observability") or {}
        mode = result.get("mode")
        rq_score = float(
            obs.get("retrieval_quality_score")
            or (result.get("retrieval_quality") or {}).get("retrieval_quality")
            or 0.0
        )
        top_result_score = float(obs.get("top_result_score") or 0.0)
        result_count = int(obs.get("result_count") or len(result.get("results") or []))

        weak = (
            mode in ("invalid_query", "no_results", "empty_query")
            or result_count == 0
            or (rq_score < 0.35 and top_result_score < 0.45)
        )
        features["results_looked_weak"] = weak
        features["retrieval_quality_score"] = rq_score
        features["top_result_score"] = top_result_score
        features["result_count"] = result_count
        features["response_mode"] = mode
    else:
        features["results_looked_weak"] = True
        features["response_mode"] = "blocked_by_firewall"

    return features


class SearchEventBuilder:
    """
    Usage — firewall blocked:

        payload = SearchEventBuilder.from_firewall_block(
            query_raw   = query,
            fw_context  = fw_result,          # dict returned by QueryFirewall.check()
            request_id  = request_id,
            fw_latency  = fw_latency_ms,
            total_latency = total_latency_ms,
        )
        obs_logger.log_search_event(payload)

    Usage — search ran:

        payload = SearchEventBuilder.from_result(
            result      = orchestrator_result,
            fw_context  = fw_result,
            request_id  = request_id,
            fw_latency  = fw_latency_ms,
            total_latency = total_latency_ms,
        )
        obs_logger.log_search_event(payload)
    """

    # ── Path A: blocked by firewall ────────────────────────────────────────────

    @staticmethod
    def from_firewall_block(
        query_raw: str,
        fw_context: dict[str, Any],
        request_id: str,
        fw_latency: float,
        total_latency: float,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        signals = fw_context.get("signals") or {}
        reason  = fw_context.get("reason") or "blocked"
        semantic = signals.get("semantic") or {}
        intent = _intent_features(fw_context, result=None, query_raw=query_raw)

        payload: dict[str, Any] = {
            # identity
            "request_id":   request_id,
            "session_id":   session_id,
            "user_id":      user_id,
            # query
            "query_raw":        query_raw,
            "query_normalized": fw_context.get("normalized_query") or query_raw,
            "query_length":     intent.get("query_length"),
            "token_count":      intent.get("token_count"),
            # firewall
            "blocked":          True,
            "block_reason":     reason,
            "firewall_allowed": False,
            "firewall_reason":  reason,
            "firewall_signals": signals,
            # semantic (for RIS calibration)
            "semantic":            semantic,
            "semantic_best_score": intent.get("semantic_score"),
            "semantic_best_field": semantic.get("best_field"),
            # latency
            "latency_firewall_ms": fw_latency,
            "latency_total_ms":    total_latency,
            # mode
            "mode":           "blocked_by_firewall",
            # zeroed-out retrieval fields
            "result_count":   0,
            "retry_triggered": False,
            "fallback_used":  False,
            "attempt_count":  0,
            "candidate_count": 0,
            "top_result_score": intent.get("top1_vector_sim"),
            # intent dataset
            "manual_intent_label":    None,
            "manual_relevance_label": None,
            "extra": intent,
        }
        payload.update(_extract_cost(fw_context))
        return payload

    # ── Path B: firewall passed, orchestrator ran ──────────────────────────────

    @staticmethod
    def from_result(
        result: dict[str, Any],
        fw_context: dict[str, Any],
        request_id: str,
        fw_latency: float,
        total_latency: float,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        obs: dict[str, Any] = result.get("observability") or {}
        latency_breakdown: dict[str, Any] = obs.get("latency_breakdown_ms") or {}

        # ── Cache Info ───────────────────────────────────────────────
        cache_hit = obs.get("cache_hit", False)
        cache_layer = obs.get("cache_layer")

        # ── Top results snapshot ───────────────────────────────────────────────
        top_results    = obs.get("top_results") or []
        top_result_id  = obs.get("top_result_id")
        top_result_score = obs.get("top_result_score")
        if not top_result_id and top_results:
            top_result_id    = top_results[0].get("id")
            top_result_score = top_results[0].get("score")

        attempt_history = obs.get("attempt_history") or []
        signals = fw_context.get("signals") or {}
        intent = _intent_features(fw_context, result=result, query_raw=obs.get("query_raw") or "")

        merged_extra = dict(obs.get("extra") or {})
        merged_extra.update(intent)

        payload: dict[str, Any] = {
            # identity
            "request_id": request_id,
            "session_id": session_id,
            "user_id":    user_id,
            # query
            "query_raw":        obs.get("query_raw") or "",
            "query_normalized": obs.get("query_normalized") or "",
            "language":         obs.get("language"),
            # firewall — always from the real fw_context, never from obs
            "blocked":          False,
            "block_reason":     None,
            "firewall_allowed": True,
            "firewall_reason":  fw_context.get("reason") or "ok",
            "firewall_signals": signals,
            "query_validation_score": obs.get("query_validation_score"),
            # semantic
            "semantic_best_field": obs.get("semantic_best_field"),
            "semantic_best_score": obs.get("semantic_best_score"),
            "semantic":            obs.get("semantic"),
            # routing
            "filters":      obs.get("filters"),
            "mode":         obs.get("mode"),
            "route_reason": obs.get("route_reason"),
            # retrieval
            "retrieval_quality":       obs.get("retrieval_quality"),
            "retrieval_quality_score": obs.get("retrieval_quality_score"),
            "candidate_count":   obs.get("candidate_count"),
            "bm25_used":         obs.get("bm25_used"),
            "retry_triggered":   obs.get("retry_triggered"),
            "attempt_count":     obs.get("attempt_count"),
            "attempt_history":   attempt_history,
            "fallback_used":     obs.get("fallback_used"),
            # results
            "result_count":      obs.get("result_count"),
            "top_result_id":     top_result_id,
            "top_result_score":  top_result_score,
            "top_results":       top_results,
            # latency — firewall measured in route, rest from breakdown
            "latency_total_ms":     total_latency,
            "latency_firewall_ms":  fw_latency,
            "latency_preprocess_ms": latency_breakdown.get("preprocess_ms") or obs.get("latency_preprocess_ms"),
            "latency_metadata_ms":   latency_breakdown.get("metadata_ms") or obs.get("latency_metadata_ms"),
            "latency_semantic_ms":   latency_breakdown.get("semantic_ms") or obs.get("latency_semantic_ms"),
            "latency_embedding_ms":  latency_breakdown.get("embedding_ms") or obs.get("latency_embedding_ms"),
            "latency_candidate_ms":  latency_breakdown.get("candidate_ms") or obs.get("latency_candidate_ms"),
            "latency_retrieval_ms":  latency_breakdown.get("retrieval_ms") or obs.get("latency_retrieval_ms"),
            "latency_ranking_ms":    latency_breakdown.get("ranking_ms") or obs.get("latency_ranking_ms"),
            # tokens
            "estimated_input_tokens":  obs.get("estimated_input_tokens"),
            "estimated_output_tokens": obs.get("estimated_output_tokens"),
            "total_tokens":            obs.get("total_tokens"),
            # versioning
            "model_version":     obs.get("model_version"),
            "embedding_model":   obs.get("embedding_model"),
            "retrieval_version": obs.get("retrieval_version"),
            # cache info
            "cache_hit": cache_hit,
            "cache_layer": cache_layer,
            # intent dataset
            "manual_intent_label":    None,
            "manual_relevance_label": None,
            # extra — RIS feature store
            "extra": merged_extra,
        }
        payload.update(_extract_cost(fw_context))
        return payload
