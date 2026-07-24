from typing import Any


class ScoreNormalizer:

    def normalize_vector(self, distance: float) -> float:
        """
        Convert cosine distance → similarity score
        """
        return max(0.0, 1.0 - float(distance))

    def normalize_lexical(self, score: float) -> float:
        return float(score or 0.0)

    def normalize_metadata(self, boost: float) -> float:
        return float(boost or 0.0)