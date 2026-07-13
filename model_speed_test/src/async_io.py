"""异步文件 I/O 工具集

提供异步读取、写入 JSON 和文本文件的工具函数，
以及将同步 SQLite 操作委托到后台线程的执行器。

使用场景：
- recorder.py: 异步写入 manifest.json 和结果文件
- database.py: 将 sqlite3 同步操作委托到线程池
- scheduler.py: tasks.json 原子写入
- test_case_manager.py: 配置文件异步读写
- logging_utils.py: 日志文件异步写入
"""

import asyncio
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

import aiofiles

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    """获取共享线程池（延迟初始化）"""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async-io")
    return _executor


async def read_text(path: str, encoding: str = "utf-8") -> str:
    """异步读取文本文件"""
    async with aiofiles.open(path, "r", encoding=encoding) as f:
        return await f.read()


async def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """异步写入文本文件"""
    async with aiofiles.open(path, "w", encoding=encoding) as f:
        await f.write(content)


async def read_json(path: str) -> Any:
    """异步读取 JSON 文件"""
    try:
        text = await read_text(path)
        return json.loads(text)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


async def write_json(path: str, data: Any, indent: int = 2) -> None:
    """异步写入 JSON 文件"""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    await write_text(path, content)


async def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """原子写入 JSON 文件

    先写入临时文件，然后通过 os.replace() 原子替换目标文件。
    即使写入过程中进程崩溃，目标文件也不会损坏。
    """
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    dir_path = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


async def write_bytes(path: str, data: bytes) -> None:
    """异步写入二进制文件"""
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


async def run_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """在后台线程池中执行同步函数

    用于将 sqlite3.connect()、cursor.execute() 等同步阻塞操作
    委托到后台线程，避免阻塞事件循环。

    Example:
        rows = await run_in_executor(
            _sync_query, db_path, "SELECT * FROM models", ()
        )
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(get_executor(), lambda: func(*args, **kwargs))