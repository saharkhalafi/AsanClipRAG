import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app2.db.url import get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "client_encoding": "utf8"
    },
    pool_pre_ping=True,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "2")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10")),
    pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
