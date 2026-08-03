from logging.config import fileConfig
import os
import re
from urllib.parse import unquote

from sqlalchemy import create_engine, pool

from alembic import context


# ======================
# Alembic Config
# ======================
config = context.config


# ======================
# Logging
# ======================
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ======================
# Import Models
# ======================
from app2.db.base import Base
from app2.db.models import *  # noqa: F401,F403


target_metadata = Base.metadata


# ======================
# Database URL
# ======================
def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        return (
            "postgresql+psycopg2://"
            "postgres:postgres@127.0.0.1:5434/"
            "Sale1404"
        )

    # Cloud Run / Secret Manager often stores asyncpg URLs; Alembic uses sync drivers.
    url = re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", url)

    # Cloud SQL unix socket form: postgresql://user:pass@/db?host=/cloudsql/...
    match = re.match(
        r"^postgresql\+psycopg2://([^:]+):([^@]+)@/?([^?]+)\?host=/cloudsql/.+",
        url,
    )
    if match:
        user, password, db = match.groups()
        host = os.getenv("CLOUDSQL_PROXY_HOST", "127.0.0.1")
        port = os.getenv("CLOUDSQL_PROXY_PORT", "5432")
        return (
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db.lstrip('/')}"
        )

    return url


DATABASE_URL = get_database_url()


# ======================
# Offline Migration
# ======================
def run_migrations_offline() -> None:
    url = DATABASE_URL
    if not url:
        raise RuntimeError("Database URL is missing")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
    )

    with context.begin_transaction():
        context.run_migrations()


# ======================
# Online Migration
# ======================
def run_migrations_online() -> None:
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ======================
# Run
# ======================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()