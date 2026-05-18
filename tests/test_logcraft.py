from __future__ import annotations

from typing import Any

import pytest

from logcraft import LogContext, _core, log_calls, log_class, log_context, no_log


class SpyLogger:
    def __init__(self, records: list[tuple[str, str, dict[str, Any]]], bound: dict[str, Any] | None = None) -> None:
        self.records = records
        self.bound = bound or {}

    def bind(self, **ctx: Any) -> SpyLogger:
        return SpyLogger(self.records, {**self.bound, **ctx})

    def _emit(self, level: str, event_name: str, **fields: Any) -> None:
        self.records.append((level, event_name, {**self.bound, **fields}))

    def debug(self, event_name: str, **fields: Any) -> None:
        self._emit("debug", event_name, **fields)

    def info(self, event_name: str, **fields: Any) -> None:
        self._emit("info", event_name, **fields)

    def warning(self, event_name: str, **fields: Any) -> None:
        self._emit("warning", event_name, **fields)

    def error(self, event_name: str, **fields: Any) -> None:
        self._emit("error", event_name, **fields)

    def context(self, event: str, **fields: Any) -> LogContext:
        return LogContext(event, logger_instance=self, **fields)


@pytest.fixture
def records() -> list[tuple[str, str, dict[str, Any]]]:
    return []


@pytest.fixture
def stub_logger(monkeypatch: pytest.MonkeyPatch, records: list[tuple[str, str, dict[str, Any]]]) -> SpyLogger:
    logger = SpyLogger(records)
    monkeypatch.setattr(_core, "get_logger", lambda _name=None: logger)
    return logger


def test_log_calls_sync_success_and_error(
    records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger
) -> None:
    @log_calls
    def add(a: int, b: int) -> int:
        return a + b

    @log_calls
    def explode(x: int) -> int:
        raise ValueError("bad")

    assert add(1, 2) == 3
    with pytest.raises(ValueError):
        explode(1)
    assert any(event.endswith(".add.done") and fields.get("result") == 3 for _, event, fields in records)
    assert any(event.endswith(".explode.error") for _, event, _ in records)


@pytest.mark.asyncio
async def test_log_calls_async_success(records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger) -> None:
    @log_calls
    async def run(v: int) -> int:
        return v + 1

    assert await run(1) == 2
    assert any(event.endswith(".run.done") and fields.get("result") == 2 for _, event, fields in records)


def test_log_calls_message_and_include_result(
    records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger
) -> None:
    @log_calls(message="custom.event", include_result=False)
    def f(message: str) -> str:
        return message

    assert f("ok") == "ok"
    done = next(fields for _, event, fields in records if event == "custom.event.done")
    assert "result" not in done
    assert done["message"] == "ok"


def test_log_class_default_true_and_exclude(
    records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger
) -> None:
    @log_class(default=True, exclude=["helper"])
    class Service:
        def run(self, x: int) -> int:
            return x * 2

        def helper(self, x: int) -> int:
            return x

    s = Service()
    assert s.run(2) == 4
    assert s.helper(2) == 2
    assert any(event.endswith(".Service.run.done") for _, event, _ in records)
    assert not any(event.endswith(".Service.helper.done") for _, event, _ in records)


def test_log_class_include_and_no_log(records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger) -> None:
    @log_class(default=False, include=["run"])
    class Service:
        def run(self, x: int) -> int:
            return x

        @no_log
        def skip(self) -> str:
            return "skip"

    s = Service()
    assert s.run(3) == 3
    assert s.skip() == "skip"
    assert any(event.endswith(".Service.run.done") for _, event, _ in records)
    assert not any(event.endswith(".Service.skip.done") for _, event, _ in records)


def test_log_class_auto_inject_and_preserve_logger(
    records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger
) -> None:
    @log_class(default=True, include=["run"])
    class Auto:
        def __init__(self) -> None:
            pass

        def run(self) -> str:
            return "ok"

    @log_class(default=True, include=["run"])
    class Manual:
        def __init__(self) -> None:
            self._log = _core.get_logger("manual").bind(tag="x")

        def run(self) -> str:
            return "ok"

    a = Auto()
    m = Manual()
    assert a.run() == "ok"
    assert m.run() == "ok"
    assert hasattr(a, "_log")
    assert hasattr(m, "_log")
    assert any(event.endswith(".Auto.run.done") for _, event, _ in records)
    assert any(event.endswith(".Manual.run.done") and fields.get("tag") == "x" for _, event, fields in records)


def test_log_context_sync(records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger) -> None:
    with log_context("sync.block", k=1) as ctx:
        ctx.bind(done=True, event="kept")
    assert any(event == "sync.block.done" and fields.get("event") == "kept" for _, event, fields in records)


@pytest.mark.asyncio
async def test_log_context_async(records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger) -> None:
    logger = _core.get_logger(__name__)
    async with logger.context("async.block", q=1) as ctx:
        ctx.bind(ok=True)
    assert any(event == "async.block.done" and fields.get("ok") is True for _, event, fields in records)


def test_log_context_error(records: list[tuple[str, str, dict[str, Any]]], stub_logger: SpyLogger) -> None:
    with pytest.raises(RuntimeError), log_context("err.block", x=1):
        raise RuntimeError("boom")
    assert any(event == "err.block.error" for _, event, _ in records)
