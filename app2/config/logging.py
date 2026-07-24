import logging
import sys
from pathlib import Path

def setup_logging(log_level: str = "INFO"):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
        ]
    )

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logger = logging.getLogger("app2")
    logger.info("✅ Logging system initialized successfully")
    return logger