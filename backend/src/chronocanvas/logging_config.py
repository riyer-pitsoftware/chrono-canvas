"""Structured JSON logging for Cloud Run / Cloud Logging integration.

Cloud Run captures stdout/stderr and sends it to Cloud Logging.
When logs are JSON, Cloud Logging auto-parses fields like `severity`,
`message`, `time`, and `logging.googleapis.com/trace`.

Usage:
    from chronocanvas.logging_config import setup_logging
    setup_logging()  # call once at startup
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from chronocanvas.config import settings


class CloudLoggingFormatter(logging.Formatter):
    """JSON formatter compatible with Google Cloud Logging.

    Maps Python log levels to Cloud Logging severity levels.
    Adds structured fields that Cloud Logging auto-indexes.
    """

    _SEVERITY_MAP = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "severity": self._SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
            "logger": record.name,
        }

        # Add source location for errors
        if record.levelno >= logging.WARNING:
            log_entry["logging.googleapis.com/sourceLocation"] = {
                "file": record.pathname,
                "line": str(record.lineno),
                "function": record.funcName,
            }

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
            log_entry["exception_type"] = type(record.exc_info[1]).__name__

        # Add request_id if present (set by middleware via LogRecord extra)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure logging based on settings.log_format.

    - "json": Structured JSON for Cloud Logging (GCP Cloud Run)
    - "text": Human-readable text for local development
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    # Remove any existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        handler.setFormatter(CloudLoggingFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    # Add request_id correlation filter
    from chronocanvas.api.middleware import RequestIdFilter

    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
