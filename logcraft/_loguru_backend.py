"""Loguru logging backend implementation.

This module provides a logging backend using the loguru library.
This is an optional backend that requires loguru to be installed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from loguru import logger as _loguru

    HAS_LOGURU = True
except ImportError:
    HAS_LOGURU = False
    _loguru = None

from logcraft._protocol import LoggerBackend, LoggerProtocol


def _format_extra(fields: dict[str, Any]) -> str:
    """Format extra fields for log output.

    Args:
        fields: Dictionary of field names to values.

    Returns:
        Formatted string representation of the fields.
    """
    parts = []
    for key, value in sorted(fields.items()):
        if isinstance(value, BaseException):
            value = f"{type(value).__name__}: {value}"
        elif isinstance(value, (dict, list, tuple)):
            value = repr(value)[:200]
        elif not isinstance(value, str):
            value = str(value)
        value = value.replace("{", "{{").replace("}", "}}")
        if "\n" in value:
            value = value.replace("\n", "\\n")[:200]
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _log_formatter(record: dict[str, Any]) -> str:
    """Format a log record for output.

    Args:
        record: Log record dictionary from loguru.

    Returns:
        Formatted log string.
    """
    time_str = record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    level = record["level"].name
    pid = record["process"].id
    tid = record["thread"].id
    name = record["name"]
    line = record["line"]
    message = record["message"]
    extra = _format_extra({k: v for k, v in record["extra"].items() if not k.startswith("_")})
    if extra:
        return f"{time_str} || {level} || {pid} || {tid} || {name}:{line} || {message} || {extra}\n"
    return f"{time_str} || {level} || {pid} || {tid} || {name}:{line} || {message}\n"


class LoguruLogger(LoggerProtocol):
    """Logger implementation using loguru.

    This class wraps loguru's logger to conform to LoggerProtocol.
    """

    __slots__ = ("_inner",)

    def __init__(self, inner: Any) -> None:
        """Initialize the LoguruLogger.

        Args:
            inner: The loguru logger instance.
        """
        self._inner = inner

    def debug(self, event_name: str, **fields: Any) -> None:
        """Log a debug message."""
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        lg.debug(event_name)

    def info(self, event_name: str, **fields: Any) -> None:
        """Log an info message."""
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        lg.info(event_name)

    def warning(self, event_name: str, **fields: Any) -> None:
        """Log a warning message."""
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        lg.warning(event_name)

    def error(self, event_name: str, **fields: Any) -> None:
        """Log an error message."""
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        lg.error(event_name)

    def exception(self, event_name: str, **fields: Any) -> None:
        """Log an exception with traceback."""
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        lg.exception(event_name)

    def bind(self, **ctx: Any) -> LoguruLogger:
        """Bind additional context to the logger.

        Args:
            **ctx: Key-value pairs to bind.

        Returns:
            A new LoguruLogger with the bound context.
        """
        return LoguruLogger(self._inner.bind(**ctx))


class LoguruBackend(LoggerBackend):
    """Logging backend using loguru.

    This backend provides logging using the loguru library,
    offering structured logging with better formatting.
    """

    def __init__(self) -> None:
        """Initialize the LoguruBackend."""
        if not HAS_LOGURU:
            raise ImportError(
                "loguru is not installed. Install it with: pip install loguru",
            )
        self._initialized = False

    def get_logger(self, name: str) -> LoguruLogger:
        """Get or create a logger for the specified name.

        Args:
            name: Logger name/module.

        Returns:
            A LoguruLogger instance.
        """
        return LoguruLogger(_loguru.bind(module=name))

    def setup(
        self,
        level: str = "INFO",
        log_dir: str | None = None,
        **options: Any,
    ) -> LoguruLogger:
        """Initialize the loguru logging backend.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            log_dir: Directory for log files.
            **options: Additional options:
                - enable_console: Whether to enable console output (default: True)
                - enable_file: Whether to enable file output (default: True)
                - rotation: Log rotation setting (default: "1 day")
                - retention: Number of rotated files to keep (default: 3)

        Returns:
            The default logger instance.
        """
        if self._initialized:
            return self.get_logger("logcraft")

        _loguru.remove()

        # Console handler
        if options.get("enable_console", True):
            _loguru.add(
                sys.stdout,
                format=_log_formatter,
                level=level.upper(),
                colorize=False,
            )

        # File handler
        if options.get("enable_file", True) and log_dir:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)

            rotation = options.get("rotation", "1 day")
            retention = options.get("retention", 3)

            _loguru.add(
                str(log_path / "logcraft.log"),
                format=_log_formatter,
                level=level.upper(),
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                colorize=False,
            )

        self._initialized = True
        return self.get_logger("logcraft")


# Global backend instance
_loguru_backend: LoguruBackend | None = None


def get_loguru_backend() -> LoguruBackend:
    """Get the global LoguruBackend instance.

    Returns:
        The global LoguruBackend instance.

    Raises:
        ImportError: If loguru is not installed.
    """
    global _loguru_backend
    if _loguru_backend is None:
        _loguru_backend = LoguruBackend()
    return _loguru_backend
