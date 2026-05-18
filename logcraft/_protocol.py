"""Logging protocol for framework-agnostic logging.

This module defines the logging protocol that allows logcraft to work
with any logging backend (loguru, standard logging, custom implementations).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LoggerProtocol(Protocol):
    """Protocol defining the logging interface.

    Any logging backend must implement this protocol to be used with logcraft.
    """

    def debug(self, event_name: str, **fields: Any) -> None:
        """Log a debug message.

        Args:
            event_name: Name of the event being logged.
            **fields: Additional fields to include in the log.
        """
        ...

    def info(self, event_name: str, **fields: Any) -> None:
        """Log an info message.

        Args:
            event_name: Name of the event being logged.
            **fields: Additional fields to include in the log.
        """
        ...

    def warning(self, event_name: str, **fields: Any) -> None:
        """Log a warning message.

        Args:
            event_name: Name of the event being logged.
            **fields: Additional fields to include in the log.
        """
        ...

    def error(self, event_name: str, **fields: Any) -> None:
        """Log an error message.

        Args:
            event_name: Name of the event being logged.
            **fields: Additional fields to include in the log.
        """
        ...

    def exception(self, event_name: str, **fields: Any) -> None:
        """Log an exception with traceback.

        Args:
            event_name: Name of the event being logged.
            **fields: Additional fields to include in the log.
        """
        ...

    def bind(self, **ctx: Any) -> LoggerProtocol:
        """Bind additional context to the logger.

        Args:
            **ctx: Key-value pairs to bind to the logger context.

        Returns:
            A new logger instance with the bound context.
        """
        ...


class LoggerBackend(Protocol):
    """Protocol for logger backend initialization.

    A backend is responsible for creating logger instances and
    initializing the logging infrastructure.
    """

    def get_logger(self, name: str) -> LoggerProtocol:
        """Get or create a logger for the specified name.

        Args:
            name: Logger name/module.

        Returns:
            A LoggerProtocol instance.
        """
        ...

    def setup(
        self,
        level: str = "INFO",
        log_dir: str | None = None,
        **options: Any,
    ) -> LoggerProtocol:
        """Initialize the logging backend.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            log_dir: Directory for log files.
            **options: Backend-specific options.

        Returns:
            The default logger instance.
        """
        ...
