# app2/services/search_orchestrator.py

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from app2.builders.observability_builder import ObservabilityBuilder
from app2.builders.response_builder import ResponseBuilder
from app2.cache.cache_service import CacheService

# Constants
from app2.config.constants import DEFAULT_TOP_K
from app2.embedding.embedding_service import EmbeddingService

# Centralized Exceptions
from app2.exceptions import DatabaseError, ValidationError
from app2.firewall.semantic_intent import SemanticIntentDetector
from app2.metadata.metadata_extractor import MetadataExtractor
from app2.metadata.metadata_loader import MetadataLoader
from app2.ranking.metadata_boost import MetadataBooster
from app2.ranking.unified_ranker import UnifiedRanker
from app2.retrieval.bm25_search import BM25SearchService
from app2.retrieval.metadata_search import MetadataSearchService
from app2.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from app2.retrieval.vector_search import VectorSearchService
from app2.routing.query_router import QueryRouter
from app2.scorers.query_alignment_scorer import QueryAlignmentScorer
from app2.services.caption_service import CaptionService
from app2.services.query_preprocessor import QueryPreprocessor
from app2.services.retrieval_quality import RetrievalQualityModel
from app2.utils.filters import normalize_filters


class SearchOrchestrator:

    def __init__(self, db, meta: dict[str, Any] | None = None):
        self.db = db
        self.cache = CacheService()

        # ----------------------------
        # CORE
        # ----------------------------
        self.embedder = EmbeddingService()
        self.preprocessor = QueryPreprocessor()

        # ----------------------------
        # METADATA
        # ----------------------------
        if meta is None:
            try:
                meta = MetadataLoader(db).load()
            except Exception as e:
                raise DatabaseError("Failed to load metadata") from e

        self.metadata_extractor = MetadataExtractor(
            product_types=meta["product_types"],
            occasions=meta["occasions"],
            platforms=meta["platforms"],
        )

        self.booster = MetadataBooster(
            product_types=meta["product_types"],
            occasions=meta["occasions"],
            platforms=meta["platforms"],
        )

        # ----------------------------
        # SEMANTIC INTENT
        # ----------------------------
        self.semantic_detector = SemanticIntentDetector(
            catalog={
                "product_types": meta["product_types"],
                "occasions": meta["occasions"],
                "platforms": meta["platforms"],
                "product_names": meta["product_names"],
            },
            sparse_fields=["occasions", "platforms", "product_types"],
            fallback_label_field="product_names",
            embedder=self.embedder,
            db=db
        )

        # ----------------------------
        # RETRIEVAL SERVICES
        # ----------------------------
        self.vector_search = VectorSearchService(db)
        self.bm25_search = BM25SearchService(db)
        self.metadata_search = MetadataSearchService(db)

        # ----------------------------
        # QUALITY + ROUTING + RANKING
        # ----------------------------
        self.rqm = RetrievalQualityModel()
        self.router = QueryRouter()
        self.ranker = UnifiedRanker()

        # ----------------------------
        # RETRIEVAL ORCHESTRATOR
        # ----------------------------
        self.retrieval_orchestrator = RetrievalOrchestrator(
            vector_search=self.vector_search,
            bm25_search=self.bm25_search,
            metadata_search=self.metadata_search,
            quality_model=self.rqm,
            router=self.router,
            max_retries=2,
            quality_threshold=0.55,
            mode_timeouts={
                "vector": 1.50,
                "hybrid": 2.50,
                "lexical": 1.80,
            },
        )

    # =====================================================
    # SAFE HELPERS
    # =====================================================

    def _vector_score(self, distance: float) -> float:
        return max(0.0, 1.0 - float(distance))

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _top_results_snapshot(self, results: list[dict[str, Any]], limit: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        snapshot: list[dict[str, Any]] = []
        for r in results[:limit]:
            snapshot.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "score": self._safe_float(r.get("final_score", r.get("vector_score", 0.0))),
                "source": r.get("source"),
                "product_type": r.get("product_type"),
                "occasion": r.get("occasion"),
                "platform": r.get("platform"),
            })
        return snapshot

    # =====================================================
    # MAIN SEARCH - OPTIMIZED (Parallel + Full Logging)
    # =====================================================
    def search(self, raw_query: str) -> dict[str, Any]:
        t_total = time.perf_counter()
        timings: dict[str, float] = {}

        # 0. Query Result Cache
        if self.cache.enabled:
            cached = self.cache.get_search_result(raw_query)
            if cached:
                if "observability" in cached:
                    cached["observability"]["cache_hit"] = True
                    cached["observability"]["cache_layer"] = "query_result"
                return cached

        # 1. PREPROCESS
        t0 = time.perf_counter()
        try:
            query = self.preprocessor.normalize(raw_query)
        except Exception as e:
            raise ValidationError("Failed to preprocess query") from e

        timings["preprocess_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        if not query:
            observability = {
                "query_raw": raw_query,
                "query_normalized": "",
                "query_length": 0,
                "token_count": 0,
                "filters": {},
                "semantic": None,
                "semantic_best_field": None,
                "semantic_best_score": 0.0,
                "retrieval_quality": None,
                "retrieval_quality_score": 0.0,
                "mode": "empty_query",
                "route_reason": None,
                "candidate_count": 0,
                "retry_triggered": False,
                "attempt_count": 0,
                "attempt_history": [],
                "bm25_used": False,
                "fallback_used": False,
                "result_count": 0,
                "top_result_id": None,
                "top_result_score": None,
                "top_results": [],
                "latency_ms_total": round((time.perf_counter() - t_total) * 1000, 2),
                "latency_breakdown_ms": timings,
                "estimated_input_tokens": 0,
                "estimated_output_tokens": 0,
                "total_tokens": 0,
                "extra": {},
            }
            final_result = {
                "mode": "empty_query",
                "query": "",
                "results": [],
                "observability": observability,
            }
            return final_result

        # 2. PARALLEL STAGE: Metadata + Semantic + Embedding
        t0 = time.perf_counter()

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_meta = executor.submit(self.metadata_extractor.extract, query)
            future_semantic = executor.submit(self.semantic_detector.detect, query)
            future_embedding = executor.submit(self.embedder.embed, query)

            raw_filters = future_meta.result()
            semantic = future_semantic.result()
            query_vector = np.asarray(future_embedding.result(), dtype=np.float32)

        filters = normalize_filters(raw_filters)

        timings["parallel_stage_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # Early Rejection
        semantic_score = float(semantic.get("best_score", 0.0))
        if semantic_score < 0.12 and len(query.split()) > 5:
            observability = {
                "query_raw": raw_query,
                "query_normalized": query,
                "query_length": len(query),
                "token_count": len(query.split()),
                "filters": filters,
                "semantic": semantic,
                "semantic_best_field": semantic.get("best_field"),
                "semantic_best_score": semantic_score,
                "retrieval_quality": None,
                "retrieval_quality_score": 0.0,
                "mode": "invalid_query",
                "route_reason": None,
                "candidate_count": 0,
                "retry_triggered": False,
                "attempt_count": 0,
                "attempt_history": [],
                "bm25_used": False,
                "fallback_used": False,
                "result_count": 0,
                "top_result_id": None,
                "top_result_score": None,
                "top_results": [],
                "latency_ms_total": round((time.perf_counter() - t_total) * 1000, 2),
                "latency_breakdown_ms": timings,
                "estimated_input_tokens": len(query.split()),
                "estimated_output_tokens": 0,
                "total_tokens": len(query.split()),
                "extra": {},
            }
            final_result = {
                "mode": "invalid_query",
                "query": query,
                "filters": filters,
                "semantic": semantic,
                "results": [],
                "observability": observability,
            }
            return final_result

        # 3. CANDIDATES
        t0 = time.perf_counter()
        try:
            candidate_ids = self.metadata_search.search(
                filters=filters,
                query=query,
                semantic=semantic,
                limit=120
            )
        except Exception as e:
            raise DatabaseError("Candidate search failed") from e

        timings["candidate_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        if candidate_ids is not None and len(candidate_ids) == 0:
            candidate_ids = None

        # 4. RETRIEVAL
        t0 = time.perf_counter()
        try:
            retrieval = self.retrieval_orchestrator.run(
                query=query,
                query_vector=query_vector,
                filters=filters,
                semantic=semantic,
                candidate_ids=candidate_ids
            )
        except Exception as e:
            raise DatabaseError("Retrieval failed") from e

        timings["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        results = retrieval["results"]
        quality = retrieval["quality"]
        route = retrieval["route"]
        retry_triggered = retrieval.get("retry_triggered", False)
        attempt_history = retrieval.get("attempt_history", [])
        selected_mode = retrieval.get("mode", "vector")

        # 5. HARD REJECTION
        retrieval_score = float(quality.get("retrieval_quality", 0.0))

        if semantic_score < 0.18 and retrieval_score < 0.32:
            observability = {
                "query_raw": raw_query,
                "query_normalized": query,
                "query_length": len(query),
                "token_count": len(query.split()),
                "filters": filters,
                "semantic": semantic,
                "semantic_best_field": semantic.get("best_field"),
                "semantic_best_score": semantic_score,
                "retrieval_quality": quality,
                "retrieval_quality_score": retrieval_score,
                "mode": "invalid_query",
                "route_reason": getattr(route, "reason", None),
                "candidate_count": len(candidate_ids or []),
                "retry_triggered": retry_triggered,
                "attempt_count": len(attempt_history),
                "attempt_history": attempt_history,
                "bm25_used": bool(selected_mode in {"hybrid", "lexical"}),
                "fallback_used": bool(retry_triggered or selected_mode in {"hybrid", "lexical"}),
                "result_count": 0,
                "top_result_id": None,
                "top_result_score": None,
                "top_results": [],
                "latency_ms_total": round((time.perf_counter() - t_total) * 1000, 2),
                "latency_breakdown_ms": timings,
                "estimated_input_tokens": len(query.split()),
                "estimated_output_tokens": 0,
                "total_tokens": len(query.split()),
                "extra": {
                    "selected_mode": selected_mode,
                    "last_route_mode": retrieval.get("last_route_mode"),
                },
            }
            final_result = {
                "mode": "invalid_query",
                "query": query,
                "filters": filters,
                "semantic": semantic,
                "retrieval_quality": quality,
                "results": [],
                "observability": observability,
            }
            return final_result

        if not results:
            observability = {
                "query_raw": raw_query,
                "query_normalized": query,
                "query_length": len(query),
                "token_count": len(query.split()),
                "filters": filters,
                "semantic": semantic,
                "semantic_best_field": semantic.get("best_field"),
                "semantic_best_score": semantic_score,
                "retrieval_quality": quality,
                "retrieval_quality_score": retrieval_score,
                "mode": "no_results",
                "route_reason": getattr(route, "reason", None),
                "candidate_count": len(candidate_ids or []),
                "retry_triggered": retry_triggered,
                "attempt_count": len(attempt_history),
                "attempt_history": attempt_history,
                "bm25_used": bool(selected_mode in {"hybrid", "lexical"}),
                "fallback_used": bool(retry_triggered or selected_mode in {"hybrid", "lexical"}),
                "result_count": 0,
                "top_result_id": None,
                "top_result_score": None,
                "top_results": [],
                "latency_ms_total": round((time.perf_counter() - t_total) * 1000, 2),
                "latency_breakdown_ms": timings,
                "estimated_input_tokens": len(query.split()),
                "estimated_output_tokens": 0,
                "total_tokens": len(query.split()),
                "extra": {
                    "selected_mode": selected_mode,
                    "last_route_mode": retrieval.get("last_route_mode"),
                },
            }
            final_result = {
                "mode": "no_results",
                "query": query,
                "filters": filters,
                "semantic": semantic,
                "retrieval_quality": quality,
                "retry_triggered": retry_triggered,
                "attempt_history": attempt_history,
                "results": [],
                "observability": observability,
            }
            return final_result

        # 6. BOOST
        t0 = time.perf_counter()
        results = self.booster.boost(results, filters, query)
        timings["metadata_boost_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # 7. RANK
        t0 = time.perf_counter()
        results = self.ranker.rank(
            results=results,
            query_signals={"tokens": query.split(), "filters": filters}
        )
        timings["ranking_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # 8. QUERY ALIGNMENT BOOST
        t0 = time.perf_counter()
        results = QueryAlignmentScorer.apply_boost(results, query, semantic)
        timings["alignment_boost_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        # 9. FINAL MODE
        final_mode = selected_mode
        if quality.get("decision") == "vector":
            final_mode = "vector"
        if not candidate_ids:
            final_mode = selected_mode

        latency_total_ms = round((time.perf_counter() - t_total) * 1000, 2)

        # Observability
        observability = ObservabilityBuilder.build(
            raw_query=raw_query,
            query=query,
            filters=filters,
            semantic=semantic,
            quality=quality,
            retrieval=retrieval,
            results=results,
            timings=timings,
            latency_total_ms=latency_total_ms,
            final_mode=final_mode,
            extra={
                "selected_mode": selected_mode,
                "last_route_mode": retrieval.get("last_route_mode"),
            }
        )

        # Response
        final_result = ResponseBuilder.build(
            query=query,
            filters=filters,
            semantic=semantic,
            quality=quality,
            retrieval=retrieval,
            results=results,
            timings=timings,
            latency_total_ms=latency_total_ms,
            final_mode=final_mode,
            observability=observability
        )

        top_product_ids: list[int] = []
        for item in results[:5]:
            product_id = item.get("id")
            try:
                top_product_ids.append(int(product_id))
            except (TypeError, ValueError):
                continue

        caption_service = CaptionService(self.db)
        suggested_captions = caption_service.get_unique_captions_for_products(
            top_product_ids,
            limit=5,
        )
        if suggested_captions:
            print("Suggested captions:")
            for index, caption in enumerate(suggested_captions, start=1):
                print(f"  {index}. {caption['text']}")

        final_result["suggested_captions"] = suggested_captions

        # Final Cache
        if self.cache.enabled and final_mode not in ["empty_query", "invalid_query", "no_results"]:
            self.cache.set_search_result(raw_query, final_result)

        return final_result
