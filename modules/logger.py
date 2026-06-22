"""Structured logger for the project.

Provides a convenience get_logger(name) that returns a configured
logging.Logger using Rich's RichHandler for pretty console output and a
RotatingFileHandler for file logs. Keep configuration minimal and safe for
tests (no external side effects).
"""
from logging import Logger, getLogger, Formatter, INFO
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from rich.logging import RichHandler
except Exception:
    RichHandler = None  # type: ignore


def get_logger(name: str = "heimerdinger", log_file: str = "logs/app.log") -> Logger:
    """Return a configured logger.

    - Uses RichHandler if available for console output.
    - Adds a RotatingFileHandler writing to logs/app.log for persistent logs.
    """
    logger = getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(INFO)

    # Console handler — prefer RichHandler when available
    if RichHandler is not None:
        ch = RichHandler(rich_tracebacks=True)
        ch.setLevel(INFO)
        ch.setFormatter(Formatter("%(message)s"))
    else:
        ch = logging.StreamHandler()
        ch.setLevel(INFO)
        ch.setFormatter(Formatter("[%(levelname)s] %(message)s"))

    logger.addHandler(ch)

    # File handler (rotating)
    try:
        p = Path(log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(str(p), maxBytes=10 * 1024 * 1024, backupCount=3)
        fh.setLevel(INFO)
        fh.setFormatter(Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
        logger.addHandler(fh)
    except Exception:
        # If file handler cannot be created, continue without it
        pass

    # Avoid propagation to root handlers
    logger.propagate = False
    return logger
