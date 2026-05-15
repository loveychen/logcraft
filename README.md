# logcraft

[中文文档](README_zh.md)

A lightweight AOP-style logging toolkit for Python, built on top of `loguru`.

It helps remove manual `logger.info(...)` boilerplate by injecting structured logs through decorators and context managers.

## Install

```bash
pip install logcraft
```

## Quick start

```python
from logcraft import get_logger, log_calls, log_class, no_log, log_context, setup_logging

setup_logging(level="INFO", enable_file=False)
logger = get_logger(__name__)


@log_calls
def add(a: int, b: int) -> int:
    return a + b


@log_class(default=True, exclude=["helper"])
class Service:
    def run(self, x: int) -> int:
        return x * 2

    @no_log
    def helper(self) -> str:
        return "skip"


with log_context("batch.process", size=10) as ctx:
    ctx.bind(done=10)
```

## API Reference

### `setup_logging()`

Initialize the global loguru sink. Call once at program startup.

```python
from logcraft import setup_logging

setup_logging(
    level="INFO",        # or set via LOG_LEVEL env var
    log_dir="logs",      # or set via LOGCRAFT_LOG_DIR env var
    when="D",            # rotation interval unit: S/M/H/D/W/midnight
    interval=1,          # rotation every N units
    backup_count=3,      # number of rotated files to keep
    enable_file=True,    # set False to disable file output
)
```

If `level` is omitted, it falls back to the `LOG_LEVEL` environment variable, then `"INFO"`. If `log_dir` is omitted, it falls back to `LOGCRAFT_LOG_DIR`, then `"logs"`.

The log format is structured and includes timestamp, level, PID, thread ID, module, and line number:

```
2026-05-15 10:30:00.123 || INFO || 12345 || 67890 || myapp:42 || add.done || a=1, b=2, result=3
```

### `get_logger(name)`

Return a `Logger` instance bound to the given module name.

```python
logger = get_logger(__name__)
logger.info("user.login", user_id=42)
```

### `Logger`

The wrapper around loguru that powers all logcraft output.

| Method | Description |
|--------|-------------|
| `debug(event, **fields)` | Emit at DEBUG level |
| `info(event, **fields)` | Emit at INFO level |
| `warning(event, **fields)` | Emit at WARNING level |
| `error(event, **fields)` | Emit at ERROR level |
| `exception(event, **fields)` | Emit at ERROR level with traceback attached |
| `bind(**ctx)` | Return a new Logger with persistent context fields |
| `context(event, **fields)` | Return a `LogContext` manager (see below) |

`bind()` is useful for attaching correlation fields that propagate across calls:

```python
req_log = logger.bind(request_id="abc-123")
req_log.info("handler.start")
req_log.info("handler.end", status=200)
# both lines include request_id=abc-123
```

### `@log_calls`

Decorator that automatically logs function entry (`.done`) and exceptions (`.error`).

```python
@log_calls
def add(a: int, b: int) -> int:
    return a + b
```

Calling `add(1, 2)` emits:

```
add.done || a=1, b=2, result=3
```

If the function raises, it emits `.error` and re-raises the exception:

```python
@log_calls
def fail():
    raise ValueError("bad")
```

Calling `fail()` emits:

```
fail.error || error=ValueError: bad
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `include_result` | `True` | Attach the return value as `result=` in the `.done` log |
| `message` | `None` | Custom event name prefix (default is `fn.__qualname__`) |
| `level` | `"info"` | Log level for `.done` events (`.error` always uses `error`) |

**Custom event name:**

```python
@log_calls(message="payment.charge", include_result=False)
def charge(user_id: str, amount: float) -> str:
    return "tx_123"
```

Emits `payment.charge.done || user_id=alice, amount=9.99` (no `result=`).

**Async support:** `@log_calls` detects coroutines automatically and wraps them with `async def`.

```python
@log_calls
async def fetch(url: str) -> str:
    ...
```

### `@log_class`

Class decorator that applies `@log_calls` to selected methods. It also injects a `self._log` attribute (a `Logger` instance) if the class doesn't already define one.

```python
@log_class(default=True, exclude=["helper"])
class Service:
    def run(self, x: int) -> int:
        return x * 2

    def helper(self) -> str:
        return "skip"
```

`run` gets logged as `Service.run.done`, while `helper` is excluded.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `default` | `True` | If `True`, log all methods (minus `exclude`). If `False`, only log methods in `include`. |
| `include` | `None` | List of method names to log (used when `default=False`) |
| `exclude` | `None` | List of method names to skip (used when `default=True`) |
| `skip_private` | `True` | Automatically skip methods starting with `_` (dunder methods are always skipped) |
| `include_result` | `False` | Whether to include return values in `.done` logs |
| `level` | `"info"` | Log level for `.done` events |

**Opt-in mode** (`default=False`):

```python
@log_class(default=False, include=["run"])
class Service:
    def run(self, x: int) -> int:
        return x * 2

    def helper(self) -> str:
        return "skip"
```

Only `run` is logged.

**Custom logger on the instance:**

If `__init__` sets `self._log`, `@log_class` preserves it and uses it for all wrapped methods:

```python
@log_class(default=True, include=["run"])
class Manual:
    def __init__(self):
        self._log = get_logger("manual").bind(tag="x")

    def run(self) -> str:
        return "ok"
```

Emits `Manual.run.done || tag=x`.

### `@no_log`

Mark a method to be skipped by `@log_class`, even if it would otherwise be included.

```python
@log_class(default=True)
class Worker:
    def run(self): ...       # logged
    def process(self): ...   # logged

    @no_log
    def internal(self): ...  # skipped
```

### `log_context()`

Context manager for block-level logging. Emits `.done` on normal exit, `.error` on exception.

```python
with log_context("batch.process", size=100) as ctx:
    ctx.bind(processed=42)
```

Normal exit emits:

```
batch.process.done || size=100, processed=42
```

If an exception occurs:

```python
with log_context("batch.process", size=100):
    raise RuntimeError("disk full")
```

Emits:

```
batch.process.error || size=100, error=RuntimeError: disk full
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `event` | required | Event name prefix |
| `logger` | `None` | Custom `Logger` instance (default: uses the global logcraft logger) |
| `level` | `"info"` | Log level for `.done` events |
| `**fields` | — | Static fields included in both `.done` and `.error` |

**`ctx.bind(**fields)`** adds fields that accumulate during the block and are emitted at exit.

**Async support:** `log_context` works with `async with`:

```python
async with logger.context("api.call", endpoint="/users") as ctx:
    ctx.bind(status=200)
```

### `LogContext`

The object returned by `log_context()` and `logger.context()`. You typically don't construct it directly.

| Method | Description |
|--------|-------------|
| `bind(**fields)` | Accumulate fields to include in the final log |
| `__enter__` / `__exit__` | Synchronous context manager protocol |
| `__aenter__` / `__aexit__` | Async context manager protocol |

## Configuration

```python
from logcraft import setup_logging

setup_logging(
    level="INFO",
    log_dir="logs",
    when="D",
    interval=1,
    backup_count=3,
    enable_file=True,
)
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `"INFO"` | Default log level when `level` param is not passed |
| `LOGCRAFT_LOG_DIR` | `"logs"` | Default log directory when `log_dir` param is not passed |

## Development shortcuts

```bash
make help
make install
make test
make build
make clean
make publish-test   # publish to TestPyPI
make publish        # publish to PyPI
```

## How it works

- Decorators capture function parameters via `inspect.signature(...)`
- `self` / `cls` parameters are automatically stripped from logged fields
- Success path emits `<event>.done`
- Error path emits `<event>.error` and re-raises exception
- `@log_class` only wraps methods defined in `cls.__dict__` (not inherited ones) to avoid side effects
- `@log_class` injects `self._log` on first call if the instance doesn't already have one
- `@no_log` sets `fn._no_log = True` which `@log_class` checks before wrapping
