"""
AsanClip RAG - Offline Evaluation Script (Rate-Limit Safe)
----------------------------------------------------------
Measures retrieval quality against a golden dataset.

Metrics:
- Recall@K
- Precision@K
- nDCG@K
- MRR
- Hit Rate@K
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from requests.exceptions import RequestException

_stdout = sys.stdout
if isinstance(_stdout, io.TextIOWrapper):
    _stdout.reconfigure(encoding="utf-8")

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent

API_URL = "http://localhost:8000/api/v1/search"
GOLDEN_PATH = BASE_DIR / "golden_dataset.json"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_PATH = RESULTS_DIR / "eval_report.json"

K_VALUES = [5, 10, 20]
TIMEOUT_SEC = 30
TOP_N_TO_FETCH = 20

# Rate-limit friendly settings
SLEEP_BETWEEN_QUERIES_SEC = 12   # برای limit حدود 5/minute
MAX_RETRIES = 5


# =========================
# LOAD GOLDEN SET
# =========================
def load_golden(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")

    text = path.read_text(encoding="utf-8").strip()

    # Support both .json (array) and .jsonl
    if path.suffix == ".jsonl":
        items = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
        return items

    data = json.loads(text)
    if isinstance(data, list):
        return data

    raise ValueError("Golden dataset must be a JSON array or JSONL file")


# =========================
# CALL SEARCH API (with retry)
# =========================
def search_api(query: str, max_retries: int = MAX_RETRIES, top_k: int = TOP_N_TO_FETCH) -> List[int]:
    """
    Calls AsanClip search endpoint and returns ranked product IDs.
    Handles 429 rate-limit with exponential-style waiting.
    """
    payload = {"query": query, "top_k": top_k}
    headers = {"Content-Type": "application/json"}

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=TIMEOUT_SEC,
            )

            if resp.status_code == 429:
                wait_s = 15 * (attempt + 1)  # 15, 30, 45, ...
                print(f"[RATE LIMIT] waiting {wait_s}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_s)
                continue

            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or []
            ids: List[int] = []

            for item in results[:TOP_N_TO_FETCH]:
                pid = item.get("id")
                if pid is None:
                    continue
                try:
                    ids.append(int(pid))
                except (TypeError, ValueError):
                    continue

            return ids

        except RequestException as e:
            print(f"[ERROR] attempt {attempt + 1}/{max_retries}: {e}")
            time.sleep(3)

    print(f"[FAILED] query: {query[:60]}")
    return []


# =========================
# METRICS
# =========================
def recall_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    if not relevant:
        return 0.0
    hit = len(set(relevant) & set(retrieved[:k]))
    return hit / len(set(relevant))


def precision_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    if k == 0:
        return 0.0
    hit = len(set(relevant) & set(retrieved[:k]))
    return hit / k


def hit_rate_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    return 1.0 if len(set(relevant) & set(retrieved[:k])) > 0 else 0.0


def mrr(relevant: List[int], retrieved: List[int]) -> float:
    relevant_set = set(relevant)
    for rank, pid in enumerate(retrieved, start=1):
        if pid in relevant_set:
            return 1.0 / rank
    return 0.0


def dcg_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    relevant_set = set(relevant)
    score = 0.0
    for i, pid in enumerate(retrieved[:k], start=1):
        rel = 1.0 if pid in relevant_set else 0.0
        score += rel / math.log2(i + 1)
    return score


def ndcg_at_k(relevant: List[int], retrieved: List[int], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = dcg_at_k(relevant, retrieved, k)
    ideal = dcg_at_k(relevant, relevant, k)
    if ideal == 0:
        return 0.0
    return dcg / ideal


# =========================
# EVALUATE ONE QUERY
# =========================
def evaluate_one(item: Dict[str, Any]) -> Dict[str, Any]:
    query = item["query"]
    relevant_ids = [int(x) for x in item.get("relevant_ids", [])]

    t0 = time.perf_counter()
    retrieved_ids = search_api(query)
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    metrics: Dict[str, float] = {
        "mrr": round(mrr(relevant_ids, retrieved_ids), 4),
        "latency_ms": latency_ms,
    }

    for k in K_VALUES:
        metrics[f"recall@{k}"] = round(recall_at_k(relevant_ids, retrieved_ids, k), 4)
        metrics[f"precision@{k}"] = round(precision_at_k(relevant_ids, retrieved_ids, k), 4)
        metrics[f"ndcg@{k}"] = round(ndcg_at_k(relevant_ids, retrieved_ids, k), 4)
        metrics[f"hit_rate@{k}"] = round(hit_rate_at_k(relevant_ids, retrieved_ids, k), 4)

    return {
        "id": item.get("id"),
        "query": query,
        "group": item.get("group"),
        "difficulty": item.get("difficulty"),
        "relevant_ids": relevant_ids,
        "retrieved_ids": retrieved_ids,
        "metrics": metrics,
    }


# =========================
# AGGREGATE
# =========================
def aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {}

    keys = [
        "mrr",
        *[f"recall@{k}" for k in K_VALUES],
        *[f"precision@{k}" for k in K_VALUES],
        *[f"ndcg@{k}" for k in K_VALUES],
        *[f"hit_rate@{k}" for k in K_VALUES],
        "latency_ms",
    ]

    summary = {}
    for key in keys:
        values = [r["metrics"][key] for r in results if key in r["metrics"]]
        summary[key] = round(sum(values) / len(values), 4) if values else 0.0

    # per group
    by_group: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        g = r.get("group") or "unknown"
        by_group.setdefault(g, []).append(r)

    group_summary = {}
    for g, items in by_group.items():
        group_summary[g] = {
            "count": len(items),
            "mrr": round(sum(i["metrics"]["mrr"] for i in items) / len(items), 4),
            "recall@10": round(sum(i["metrics"]["recall@10"] for i in items) / len(items), 4),
            "ndcg@10": round(sum(i["metrics"]["ndcg@10"] for i in items) / len(items), 4),
            "hit_rate@10": round(sum(i["metrics"]["hit_rate@10"] for i in items) / len(items), 4),
        }

    # per difficulty
    by_diff: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        d = r.get("difficulty") or "unknown"
        by_diff.setdefault(d, []).append(r)

    difficulty_summary = {}
    for d, items in by_diff.items():
        difficulty_summary[d] = {
            "count": len(items),
            "mrr": round(sum(i["metrics"]["mrr"] for i in items) / len(items), 4),
            "recall@10": round(sum(i["metrics"]["recall@10"] for i in items) / len(items), 4),
            "ndcg@10": round(sum(i["metrics"]["ndcg@10"] for i in items) / len(items), 4),
            "hit_rate@10": round(sum(i["metrics"]["hit_rate@10"] for i in items) / len(items), 4),
        }

    failed = sum(1 for r in results if not r["retrieved_ids"])
    return {
        "total_queries": len(results),
        "failed_queries": failed,
        "overall": summary,
        "by_group": group_summary,
        "by_difficulty": difficulty_summary,
    }


# =========================
# MAIN
# =========================
def main():
    parser = argparse.ArgumentParser(description="AsanClip offline retrieval evaluation")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only the first N golden queries (0 = all)",
    )
    parser.add_argument(
        "--no-sleep",
        action="store_true",
        help="Skip sleep between queries (local benchmarking only)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("AsanClip Offline Evaluation (Rate-Limit Safe)")
    print("=" * 60)

    golden = load_golden(GOLDEN_PATH)
    if args.limit and args.limit > 0:
        golden = golden[: args.limit]
    print(f"Loaded {len(golden)} golden queries from {GOLDEN_PATH}")
    print(f"Sleep between queries: {SLEEP_BETWEEN_QUERIES_SEC}s")
    print("-" * 60)

    results = []
    for i, item in enumerate(golden, start=1):
        qid = item.get("id")
        qtext = item.get("query", "")[:50]
        print(f"[{i}/{len(golden)}] {qid} | {qtext}")

        row = evaluate_one(item)
        results.append(row)

        m = row["metrics"]
        print(
            f"   MRR={m['mrr']:.3f} | R@10={m['recall@10']:.3f} | "
            f"nDCG@10={m['ndcg@10']:.3f} | Hit@10={m['hit_rate@10']:.3f} | "
            f"{m['latency_ms']}ms | retrieved={len(row['retrieved_ids'])}"
        )

        # مهم: جلوگیری از 429
        if i < len(golden) and not args.no_sleep:
            time.sleep(SLEEP_BETWEEN_QUERIES_SEC)

    summary = aggregate(results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "summary": summary,
        "details": results,
    }
    RESULTS_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    overall = summary["overall"]
    print(f"Queries       : {summary['total_queries']}")
    print(f"Failed        : {summary['failed_queries']}")
    print(f"MRR           : {overall['mrr']:.4f}")
    print(f"Recall@5      : {overall['recall@5']:.4f}")
    print(f"Recall@10     : {overall['recall@10']:.4f}")
    print(f"Precision@10  : {overall['precision@10']:.4f}")
    print(f"nDCG@10       : {overall['ndcg@10']:.4f}")
    print(f"Hit Rate@10   : {overall['hit_rate@10']:.4f}")
    print(f"Avg Latency   : {overall['latency_ms']:.1f} ms")
    print(f"\nReport saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()