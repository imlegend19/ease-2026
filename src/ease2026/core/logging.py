"""
Structured logging helpers for experiment scripts.

This module configures stdlib logging with structlog and provides
contextvars helpers for request/run-scoped fields.
"""

__all__ = [
    "LoggerKlass",
    "get_logger",
    "get_default_logger",
    "bind_logger_contextvars",
    "clear_logger_contextvars",
    "setup_logging",
    "cleanup_duplicate_handlers",
]

import logging
import sys
from collections.abc import Callable, Mapping
from contextvars import Token
from pathlib import Path
from typing import Any

import structlog
from structlog import BoundLogger

LoggerKlass = BoundLogger


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name=name)


def get_default_logger(name: str, level: int | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger


def setup_logging(debug: bool = False, log_file_path: str | None = None) -> None:
    root_level = logging.DEBUG if debug else logging.INFO

    pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=pre_chain,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    handlers: list[logging.Handler] = [console_handler]

    if log_file_path is not None:
        target = Path(log_file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=pre_chain,
        )
        file_handler = logging.FileHandler(target)
        file_handler.setFormatter(json_formatter)
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)
    root_logger.handlers = handlers

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(root_level),
        cache_logger_on_first_use=True,
    )

    get_logger("ease2026.core.logging").info(
        "Logging configured",
        level=logging.getLevelName(root_level),
    )


def cleanup_duplicate_handlers() -> None:
    for logger_name in list(logging.root.manager.loggerDict.keys()):
        if logger_name:
            child_logger = logging.getLogger(logger_name)
            child_logger.handlers = []
            child_logger.propagate = True

    get_logger("ease2026.core.logging").debug("Duplicate handlers cleaned up")


bind_logger_contextvars: Callable[[Any], Mapping[str, Token]] = (
    structlog.contextvars.bind_contextvars
)
clear_logger_contextvars: Callable[[], None] = structlog.contextvars.clear_contextvars

