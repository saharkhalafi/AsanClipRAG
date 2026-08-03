"""Normalize DATABASE_URL for sync SQLAlchemy + Cloud SQL."""
from __future__ import annotations

import os
import re


def normalize_database_url(url: str) -> str:
    if not url:
        return url

    url = url.strip()

    # Cloud Run secrets may store asyncpg URLs; the app uses sync SQLAlchemy.
    return re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set in environment variables")
    return normalize_database_url(url)
