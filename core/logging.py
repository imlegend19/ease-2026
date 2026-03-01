"""Compatibility exports for the legacy ``core.logging`` import path."""

from ease2026.core.logging import (
    LoggerKlass,
    bind_logger_contextvars,
    cleanup_duplicate_handlers,
    clear_logger_contextvars,
    get_default_logger,
    get_logger,
    setup_logging,
)

__all__ = [
    "LoggerKlass",
    "get_logger",
    "get_default_logger",
    "bind_logger_contextvars",
    "clear_logger_contextvars",
    "setup_logging",
    "cleanup_duplicate_handlers",
]
