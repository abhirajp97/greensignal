"""Structured logging setup for ingestion jobs and API."""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a logger writing JSON-structured lines to stdout."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        ))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
