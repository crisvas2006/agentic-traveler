"""
Centralized logging configuration.

Call ``setup_logging()`` once at application startup (e.g. in the CLI
entry-point).  All modules that use ``logging.getLogger(__name__)``
will inherit the configured level and format automatically.
"""

import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """
    Configure the root logger.

    Args:
        verbose: If True, set level to DEBUG and show module names.
                 Otherwise, set to INFO with a compact format.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = (
        "[%(asctime)s] %(levelname)-5s %(name)s — %(message)s"
        if verbose
        else "[%(asctime)s] %(levelname)-5s — %(message)s"
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on repeated calls
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)
