"""Core implementation for logcraft."""

from __future__ import annotations

import asyncio
import functools
import inspect
import os
import sys
import traceback
import types
from pathlib import Path
from typing import Any

from loguru import logger as _loguru

DEFAULT_LOGGER_NAME = "logcraft"
DEFAULT_LOG_DIR = os.getenv("LOGCRAFT_LOG_DIR", "logs")
_initialized = False


def _format_extra(fields: dict[str, Any]) -> str:
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


class Logger:
    __slots__ = ("_inner",)

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def bind(self, **ctx: Any) -> Logger:
        return Logger(self._inner.bind(**ctx))

    def _emit(self, level: str, event_name: str, **fields: Any) -> None:
        lg = self._inner.opt(depth=2)
        if fields:
            lg = lg.bind(**fields)
        getattr(lg, level)(event_name)

    def debug(self, event_name: str, **fields: Any) -> None:
        self._emit("debug", event_name, **fields)

    def info(self, event_name: str, **fields: Any) -> None:
        self._emit("info", event_name, **fields)

    def warning(self, event_name: str, **fields: Any) -> None:
        self._emit("warning", event_name, **fields)

    def error(self, event_name: str, **fields: Any) -> None:
        self._emit("error", event_name, **fields)

    def exception(self, event_name: str, **fields: Any) -> None:
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            fields["traceback"] = "".join(traceback.format_exception(*exc_info))
        self._emit("error", event_name, **fields)

    def context(self, event: str, **fields: Any) -> LogContext:
        return LogContext(event, logger_instance=self, **fields)


def _capture_params(fn: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
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
) -> Any:
    def decorator(fn: Any) -> Any:
        event_base = message if message is not None else fn.__qualname__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            carrier = args[0] if args else None
            fallback = get_logger(fn.__module__)
            current_log = getattr(carrier, "_log", None)
            if current_log is None and carrier is not None:
                try:
                    carrier._log = fallback
                    current_log = carrier._log
                except AttributeError:
                    current_log = None
            _log: Logger = current_log or fallback
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
            carrier = args[0] if args else None
            fallback = get_logger(fn.__module__)
            current_log = getattr(carrier, "_log", None)
            if current_log is None and carrier is not None:
                try:
                    carrier._log = fallback
                    current_log = carrier._log
                except AttributeError:
                    current_log = None
            _log: Logger = current_log or fallback
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

        wrapper = async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper
        wrapper._log_calls = True
        return wrapper

    return decorator(method) if method is not None else decorator


class LogContext:
    __slots__ = ("_event", "_log", "_fields", "_extra", "_level")

    def __init__(self, event: str, *, logger_instance: Logger, level: str = "info", **fields: Any) -> None:
        self._event = event
        self._log = logger_instance
        self._fields = fields
        self._extra: dict[str, Any] = {}
        self._level = level

    def bind(self, **extra: Any) -> LogContext:
        self._extra.update(extra)
        return self

    def _emit(self, exc_val: BaseException | None) -> None:
        all_fields = {**self._fields, **self._extra}
        if exc_val is not None:
            self._log.error(f"{self._event}.error", **all_fields, error=exc_val)
        else:
            getattr(self._log, self._level)(f"{self._event}.done", **all_fields)

    def __enter__(self) -> LogContext:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._emit(exc_val)

    async def __aenter__(self) -> LogContext:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._emit(exc_val)


def log_context(event: str, *, logger: Logger | None = None, level: str = "info", **fields: Any) -> LogContext:
    lg = logger or get_logger(DEFAULT_LOGGER_NAME)
    return LogContext(event, logger_instance=lg, level=level, **fields)


def no_log(fn: Any) -> Any:
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
) -> Any:
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
            if default:
                should_wrap = name not in (exclude or [])
            else:
                should_wrap = name in (include or [])
            if should_wrap:
                setattr(klass, name, log_calls(obj, include_result=include_result, level=level))
        return klass

    if cls is not None:
        return decorator(cls)
    return decorator


def setup_logging(
    name: str = DEFAULT_LOGGER_NAME,
    level: str | None = None,
    log_dir: str | Path | None = None,
    when: str = "D",
    interval: int = 1,
    backup_count: int = 3,
    enable_file: bool = True,
) -> Logger:
    global _initialized, _loguru
    raw_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()

    if not _initialized:
        _loguru.remove()
        _loguru.add(
            sys.stdout,
            format=_log_formatter,
            level=raw_level,
            colorize=False,
        )

        if enable_file:
            effective_dir = Path(log_dir or DEFAULT_LOG_DIR)
            effective_dir.mkdir(parents=True, exist_ok=True)
            log_file = effective_dir / f"{DEFAULT_LOGGER_NAME}.log"
            _rotation_map = {
                "S": "second",
                "M": "minute",
                "H": "hour",
                "D": "day",
                "W": "week",
                "midnight": "00:00",
            }
            rotation_unit = _rotation_map.get(when, "day")
            if rotation_unit == "00:00":
                rotation = "00:00"
            elif interval > 1:
                rotation = f"{interval} {rotation_unit}s"
            else:
                rotation = f"1 {rotation_unit}"

            _loguru.add(
                str(log_file),
                format=_log_formatter,
                level=raw_level,
                rotation=rotation,
                retention=backup_count,
                encoding="utf-8",
                colorize=False,
            )
        _initialized = True

    return get_logger(name)


def get_logger(name: str = DEFAULT_LOGGER_NAME) -> Logger:
    global _initialized
    if not _initialized:
        setup_logging()
    return Logger(_loguru.bind(module=name))
