"""Configure loguru logging for the application."""

import sys

from loguru import logger


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    logger.add(
        "logs/app.log",
        rotation="1 MB",
        retention=3,
        encoding="utf-8",
        level="DEBUG",
    )
