"""Prepare PostgreSQL for the app container: extensions, migrations, optional import."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def wait_for_database(url: str, retries: int = 30, delay: float = 2.0) -> None:
    engine = create_engine(url)
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"PostgreSQL is ready (attempt {attempt}/{retries})")
            return
        except OperationalError as exc:
            print(f"Waiting for PostgreSQL... ({attempt}/{retries}): {exc}")
            time.sleep(delay)
    raise RuntimeError("PostgreSQL did not become ready in time")


def ensure_extensions(url: str) -> None:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    print("PostgreSQL extensions verified (vector, pg_trgm)")


def run_migrations() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Alembic migrations applied")


def get_product_count(url: str) -> int:
    engine = create_engine(url)
    with engine.connect() as conn:
        try:
            return conn.execute(text("SELECT COUNT(*) FROM asanclipproducts")).scalar_one()
        except ProgrammingError:
            return 0


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes")


def get_caption_count(url: str) -> int:
    engine = create_engine(url)
    with engine.connect() as conn:
        try:
            return conn.execute(text("SELECT COUNT(*) FROM product_captions")).scalar_one()
        except ProgrammingError:
            return 0


def maybe_import_sale1404(url: str) -> None:
    if not env_flag("AUTO_IMPORT_SALE1404", default=True):
        print("Skipping Sale1404 import (AUTO_IMPORT_SALE1404=false)")
        return

    sql_path = Path(os.getenv("SALE1404_SQL_PATH", "Sale1404.sql"))
    if not sql_path.exists():
        print(f"Sale1404 dump not found at {sql_path}; skipping import")
        return

    min_products = int(os.getenv("MIN_PRODUCTS_FOR_IMPORT", "100"))
    count = get_product_count(url)
    if count >= min_products:
        print(f"Database already has {count} products; skipping Sale1404 import")
        return

    print(f"Database has {count} products; importing from {sql_path}...")
    cmd = [sys.executable, "scripts/import_sale1404_products.py", "--sql-file", str(sql_path)]
    if count > 0:
        cmd.append("--truncate")
    subprocess.run(cmd, check=True)


def maybe_import_captions(url: str) -> None:
    if not env_flag("AUTO_IMPORT_SALE1404", default=True):
        return

    sql_path = Path(os.getenv("SALE1404_SQL_PATH", "Sale1404.sql"))
    if not sql_path.exists():
        return

    if get_product_count(url) == 0:
        print("Skipping caption import because products table is empty")
        return

    caption_count = get_caption_count(url)
    if caption_count > 0:
        print(f"Database already has {caption_count} captions; skipping caption import")
        return

    print("Importing product captions from Sale1404.sql...")
    subprocess.run(
        [
            sys.executable,
            "scripts/import_sale1404_products.py",
            "--sql-file",
            str(sql_path),
            "--captions-only",
        ],
        check=True,
    )


def maybe_seed_sample_data(url: str) -> None:
    if not env_flag("SEED_DATABASE", default=False):
        print("Skipping sample seed (SEED_DATABASE=false)")
        return

    if get_product_count(url) > 0:
        print("Database already contains products; skipping sample seed")
        return

    print("Database is empty; loading sample products...")
    subprocess.run([sys.executable, "scripts/seed_data.py"], check=True)


def main() -> int:
    url = get_database_url()
    wait_for_database(url)
    ensure_extensions(url)
    run_migrations()
    maybe_import_sale1404(url)
    maybe_import_captions(url)
    maybe_seed_sample_data(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
