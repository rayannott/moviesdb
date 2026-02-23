"""Configure loguru logging for the application."""

import sys
from pathlib import Path

from loguru import logger

LOGS_DIR = Path.home() / ".config" / "moviesdb" / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    logger.add(
        LOG_FILE,
        rotation="1 MB",
        retention=3,
        encoding="utf-8",
        level="DEBUG",
    )
