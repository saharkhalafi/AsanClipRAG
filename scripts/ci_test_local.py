"""Run the same DB prep + pytest sequence as GitHub Actions Test job."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


def main() -> int:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/asanclip_test",
    )
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("ENABLE_CACHE", "false")
    os.environ.setdefault("ENABLE_PII_DETECTION", "false")
    os.environ.setdefault("PYTHONPATH", ".")

    admin_url = database_url.rsplit("/", 1)[0] + "/postgres"
    db_name = database_url.rsplit("/", 1)[1]

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    subprocess.check_call(["alembic", "upgrade", "head"])
    return subprocess.call([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"])


if __name__ == "__main__":
    raise SystemExit(main())
