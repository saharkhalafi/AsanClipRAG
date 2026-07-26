# app2/services/query_preprocessor.py

import re
import unicodedata


class QueryPreprocessor:
    """
    Production-grade query normalization for Persian/English RAG systems.
    """

    REPLACEMENTS = {
        "ي": "ی",
        "ك": "ک",
        "ۀ": "ه",
        "ة": "ه",
        "ؤ": "و",
        "إ": "ا",
        "أ": "ا",
        "آ": "ا",

        # common domain typos
        "لوگوموشن": "لوگو موشن",
        "پیج اینستا": "پیج اینستاگرام",
        "استوری اینستا": "استوری اینستاگرام",
        "کلیپ استوری": "استوری",
        "لوگو انیمیشن": "لوگو موشن",
    }

    PERSIAN_DIGITS = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹",
        "0123456789"
    )

    ARABIC_DIGITS = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩",
        "0123456789"
    )

    @classmethod
    def normalize(cls, text: str) -> str:

        if not text:
            return ""

        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # lowercase English
        text = text.lower().strip()

        # remove zero width characters
        text = text.replace("\u200c", " ")
        text = text.replace("\u200f", "")
        text = text.replace("\ufeff", "")

        # normalize digits
        text = text.translate(cls.PERSIAN_DIGITS)
        text = text.translate(cls.ARABIC_DIGITS)

        # character replacements
        for old, new in cls.REPLACEMENTS.items():
            text = text.replace(old, new)

        # remove urls
        text = re.sub(r"http\S+", " ", text)

        # remove emails
        text = re.sub(r"\S+@\S+", " ", text)

        # remove emojis and symbols
        text = re.sub(
            r"[^\w\s\u0600-\u06FF]",
            " ",
            text
        )

        # collapse repeated characters
        # سلاااااام -> سلام
        text = re.sub(r"(.)\1{2,}", r"\1", text)

        # collapse spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()
