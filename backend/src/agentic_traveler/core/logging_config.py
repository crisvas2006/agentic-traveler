"""
Centralized logging configuration.

Call ``setup_logging()`` once at application startup (e.g. in the CLI
entry-point).  All modules that use ``logging.getLogger(__name__)``
will inherit the configured level and format automatically.
"""

import logging
import sys

try:
    import colorama
    colorama.init()
except ImportError:
    colorama = None

class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""
    
    if colorama:
        COLORS = {
            logging.DEBUG: colorama.Fore.CYAN,
            logging.INFO: colorama.Fore.GREEN,
            logging.WARNING: colorama.Fore.YELLOW,
            logging.ERROR: colorama.Fore.RED,
            logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
        }
        RESET = colorama.Style.RESET_ALL
    else:
        COLORS = {}
        RESET = ""

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        reset = self.RESET if color else ""
        
        # Colorize the level name
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


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
    handler.setFormatter(ColorFormatter(fmt, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers on repeated calls
    root.handlers = [handler]

    # Quiet noisy third-party loggers
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
