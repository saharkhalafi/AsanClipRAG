# app2/builders/response_builder.py
from typing import Dict, Any, List

class ResponseBuilder:
    @staticmethod
    def build(
        query: str,
        filters: Dict,
        semantic: Dict,
        quality: Dict,
        retrieval: Dict,
        results: List[Dict],
        timings: Dict,
        latency_total_ms: float,
        final_mode: str,               
        observability: Dict
    ) -> Dict[str, Any]:
        
        return {
            "mode": final_mode,
            "query": query,
            "filters": filters,
            "semantic": semantic,
            "retrieval_quality": quality,
            "retry_triggered": retrieval.get("retry_triggered", False),
            "attempt_history": retrieval.get("attempt_history", []),
            "candidate_count": len(retrieval.get("candidate_ids", []) or []),
            "bm25_used": bool(final_mode in {"hybrid", "lexical"}),
            "results": results[:5],
            "observability": observability,
        }