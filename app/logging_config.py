"""Centralized logging setup.

The application only writes to stdout. Capture, storage and rotation are the
service manager's job.
"""

import logging
import os
import sys

from app.config import settings

CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
JOURNAL_FORMAT = "%(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

QUIET_LIBRARIES = ("httpx", "httpcore", "msal", "urllib3")


def _running_under_journald() -> bool:
    return "JOURNAL_STREAM" in os.environ


def setup_logging() -> None:
    """Configure the root logger. Safe to call more than once."""
    root = logging.getLogger()
    if any(getattr(handler, "_configured_by_app", False) for handler in root.handlers):
        return

    if _running_under_journald():
        formatter = logging.Formatter(JOURNAL_FORMAT)
    else:
        formatter = logging.Formatter(CONSOLE_FORMAT, datefmt=DATE_FORMAT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler._configured_by_app = True

    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    for name in QUIET_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
