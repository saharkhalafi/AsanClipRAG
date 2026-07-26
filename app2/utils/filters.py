from typing import Any


def normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Converts list-based filters into single values
    for SQL compatibility (Postgres =, not ANY()).
    """

    if not filters:
        return {}

    normalized = {}

    for k, v in filters.items():

        if isinstance(v, list):
            if len(v) > 0:
                normalized[k] = v[0]

        elif v is not None:
            normalized[k] = v

    return normalized
