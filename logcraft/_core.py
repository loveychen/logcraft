"""Core implementation for logcraft.

This module provides the core logging infrastructure including:
- log_calls: Decorator for automatic function/method logging
- log_class: Decorator for automatic class method logging
- LogContext: Context manager for scoped logging
- Backend-agnostic logging support
"""

from __future__ import annotations

import functools
import inspect
import os
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

from logcraft._protocol import LoggerProtocol
from logcraft._stdlib_backend import StdlibBackend, get_stdlib_backend

# Optional loguru support
try:
    from logcraft._loguru_backend import LoguruBackend, get_loguru_backend

    HAS_LOGURU = True
except ImportError:
    LoguruBackend = None
    get_loguru_backend = None
    HAS_LOGURU = False

DEFAULT_LOGGER_NAME = "logcraft"
DEFAULT_LOG_DIR = os.getenv("LOGCRAFT_LOG_DIR", "logs")

# Global backend instance
_backend: StdlibBackend | LoguruBackend | None = None
_initialized = False


def _get_current_backend() -> StdlibBackend | LoguruBackend:
    """Get the current backend, initializing if needed.

    Returns:
        The current logging backend.
    """
    global _backend, _initialized
    if _backend is None:
        # Default to stdlib backend
        _backend = get_stdlib_backend()
    return _backend


def _set_backend(backend_type: str = "stdlib") -> None:
    """Set the logging backend (internal function).

    Args:
        backend_type: Backend type - "stdlib" or "loguru".

    Raises:
        ImportError: If loguru backend is requested but not installed.
        ValueError: If unknown backend type is specified.
    """
    global _backend, _initialized

    if backend_type == "stdlib":
        _backend = get_stdlib_backend()
    elif backend_type == "loguru":
        if not HAS_LOGURU:
            raise ImportError(
                "loguru backend requires loguru to be installed. Install it with: pip install loguru",
            )
        _backend = get_loguru_backend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}. Use 'stdlib' or 'loguru'.")

    _initialized = False


def _capture_params(fn: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Capture function parameters as a dictionary.

    Args:
        fn: The function to capture parameters from.
        args: Positional arguments passed to the function.
        kwargs: Keyword arguments passed to the function.

    Returns:
        Dictionary mapping parameter names to their values.
        Excludes 'self' and 'cls' parameters.
    """
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        params = dict(bound.arguments)
        first = next(iter(sig.parameters), None)
        if first in {"self", "cls"}:
            params.pop(first, None)
        return params
    except Exception:
        return {}


def log_calls(
    method: Any = None,
    *,
    include_result: bool = True,
    message: str | None = None,
    level: str = "info",
    filter: Callable[..., bool] | None = None,
) -> Any:
    """Decorator for automatic function/method logging.

    This decorator wraps a function to automatically log its execution,
    including parameters and optionally the result.

    Args:
        method: The function to decorate (when used without parentheses).
        include_result: Whether to include the return value in the log.
        message: Custom event name prefix. Defaults to function's qualified name.
        level: Log level (debug, info, warning, error).
        filter: Optional callable that receives (func_name, *args, **kwargs) and returns
                a bool indicating whether to log this call. func_name is the event prefix
                (fn.__qualname__ or custom message). Return True to log, False to skip.

    Returns:
        The decorated function with logging enabled.

    Example:
        @log_calls
        def my_function(x, y):
            return x + y

        @log_calls(filter=lambda name, x, y: x > 0 and "important" in name)
        def conditional_log(x, y):
            return x + y  # Only logs when x > 0 and "important" in function name
    """

    def decorator(fn: Any) -> Any:
        event_base = message if message is not None else fn.__qualname__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if filter is not None:
                try:
                    sig = inspect.signature(fn)
                    bound = sig.bind(*args, **kwargs)
                    if not filter(event_base, *bound.args, **bound.kwargs):
                        return await fn(*args, **kwargs)
                except Exception:
                    pass

            carrier = args[0] if args else None
            fallback = get_logger(fn.__module__)
            current_log = getattr(carrier, "_log", None)
            if current_log is None and carrier is not None:
                try:
                    carrier._log = fallback
                    current_log = carrier._log
                except AttributeError:
                    current_log = None
            _log: LoggerProtocol = current_log or fallback
            params = _capture_params(fn, args, kwargs)
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                _log.error(f"{event_base}.error", **params, error=exc)
                raise
            if include_result:
                getattr(_log, level)(f"{event_base}.done", **params, result=result)
            else:
                getattr(_log, level)(f"{event_base}.done", **params)
            return result

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if filter is not None:
                try:
                    sig = inspect.signature(fn)
                    bound = sig.bind(*args, **kwargs)
                    if not filter(event_base, *bound.args, **bound.kwargs):
                        return fn(*args, **kwargs)
                except Exception:
                    pass

            carrier = args[0] if args else None
            fallback = get_logger(fn.__module__)
            current_log = getattr(carrier, "_log", None)
            if current_log is None and carrier is not None:
                try:
                    carrier._log = fallback
                    current_log = carrier._log
                except AttributeError:
                    current_log = None
            _log: LoggerProtocol = current_log or fallback
            params = _capture_params(fn, args, kwargs)
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                _log.error(f"{event_base}.error", **params, error=exc)
                raise
            if include_result:
                getattr(_log, level)(f"{event_base}.done", **params, result=result)
            else:
                getattr(_log, level)(f"{event_base}.done", **params)
            return result

        wrapper = async_wrapper if inspect.iscoroutinefunction(fn) else sync_wrapper
        wrapper._log_calls = True
        return wrapper

    return decorator(method) if method is not None else decorator


class LogContext:
    """Context manager for scoped logging.

    This class provides a context manager that automatically logs
    completion or error when exiting the context.

    Attributes:
        _event: Base event name for the context.
        _log: Logger instance to use.
        _fields: Initial fields for the log.
        _extra: Additional fields bound during the context.
        _level: Log level to use on successful completion.
    """

    __slots__ = ("_event", "_log", "_fields", "_extra", "_level")

    def __init__(self, event: str, *, logger_instance: LoggerProtocol, level: str = "info", **fields: Any) -> None:
        """Initialize the LogContext.

        Args:
            event: Base event name for the context.
            logger_instance: Logger to use for logging.
            level: Log level for successful completion.
            **fields: Initial fields to include in the log.
        """
        self._event = event
        self._log = logger_instance
        self._fields = fields
        self._extra: dict[str, Any] = {}
        self._level = level

    def bind(self, **extra: Any) -> LogContext:
        """Bind additional fields to the context.

        Args:
            **extra: Key-value pairs to add to the log.

        Returns:
            Self for method chaining.
        """
        self._extra.update(extra)
        return self

    def _emit(self, exc_val: BaseException | None) -> None:
        """Emit the log message when exiting the context.

        Args:
            exc_val: Exception if one occurred, None otherwise.
        """
        all_fields = {**self._fields, **self._extra}
        if exc_val is not None:
            self._log.error(f"{self._event}.error", **all_fields, error=exc_val)
        else:
            getattr(self._log, self._level)(f"{self._event}.done", **all_fields)

    def __enter__(self) -> LogContext:
        """Enter the synchronous context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the synchronous context and emit log.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self._emit(exc_val)

    async def __aenter__(self) -> LogContext:
        """Enter the asynchronous context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the asynchronous context and emit log.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self._emit(exc_val)


def log_context(event: str, *, logger: LoggerProtocol | None = None, level: str = "info", **fields: Any) -> LogContext:
    """Create a logging context manager.

    This is a convenience function for creating LogContext instances.

    Args:
        event: Base event name for the context.
        logger: Logger instance to use. Defaults to the default logger.
        level: Log level for successful completion.
        **fields: Initial fields to include in the log.

    Returns:
        A LogContext instance for use with 'with' or 'async with'.

    Example:
        with log_context("processing_data", user_id=123):
            # ... do work ...
            pass  # Logs "processing_data.done" on exit
    """
    lg = logger or get_logger(DEFAULT_LOGGER_NAME)
    return LogContext(event, logger_instance=lg, level=level, **fields)


def no_log(fn: Any) -> Any:
    """Mark a function to be excluded from log_class decoration.

    Use this decorator on methods that should not be automatically
    logged when using @log_class on the containing class.

    Args:
        fn: The function to mark as excluded from logging.

    Returns:
        The same function with a _no_log marker attribute.

    Example:
        @log_class
        class MyClass:
            def public_method(self):
                pass  # This will be logged

            @no_log
            def internal_method(self):
                pass  # This will NOT be logged
    """
    fn._no_log = True
    return fn


def log_class(
    cls: Any = None,
    *,
    default: bool = True,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    skip_private: bool = True,
    include_result: bool = False,
    level: str = "info",
    filter: Callable[..., bool] | None = None,
) -> Any:
    """Decorator for automatic class method logging.

    This decorator wraps all methods of a class with log_calls.
    It automatically injects a logger instance into the class.

    Args:
        cls: The class to decorate (when used without parentheses).
        default: If True, log all methods except those in exclude.
                 If False, only log methods in include.
        include: List of method names to always log.
        exclude: List of method names to never log.
        skip_private: Whether to skip methods starting with underscore.
        include_result: Whether to include return values in logs.
        level: Log level (debug, info, warning, error).
        filter: Optional callable that receives (func_name, *args, **kwargs) and returns
                a bool indicating whether to log this call. Applied to all methods.

    Returns:
        The decorated class with method logging enabled.

    Example:
        @log_class
        class MyService:
            def process(self, data):
                return data.upper()  # Automatically logged

        @log_class(exclude=["internal_helper"])
        class MyService:
            def process(self, data):
                return data.upper()

            def internal_helper(self):
                pass  # Not logged

        @log_class(filter=lambda name, self, *args, **kwargs: "process" in name)
        class ConditionalService:
            def process(self, value):
                return value * 2  # Only logs for methods with "process" in name
    """

    def decorator(klass: Any) -> Any:
        own_init = klass.__dict__.get("__init__")
        if own_init is not None:

            @functools.wraps(own_init)
            def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
                own_init(self, *args, **kwargs)
                try:
                    if not getattr(self, "_log", None):
                        self._log = get_logger(klass.__module__)
                except AttributeError:
                    pass

            klass.__init__ = _patched_init

        for name, obj in list(klass.__dict__.items()):
            if not isinstance(obj, types.FunctionType):
                continue
            if name.startswith("__") and name.endswith("__"):
                continue
            if skip_private and name.startswith("_"):
                continue
            if getattr(obj, "_no_log", False):
                continue
            if getattr(obj, "_log_calls", False):
                continue
            should_wrap = name not in (exclude or []) if default else name in (include or [])
            if should_wrap:
                setattr(klass, name, log_calls(obj, include_result=include_result, level=level, filter=filter))
        return klass

    if cls is not None:
        return decorator(cls)
    return decorator


def setup_logging(
    name: str = DEFAULT_LOGGER_NAME,
    level: str | None = None,
    log_dir: str | Path | None = None,
    backend: str = "stdlib",
    **options: Any,
) -> LoggerProtocol:
    """Set up logging with console and optional file output.

    This function initializes the logging system with a custom format.
    It should be called once at application startup.

    Args:
        name: Logger name. Defaults to "logcraft".
        level: Log level (DEBUG, INFO, WARNING, ERROR).
               Defaults to LOG_LEVEL env var or INFO.
        log_dir: Directory for log files. Defaults to LOGCRAFT_LOG_DIR env var or "logs".
        backend: Logging backend - "stdlib" (default) or "loguru".
        **options: Backend-specific options.

    Returns:
        A Logger instance for the specified name.

    Example:
        # Basic setup with stdlib (default)
        log = setup_logging()

        # Use loguru backend
        log = setup_logging(backend="loguru", level="DEBUG")

        # Custom configuration
        log = setup_logging(
            level="DEBUG",
            log_dir="var/logs",
            backend="stdlib",
        )
    """
    global _initialized, _backend

    # Set backend if different from current
    if backend == "loguru" and not isinstance(_backend, LoguruBackend if HAS_LOGURU else type(None)):
        _set_backend("loguru")
    elif backend == "stdlib" and not isinstance(_backend, StdlibBackend):
        _set_backend("stdlib")

    raw_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    effective_dir = str(log_dir or DEFAULT_LOG_DIR)

    backend_instance = _get_current_backend()
    if not _initialized:
        backend_instance.setup(level=raw_level, log_dir=effective_dir, **options)
        _initialized = True

    return get_logger(name)


def get_logger(name: str = DEFAULT_LOGGER_NAME) -> LoggerProtocol:
    """Get or create a Logger instance for the specified name.

    This function returns a Logger instance from the current backend.
    If logging has not been initialized, it will be initialized with defaults.

    Args:
        name: Logger name/module. Defaults to "logcraft".

    Returns:
        A Logger instance for the specified name.

    Example:
        log = get_logger("myapp.database")
        log.info("connection_established", host="localhost", port=5432)
    """
    global _initialized
    if not _initialized:
        setup_logging()
    backend_instance = _get_current_backend()
    return backend_instance.get_logger(name)
