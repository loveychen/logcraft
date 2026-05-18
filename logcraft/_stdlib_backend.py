"""Standard library logging backend implementation.

This module provides a logging backend using Python's standard logging module.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from logcraft._protocol import LoggerBackend, LoggerProtocol


class StdlibLogger(LoggerProtocol):
    """Logger implementation using standard library logging.

    This class wraps Python's standard logging.Logger to conform
    to the LoggerProtocol.
    """

    __slots__ = ("_inner", "_bound_ctx")

    def __init__(self, inner: logging.Logger, bound_ctx: dict[str, Any] | None = None) -> None:
        """Initialize the StdlibLogger.

        Args:
            inner: The standard library Logger instance.
            bound_ctx: Context bound to this logger instance.
        """
        self._inner = inner
        self._bound_ctx = bound_ctx or {}

    def _format_message(self, event_name: str, **fields: Any) -> str:
        """Format a log message with structured fields.

        Args:
            event_name: Name of the event.
            **fields: Additional fields.

        Returns:
            Formatted message string.
        """
        all_fields = {**self._bound_ctx, **fields}
        if all_fields:
            fields_str = " ".join(f"{k}={repr(v)}" for k, v in sorted(all_fields.items()))
            return f"{event_name} | {fields_str}"
        return event_name

    def debug(self, event_name: str, **fields: Any) -> None:
        """Log a debug message."""
        self._inner.debug(self._format_message(event_name, **fields))

    def info(self, event_name: str, **fields: Any) -> None:
        """Log an info message."""
        self._inner.info(self._format_message(event_name, **fields))

    def warning(self, event_name: str, **fields: Any) -> None:
        """Log a warning message."""
        self._inner.warning(self._format_message(event_name, **fields))

    def error(self, event_name: str, **fields: Any) -> None:
        """Log an error message."""
        self._inner.error(self._format_message(event_name, **fields))

    def exception(self, event_name: str, **fields: Any) -> None:
        """Log an exception with traceback."""
        self._inner.exception(self._format_message(event_name, **fields))

    def bind(self, **ctx: Any) -> StdlibLogger:
        """Bind additional context to the logger.

        Args:
            **ctx: Key-value pairs to bind.

        Returns:
            A new StdlibLogger with the combined context.
        """
        new_ctx = {**self._bound_ctx, **ctx}
        return StdlibLogger(self._inner, new_ctx)


class StdlibBackend(LoggerBackend):
    """Logging backend using Python's standard library.

    This backend provides logging using the built-in logging module,
    making logcraft independent of any third-party logging framework.
    """

    def __init__(self) -> None:
        """Initialize the StdlibBackend."""
        self._initialized = False

    def get_logger(self, name: str) -> StdlibLogger:
        """Get or create a logger for the specified name.

        Args:
            name: Logger name/module.

        Returns:
            A StdlibLogger instance.
        """
        logger = logging.getLogger(name)
        return StdlibLogger(logger)

    def setup(
        self,
        level: str = "INFO",
        log_dir: str | None = None,
        **options: Any,
    ) -> StdlibLogger:
        """Initialize the standard library logging backend.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            log_dir: Directory for log files.
            **options: Additional options:
                - format: Custom log format string
                - datefmt: Date format string
                - enable_console: Whether to enable console output (default: True)
                - enable_file: Whether to enable file output (default: True)

        Returns:
            The root logger instance.
        """
        if self._initialized:
            return self.get_logger("logcraft")

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Setup format
        fmt = options.get(
            "format", "%(asctime)s || %(levelname)s || %(process)d || %(thread)d || %(name)s:%(lineno)d || %(message)s"
        )
        datefmt = options.get("datefmt", "%Y-%m-%d %H:%M:%S")
        formatter = logging.Formatter(fmt, datefmt=datefmt)

        # Console handler
        if options.get("enable_console", True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # File handler
        if options.get("enable_file", True) and log_dir:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(
                log_path / "logcraft.log",
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        self._initialized = True
        return self.get_logger("logcraft")


# Global backend instance
_stdlib_backend: StdlibBackend | None = None


def get_stdlib_backend() -> StdlibBackend:
    """Get the global StdlibBackend instance.

    Returns:
        The global StdlibBackend instance.
    """
    global _stdlib_backend
    if _stdlib_backend is None:
        _stdlib_backend = StdlibBackend()
    return _stdlib_backend
