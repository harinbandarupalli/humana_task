"""Logging configuration module."""

import logging
import sys
try:
    from src.orchestrator.config import settings
except ImportError:
    class _FallbackSettings:
        LOG_LEVEL = "INFO"
    settings = _FallbackSettings()


def setup_logger(name: str = "orchestrator") -> logging.Logger:
    """Configures structured standard logging for orchestrator."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    return logger


logger = setup_logger()
