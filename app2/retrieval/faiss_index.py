import pickle
from pathlib import Path
from typing import Any

import numpy as np
from app2.config.constants import EMBEDDING_DIMENSION, FAISS_INDEX_PATH

_shared_faiss: "FaissIndex | None" = None


def _faiss_module():
    import faiss

    return faiss


def get_faiss_index(
    dimension: int | None = None,
    index_path: str | None = None,
) -> "FaissIndex":
    """Return a process-wide FAISS index (loaded once)."""
    global _shared_faiss
    if _shared_faiss is None:
        _shared_faiss = FaissIndex(
            dimension=dimension or EMBEDDING_DIMENSION,
            index_path=index_path or FAISS_INDEX_PATH,
        )
        _shared_faiss.load_index()
    return _shared_faiss



class FaissIndex:
    def __init__(
        self,
        dimension: int = EMBEDDING_DIMENSION,
        index_path: str = FAISS_INDEX_PATH,
    ):
        self.dimension = dimension
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        self.index: Any | None = None
        self.id_map: dict[int, int] = {}
        self.reverse_map: dict[int, int] = {}

    # =====================================================
    # BUILD INDEX
    # =====================================================
    def build_index(self, embeddings: np.ndarray, product_ids: list[int]):
        """
        ساخت FAISS index
        embeddings: shape = (n, dimension)
        """

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dim mismatch: got {embeddings.shape[1]}, expected {self.dimension}"
            )

        faiss = _faiss_module()

        # normalize برای cosine similarity
        faiss.normalize_L2(embeddings)

        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings.astype(np.float32))

        # mapping
        self.id_map = {pid: i for i, pid in enumerate(product_ids)}
        self.reverse_map = {i: pid for pid, i in self.id_map.items()}

        # save index
        faiss.write_index(self.index, str(self.index_path))

        with open(self.index_path.with_suffix(".pkl"), "wb") as f:
            pickle.dump(self.id_map, f)

        print(f"FAISS index built with {len(product_ids)} vectors")

    # =====================================================
    # LOAD INDEX
    # =====================================================
    def load_index(self):
        """Load index from disk"""
        if self.index_path.exists():
            faiss = _faiss_module()
            self.index = faiss.read_index(str(self.index_path))

            with open(self.index_path.with_suffix(".pkl"), "rb") as f:
                self.id_map = pickle.load(f)

            self.reverse_map = {i: pid for pid, i in self.id_map.items()}

    # =====================================================
    # SEARCH
    # =====================================================
    def search(self, query_vector: np.ndarray, k: int = 50) -> list[tuple[int, float]]:
        """
        جستجوی nearest neighbors
        return: List[(product_id, similarity)]
        """

        if self.index is None:
            self.load_index()

        if self.index is None:
            raise RuntimeError("❌ FAISS index is not loaded")

        query_vector = np.array(query_vector, dtype=np.float32).reshape(1, -1)

        if query_vector.shape[1] != self.dimension:
            raise ValueError(
                f"Query dim mismatch: got {query_vector.shape[1]}, expected {self.dimension}"
            )

        faiss = _faiss_module()

        # normalize برای cosine similarity
        faiss.normalize_L2(query_vector)

        distances, indices = self.index.search(query_vector, k)

        results: list[tuple[int, float]] = []

        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue

            product_id = self.reverse_map.get(int(idx))
            if product_id is None:
                continue

            # cosine similarity (IP after normalization)
            similarity = float(dist)

            results.append((product_id, similarity))

        return results
