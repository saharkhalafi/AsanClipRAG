import logging
import os
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO"):
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    log_to_file = os.getenv("LOG_TO_FILE", "true").strip().lower() in {"1", "true", "yes"}
    if log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "app.log", encoding="utf-8"))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
        handlers=handlers,
    )

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logger = logging.getLogger("app2")
    logger.info("✅ Logging system initialized successfully")
    return logger
