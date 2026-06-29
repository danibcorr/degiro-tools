# Standard libraries
import logging
from typing import Final

# Name of the single application-wide logger built at the CLI entry
# point and injected through the call chain instead of relying on
# module-global loggers.
APP_LOGGER_NAME: Final[str] = "degiro_tools"

# Log line format shared by every CLI invocation.
_LOG_FORMAT: Final[str] = "%(levelname)s: %(message)s"


def build_logger(*, verbose: bool = False) -> logging.Logger:
    """
    Build and configure the application logger.

    Creates (or retrieves) the single ``degiro_tools`` logger, attaches
    a stream handler exactly once, and sets its level from the
    verbosity flag. The returned logger is meant to be injected through
    the call chain rather than fetched ad hoc in each module.

    Args:
        verbose: When True, lower the threshold to DEBUG; otherwise
            INFO.

    Returns:
        The configured application logger.
    """

    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)

    return logger
