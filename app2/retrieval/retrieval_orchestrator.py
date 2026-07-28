# app2/retrieval/retrieval_orchestrator.py

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np


class RetrievalOrchestrator:
    """
    Production-safe retrieval controller with parallel execution and smart retry.
    """

    def __init__(
        self,
        vector_search,
        bm25_search,
        metadata_search,
        quality_model,
        router,
        max_retries: int = 2,
        quality_threshold: float = 0.55,
        mode_timeouts: dict[str, float] | None = None,
    ):
        self.vector_search = vector_search
        self.bm25_search = bm25_search
        self.metadata_search = metadata_search
        self.rqm = quality_model
        self.router = router
        self.max_retries = max(0, int(max_retries))
        self.quality_threshold = float(quality_threshold)
        self.mode_timeouts = mode_timeouts or {
            "vector": 1.50,
            "hybrid": 2.50,
            "lexical": 1.80,
        }

    # -------------------------------------------------
    # MODE HELPERS
    # -------------------------------------------------
    def _next_mode(self, current_mode: str, router_mode: str | None = None) -> str:
        current_mode = (current_mode or "vector").lower()
        router_mode = (router_mode or "").lower()
        if current_mode == "vector":
            if router_mode in {"hybrid", "lexical"} and router_mode != "vector":
                return router_mode
            return "hybrid"
        if current_mode == "hybrid":
            return "lexical"
        return "lexical"

    def _mode_budget(self, mode: str) -> float:
        return float(self.mode_timeouts.get((mode or "vector").lower(), 2.0))

    def _normalize_vector_result(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        distance = float(item.get("distance", 1.0))
        vector_score = max(0.0, 1.0 - distance)
        item["vector_score"] = float(vector_score)
        item["bm25_score"] = float(item.get("bm25_score", 0.0))
        item["final_score"] = float(item.get("final_score", vector_score))
        item["source"] = item.get("source", "vector")
        return item

    def _normalize_bm25_result(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["vector_score"] = float(item.get("vector_score", 0.0))
        item["bm25_score"] = float(item.get("bm25_score", 0.0))
        item["final_score"] = float(item.get("final_score", item["bm25_score"]))
        item["source"] = item.get("source", "bm25")
        return item

    def _merge_vector_bm25(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        bm25_rescue_limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Hybrid merge — vector primary, BM25 rescues lexical-only hits."""
        if not vector_results and not bm25_results:
            return []

        normalized_vec = [self._normalize_vector_result(r) for r in vector_results]
        normalized_bm25 = [self._normalize_bm25_result(r) for r in bm25_results]

        bm25_map = {r["id"]: r for r in normalized_bm25 if r.get("id") is not None}
        max_bm25 = max((r.get("bm25_score", 0.0) for r in normalized_bm25), default=0.0) or 1.0

        merged: list[dict[str, Any]] = []
        seen_ids = set()

        for r in normalized_vec:
            doc_id = r.get("id")
            if doc_id is None:
                continue
            seen_ids.add(doc_id)
            vector_score = float(r.get("vector_score", 0.0))
            raw_bm25 = float(bm25_map.get(doc_id, {}).get("bm25_score", 0.0))
            bm25_norm = raw_bm25 / max_bm25
            lexical_score = bm25_norm
            final_score = (0.72 * vector_score) + (0.28 * bm25_norm)
            merged.append({
                **r,
                "vector_score": vector_score,
                "bm25_score": raw_bm25,
                "lexical_score": lexical_score,
                "final_score": final_score,
                "source": r.get("source", "vector"),
            })

        bm25_only = [r for r in normalized_bm25 if r.get("id") not in seen_ids]
        bm25_only.sort(key=lambda x: x.get("bm25_score", 0.0), reverse=True)

        for r in bm25_only[:bm25_rescue_limit]:
            raw_bm25 = float(r.get("bm25_score", 0.0))
            bm25_norm = raw_bm25 / max_bm25
            merged.append({
                **r,
                "vector_score": 0.0,
                "bm25_score": raw_bm25,
                "lexical_score": bm25_norm,
                "final_score": 0.40 * bm25_norm,
                "source": "bm25",
            })

        merged.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        return merged

    @staticmethod
    def _lexical_signal(bm25_results: list[dict[str, Any]]) -> dict[str, float]:
        if not bm25_results:
            return {"top_score": 0.0}
        top = max(float(r.get("bm25_score", 0.0)) for r in bm25_results)
        # Normalize ts_rank / ILIKE scores into router-friendly 0..1 range
        return {"top_score": min(1.0, top / 2.0) if top > 1.0 else top}

    # -------------------------------------------------
    # PARALLEL MODE EXECUTION
    # -------------------------------------------------
    def _run_parallel_modes(
        self,
        query: str,
        query_vector: np.ndarray,
        filters: dict[str, Any],
        candidate_ids: list[int] | None,
    ) -> dict[str, Any]:
        """Run vector + BM25 in parallel"""
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_vector = executor.submit(
                self.vector_search.search,
                query_vector=query_vector,
                candidate_ids=candidate_ids,
                limit=80,
            )
            future_bm25 = executor.submit(
                self.bm25_search.search,
                query=query,
                limit=80,
                filters=filters,
                candidate_ids=candidate_ids,
            )

            vec_results = future_vector.result()
            bm25_results = future_bm25.result()

        return {
            "vector": [self._normalize_vector_result(r) for r in vec_results],
            "bm25": [self._normalize_bm25_result(r) for r in bm25_results],
        }

    # -------------------------------------------------
    # MAIN RETRIEVAL PIPELINE
    # -------------------------------------------------
    def run(
        self,
        query: str,
        query_vector: np.ndarray,
        filters: dict[str, Any],
        semantic: dict[str, Any],
        candidate_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        started_at = time.monotonic()
        attempt_history: list[dict[str, Any]] = []
        current_mode = "vector"
        best_bundle: dict[str, Any] | None = None
        last_quality: dict[str, Any] = {}
        last_route = None

        for attempt_idx in range(self.max_retries + 1):
            if (time.monotonic() - started_at) > self._mode_budget(current_mode):
                break

            mode_started = time.monotonic()

            # Parallel Vector + BM25
            if current_mode in ("vector", "hybrid"):
                parallel_results = self._run_parallel_modes(
                    query=query,
                    query_vector=query_vector,
                    filters=filters,
                    candidate_ids=candidate_ids,
                )

                if current_mode == "vector":
                    results = parallel_results["vector"]
                else:
                    results = self._merge_vector_bm25(
                        parallel_results["vector"],
                        parallel_results["bm25"],
                    )
            else:  # lexical
                bm25_results = self.bm25_search.search(
                    query=query,
                    limit=80,
                    filters=filters,
                    candidate_ids=candidate_ids,
                )
                results = [self._normalize_bm25_result(r) for r in bm25_results]

            mode_elapsed = time.monotonic() - mode_started

            lexical_signal = self._lexical_signal(
                parallel_results["bm25"] if current_mode in ("vector", "hybrid") else results
            )

            quality = self.rqm.compute(results=results, query=query)
            route = self.router.route(
                query=query,
                retrieval_quality=quality,
                filters=filters,
                lexical_signal=lexical_signal,
            )

            score = float(quality.get("retrieval_quality", 0.0))

            attempt_entry = {
                "attempt": attempt_idx,
                "mode": current_mode,
                "result_count": len(results),
                "quality": quality,
                "route_mode": getattr(route, "mode", None),
                "route_reason": getattr(route, "reason", None),
                "elapsed_sec": round(mode_elapsed, 6),
            }
            attempt_history.append(attempt_entry)

            bundle = {
                "mode": current_mode,
                "results": results,
                "quality": quality,
                "route": route,
                "score": score,
                "attempt": attempt_idx,
                "elapsed_sec": mode_elapsed,
            }

            if best_bundle is None or score > best_bundle["score"]:
                best_bundle = bundle

            last_quality = quality
            last_route = route

            if score >= self.quality_threshold:
                break

            if attempt_idx >= self.max_retries:
                break

            next_mode = self._next_mode(current_mode, getattr(route, "mode", None))
            if next_mode == current_mode:
                break
            current_mode = next_mode

        if best_bundle is None:
            best_bundle = {
                "mode": "vector",
                "results": [],
                "quality": {"retrieval_quality": 0.0, "decision": "fallback", "signals": {}},
                "route": None,
                "score": 0.0,
                "attempt": 0,
                "elapsed_sec": 0.0,
            }

        return {
            "mode": best_bundle["mode"],
            "results": best_bundle["results"],
            "quality": best_bundle["quality"],
            "route": best_bundle["route"],
            "retry_triggered": len(attempt_history) > 1,
            "attempt_history": attempt_history,
            "attempt_count": len(attempt_history),
            "best_score": best_bundle["score"],
            "last_quality": last_quality,
            "last_route_mode": getattr(last_route, "mode", None),
        }
