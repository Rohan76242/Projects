"""Z3RO / SOBIA — Production Structured Logger.

Provides colorized console output and persistent file logging into logs/assistant.log.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from z3ro.config import config


# ANSI Color Codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class ColoredFormatter(logging.Formatter):
    """Custom log formatter adding ANSI colors for console display."""

    FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    DATE_FORMAT = "%H:%M:%S"

    LEVEL_COLORS = {
        logging.DEBUG: Colors.DIM + Colors.WHITE,
        logging.INFO: Colors.CYAN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED + Colors.BOLD,
        logging.CRITICAL: Colors.RED + Colors.BOLD,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
        timestamp = self.formatTime(record, self.DATE_FORMAT)
        msg = record.getMessage()
        return f"{Colors.DIM}{timestamp}{Colors.RESET} {color}[{record.levelname:<5}]{Colors.RESET} {msg}"


def setup_logger(name: str = "assistant") -> logging.Logger:
    """Configure and return a structured logger."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    # Console Handler (colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    # File Handler (rotating log in logs/assistant.log)
    try:
        log_file = config.LOG_DIR / "assistant.log"
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize file logging: {e}")

    logger.propagate = False
    return logger


# Global default logger
logger = setup_logger("z3ro")
