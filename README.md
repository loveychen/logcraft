# logcraft

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

## Features

- `@log_calls` for method/function-level logging on `.done` / `.error`
- `@log_class` for class-level auto-injection with `include` / `exclude`
- `@no_log` to skip specific methods
- `log_context(...)` and `logger.context(...)` for block-level logs
- Structured fields through `**kwargs`

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
- Success path emits `<event>.done`
- Error path emits `<event>.error` and re-raises exception
- Class decorator wraps methods in `cls.__dict__` to avoid inherited method side effects
