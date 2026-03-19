"""Structured logging setup and helpers."""
import logging
import os
import sys
from pathlib import Path

import structlog
from structlog import contextvars as struct_contextvars
from structlog.stdlib import ProcessorFormatter

from app.core.timezone import now_dhaka


def _dhaka_timestamper(_logger, _method_name, event_dict):
    """Attach an ISO timestamp in Asia/Dhaka (+06:00)."""
    event_dict["timestamp"] = now_dhaka().isoformat(timespec="microseconds")
    return event_dict


def setup_logging() -> None:
    """Configure structlog + stdlib logging to write all logs into log/backend.log."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Ensure log directory exists at project root: ./log/backend.log
    log_dir = Path(__file__).resolve().parents[3] / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    formatter = ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer()
        if sys.stderr.isatty()
        else structlog.processors.JSONRenderer(),
        foreign_pre_chain=[
            struct_contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _dhaka_timestamper,
        ],
    )

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    structlog.configure(
        processors=[
            struct_contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            _dhaka_timestamper,
            ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    """Return a structured logger bound to a module or component name."""
    if name:
        return structlog.get_logger(name=name)
    return structlog.get_logger()

