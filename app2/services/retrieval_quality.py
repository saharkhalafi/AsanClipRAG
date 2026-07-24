from typing import List, Dict, Any
import numpy as np


class RetrievalQualityModel:

    def compute(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> Dict[str, Any]:

        if not results:
            return {
                "retrieval_quality": 0,
                "decision": "fallback",
                "signals": {}
            }

        query_tokens = set(query.split())

        distances = np.array(
            [r.get("distance", 1.0) for r in results[:10]],
            dtype=np.float32
        )

        sims = 1 / (1 + distances)

        top1 = float(sims[0])

        top2 = float(sims[1]) if len(sims) > 1 else top1

        margin = top1 - top2

        topk_mean = float(np.mean(sims[:5]))

        density = float(
            np.sum(sims > 0.55)
        ) / len(sims)

        # --------------------------------
        # lexical overlap
        # --------------------------------

        best_overlap = 0

        for r in results[:5]:

            text = " ".join([
                str(r.get("name", "")),
                str(r.get("rag_text", ""))
            ])

            doc_tokens = set(text.split())

            overlap = len(
                query_tokens & doc_tokens
            ) / max(len(query_tokens), 1)

            best_overlap = max(
                best_overlap,
                overlap
            )

        # --------------------------------
        # final quality
        # --------------------------------

        retrieval_quality = (
            0.45 * top1 +
            0.20 * density +
            0.20 * best_overlap +
            0.15 * topk_mean
        )

        # --------------------------------
        # routing
        # --------------------------------

        if (
            top1 > 0.65
            and best_overlap > 0.40
        ):
            decision = "vector"

        elif retrieval_quality > 0.50:
            decision = "hybrid"

        else:
            decision = "fallback"

        return {
            "retrieval_quality": float(retrieval_quality),
            "decision": decision,
            "signals": {
                "top1": top1,
                "top2": top2,
                "margin": margin,
                "density": density,
                "topk_mean": topk_mean,
                "overlap": best_overlap
            }
        }