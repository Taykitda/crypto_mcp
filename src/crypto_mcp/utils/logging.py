"""Observability and logging utilities.

CRITICAL: MCP uses stdio for JSON-RPC communication.
All logging MUST go to sys.stderr to avoid breaking the protocol stream.
"""

import logging
import sys

logger = logging.getLogger("crypto_mcp")


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure logger to strictly use stderr."""
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger


# Initialize default logger on import
setup_logging()
