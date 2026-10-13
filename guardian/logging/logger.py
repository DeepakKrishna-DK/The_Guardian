"""
Guardian Logging System
Provides structured logging for all Guardian components.
Writes both to console (human-readable) and to log files (JSON).
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for a Guardian component.

    Usage:
        from guardian.logging.logger import get_logger
        log = get_logger(__name__)
        log.info("Component started")
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --- Console handler (human-readable) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    logger.addHandler(console_handler)

    return logger


def get_file_logger(name: str, log_dir: Path) -> logging.Logger:
    """
    Return a logger that also writes to a daily log file in log_dir.
    File format: YYYY-MM-DD_guardian.log (plain text, one line per record).
    """
    logger = get_logger(name)

    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"{today}_guardian.log"

    # Check if file handler already added
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            return logger

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    return logger
