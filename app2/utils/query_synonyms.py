"""Domain synonym expansion for Persian catalog queries (no ML cost)."""
from __future__ import annotations

# phrase -> additional search terms appended to query
PHRASE_EXPANSIONS: dict[str, str] = {
    "شب چله": "یلدا",
    "شب یلدا": "یلدا",
    "یلدایی": "یلدا",
    "بچه گانه": "بچگانه کودکانه",
    "جشن تولد": "تولد",
    "روز مامان": "روز مادر",
    "تولدت مبارک": "تولد",
    "تبریک تولد": "تولد",
    "بلک فرایدی": "تخفیف",
    "بلک‌فرایدی": "تخفیف",
}

# typo / variant -> canonical form (applied before tokenization)
NORMALIZATION_MAP: dict[str, str] = {
    "لوگومیشن": "لوگو موشن",
    "لوگوموشن": "لوگو موشن",
    "لوگومشن": "لوگو موشن",
    "بچه گانه": "بچگانه",
    "اینستا": "اینستاگرام",
    "دخترونه": "دختر",
}


def expand_query(query: str) -> str:
    """Append catalog synonyms so metadata/BM25 can match paraphrases."""
    if not query:
        return query

    text = query
    extras: list[str] = []

    for phrase, expansion in PHRASE_EXPANSIONS.items():
        if phrase in text and expansion not in text:
            extras.append(expansion)

    if extras:
        text = f"{text} {' '.join(dict.fromkeys(extras))}"

    return text.strip()


def normalize_variants(query: str) -> str:
    """Fix common typos and colloquial variants."""
    if not query:
        return query

    text = query
    for old, new in NORMALIZATION_MAP.items():
        text = text.replace(old, new)
    return text.strip()
