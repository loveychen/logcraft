# logcraft

一个轻量级的 AOP 风格 Python 日志工具，**框架无关设计**。

通过装饰器和上下文管理器注入结构化日志，消除手动 `logger.info(...)` 的样板代码。

**核心特性：**
- 🎯 **框架无关**：默认使用 Python 标准 `logging` 模块，可选 `loguru` 支持
- 🔍 **条件日志**：支持过滤器装饰器，实现细粒度日志控制
- 📝 **完整文档**：所有公共 API 都有详细的 docstring
- 🛠️ **代码质量**：内置 lint、format 和测试工具

## 安装

```bash
pip install logcraft-aop
```

**可选后端：**

```bash
# 安装 loguru 后端（可选）
pip install logcraft-aop[loguru]
```

## 快速开始

```python
from logcraft import get_logger, log_calls, log_class, no_log, log_context, setup_logging

# 使用 stdlib 后端初始化（默认）
setup_logging(level="INFO", enable_file=False)
logger = get_logger(__name__)


@log_calls
def add(a: int, b: int) -> int:
    return a + b


# 使用 filter 实现条件日志
@log_calls(filter=lambda x, y: x > 0)
def conditional_add(x: int, y: int) -> int:
    return x + y  # 只在 x > 0 时记录日志


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

## 后端选择

Logcraft 支持多种日志后端。**默认使用 Python 标准 `logging` 模块**，实现框架无关。

### 使用 stdlib 后端（默认）

```python
from logcraft import setup_logging

# 默认就是 stdlib 后端
setup_logging(level="INFO", log_dir="logs")
```

### 使用 loguru 后端

```python
from logcraft import setup_logging

# 在 setup_logging 中指定 loguru 后端
setup_logging(backend="loguru", level="INFO", log_dir="logs")
```

## API 参考

### `setup_logging()`

初始化日志系统，在程序启动时调用一次。

```python
from logcraft import setup_logging

setup_logging(
    level="INFO",        # 也可通过 LOG_LEVEL 环境变量设置
    log_dir="logs",      # 也可通过 LOGCRAFT_LOG_DIR 环境变量设置
    backend="stdlib",    # "stdlib"（默认）或 "loguru"
    **options            # 后端特定选项
)
```

如果省略 `level`，将依次回退到 `LOG_LEVEL` 环境变量和 `"INFO"`。如果省略 `log_dir`，将依次回退到 `LOGCRAFT_LOG_DIR` 环境变量和 `"logs"`。

**后端特定选项：**

对于 `stdlib` 后端：
- `format`：自定义日志格式字符串
- `datefmt`：日期格式字符串
- `enable_console`：启用控制台输出（默认：`True`）
- `enable_file`：启用文件输出（默认：`True`）

对于 `loguru` 后端：
- `enable_console`：启用控制台输出（默认：`True`）
- `enable_file`：启用文件输出（默认：`True`）
- `rotation`：日志轮转设置（默认：`"1 day"`）
- `retention`：保留的轮转文件数量（默认：`3`）

日志格式为结构化输出，包含时间戳、级别、PID、线程 ID、模块和行号：

```text
2026-05-15 10:30:00.123 || INFO || 12345 || 67890 || myapp:42 || add.done || a=1, b=2, result=3
```

### `get_logger(name)`

返回绑定到指定模块名的 `LoggerProtocol` 实例。

```python
logger = get_logger(__name__)
logger.info("user.login", user_id=42)
```

### `LoggerProtocol`

所有日志后端实现的协议。这替代了之前的 `Logger` 类。

| 方法 | 说明 |
|------|------|
| `debug(event, **fields)` | 以 DEBUG 级别输出 |
| `info(event, **fields)` | 以 INFO 级别输出 |
| `warning(event, **fields)` | 以 WARNING 级别输出 |
| `error(event, **fields)` | 以 ERROR 级别输出 |
| `exception(event, **fields)` | 以 ERROR 级别输出，自动附带 traceback |
| `bind(**ctx)` | 返回一个携带持久上下文字段的新 Logger |
| `context(event, **fields)` | 返回 `LogContext` 上下文管理器（见下方说明） |

`bind()` 适合附加需要跨调用传播的关联字段：

```python
req_log = logger.bind(request_id="abc-123")
req_log.info("handler.start")
req_log.info("handler.end", status=200)
# 两行日志都包含 request_id=abc-123
```

### `@log_calls`

装饰器，自动记录函数执行完成（`.done`）和异常（`.error`）。

```python
@log_calls
def add(a: int, b: int) -> int:
    return a + b
```

调用 `add(1, 2)` 输出：

```text
add.done || a=1, b=2, result=3
```

如果函数抛出异常，输出 `.error` 并重新抛出：

```python
@log_calls
def fail():
    raise ValueError("bad")
```

调用 `fail()` 输出：

```text
fail.error || error=ValueError: bad
```

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `include_result` | `True` | 在 `.done` 日志中附带返回值 `result=` |
| `message` | `None` | 自定义事件名前缀（默认使用 `fn.__qualname__`） |
| `level` | `"info"` | `.done` 事件的日志级别（`.error` 始终使用 `error`） |
| `filter` | `None` | 接收函数参数并返回 `bool` 的可调用对象，决定是否记录日志 |

**使用 filter 实现条件日志：**

`filter` 参数允许根据函数参数条件性地记录日志：

```python
# 只在金额 > 1000 时记录日志
@log_calls(filter=lambda user_id, amount: amount > 1000)
def process_payment(user_id: str, amount: float) -> str:
    return "tx_123"

# 只为特定用户记录日志
@log_calls(filter=lambda user_id, **kwargs: user_id.startswith("admin_"))
def admin_action(user_id: str, action: str) -> None:
    pass
```

过滤器函数的签名应与被装饰函数兼容。它接收函数的所有参数并返回：
- `True`：记录此调用
- `False`：跳过此调用的日志
| `filter` | `None` | 接收函数参数并返回 `bool` 的可调用对象，决定是否记录日志 |

**使用 filter 实现条件日志：**

`filter` 参数允许根据函数参数条件性地记录日志。函数名称通过关键字参数 `func_name` 传入。

**1. 仅按参数过滤：**
```python
# 只在金额 > 1000 时记录日志
@log_calls(filter=lambda user_id, amount: amount > 1000)
def process_payment(user_id: str, amount: float) -> str:
    return "tx_123"

# 只为特定用户记录日志
@log_calls(filter=lambda user_id, **kwargs: user_id.startswith("admin_"))
def admin_action(user_id: str, action: str) -> None:
    pass
```

**2. 按函数名称过滤（作为关键字参数）：**
```python
# 只为名称包含 "important" 的函数记录日志
@log_calls(filter=lambda **kwargs: "important" in kwargs.get("func_name", ""))
def important_operation(data: dict) -> None:
    pass

# 结合名称和参数
@log_calls(filter=lambda user_id, amount, func_name="": "payment" in func_name and amount > 1000)
def process_payment(user_id: str, amount: float) -> str:
    return "tx_123"
```

过滤器接收所有函数参数，以及 `func_name` 作为关键字参数。

**自定义事件名：**

```python
@log_calls(message="payment.charge", include_result=False)
def charge(user_id: str, amount: float) -> str:
    return "tx_123"
```

输出 `payment.charge.done || user_id=alice, amount=9.99`（不含 `result=`）。

**异步支持：** `@log_calls` 自动检测协程并使用 `async def` 包装。

```python
@log_calls
async def fetch(url: str) -> str:
    ...
```

### `@log_class`

类装饰器，对选定方法应用 `@log_calls`。如果类尚未定义 `self._log`，会自动注入一个 `Logger` 实例。

```python
@log_class(default=True, exclude=["helper"])
class Service:
    def run(self, x: int) -> int:
        return x * 2

    def helper(self) -> str:
        return "skip"
```

`run` 会被记录为 `Service.run.done`，而 `helper` 被排除。

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `default` | `True` | 为 `True` 时记录所有方法（减去 `exclude`）；为 `False` 时只记录 `include` 中的方法 |
| `include` | `None` | 需要记录日志的方法名列表（`default=False` 时生效） |
| `exclude` | `None` | 需要跳过的方法名列表（`default=True` 时生效） |
| `skip_private` | `True` | 自动跳过以 `_` 开头的方法（双下划线方法始终跳过） |
| `include_result` | `False` | 是否在 `.done` 日志中包含返回值 |
| `level` | `"info"` | `.done` 事件的日志级别 |
| `filter` | `None` | 接收方法参数并返回 `bool` 的可调用对象，决定是否记录日志 |

**使用 filter 实现条件日志：**

`filter` 参数应用于类中的所有方法，函数名称通过关键字参数 `func_name` 传入：

```python
# 只为名称包含 "process" 的方法记录日志
@log_class(filter=lambda **kwargs: "process" in kwargs.get("func_name", ""))
class Processor:
    def process(self, value: int) -> int:
        return value * 2

    def validate(self, value: int) -> bool:
        return value > 0  # 不记录日志（名称中没有 "process"）
```

**白名单模式** (`default=False`)：

```python
@log_class(default=False, include=["run"])
class Service:
    def run(self, x: int) -> int:
        return x * 2

    def helper(self) -> str:
        return "skip"
```

只有 `run` 会被记录。

**实例上的自定义 Logger：**

如果 `__init__` 设置了 `self._log`，`@log_class` 会保留并使用它：

```python
@log_class(default=True, include=["run"])
class Manual:
    def __init__(self):
        self._log = get_logger("manual").bind(tag="x")

    def run(self) -> str:
        return "ok"
```

输出 `Manual.run.done || tag=x`。

### `@no_log`

标记方法使其被 `@log_class` 跳过，即使它本来应该被包含。

```python
@log_class(default=True)
class Worker:
    def run(self): ...       # 记录日志
    def process(self): ...   # 记录日志

    @no_log
    def internal(self): ...  # 跳过
```

### `log_context()`

用于代码块级别日志的上下文管理器。正常退出时输出 `.done`，异常时输出 `.error`。

```python
with log_context("batch.process", size=100) as ctx:
    ctx.bind(processed=42)
```

正常退出输出：

```text
batch.process.done || size=100, processed=42
```

如果发生异常：

```python
with log_context("batch.process", size=100):
    raise RuntimeError("disk full")
```

输出：

```text
batch.process.error || size=100, error=RuntimeError: disk full
```

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `event` | 必填 | 事件名前缀 |
| `logger` | `None` | 自定义 `Logger` 实例（默认使用全局 logcraft logger） |
| `level` | `"info"` | `.done` 事件的日志级别 |
| `**fields` | — | 在 `.done` 和 `.error` 中都包含的静态字段 |

**`ctx.bind(**fields)`** 在代码块中逐步累积字段，退出时一并输出。

**异步支持：** `log_context` 支持 `async with`：

```python
async with logger.context("api.call", endpoint="/users") as ctx:
    ctx.bind(status=200)
```

### `LogContext`

由 `log_context()` 和 `logger.context()` 返回的对象，通常不需要直接构造。

| 方法 | 说明 |
|------|------|
| `bind(**fields)` | 累积字段，在最终日志中输出 |
| `__enter__` / `__exit__` | 同步上下文管理器协议 |
| `__aenter__` / `__aexit__` | 异步上下文管理器协议 |

## 配置

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

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `"INFO"` | 未传入 `level` 参数时的默认日志级别 |
| `LOGCRAFT_LOG_DIR` | `"logs"` | 未传入 `log_dir` 参数时的默认日志目录 |

## 开发命令

```bash
make help
make install
make test
make build
make clean
make lint           # 运行 ruff 代码检查和格式化
make publish-test   # 发布到 TestPyPI
make publish        # 发布到 PyPI
```

## 实现原理

- 装饰器通过 `inspect.signature(...)` 捕获函数参数
- `self` / `cls` 参数会自动从日志字段中剔除
- 成功路径输出 `<event>.done`
- 异常路径输出 `<event>.error` 并重新抛出异常
- `@log_class` 只包装定义在 `cls.__dict__` 中的方法（不包含继承的），避免副作用
- `@log_class` 在首次调用时注入 `self._log`（如果实例尚未拥有）
- `@no_log` 通过设置 `fn._no_log = True`，供 `@log_class` 在包装前检查
