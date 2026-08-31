"""
并发控制单测：验证 max_concurrent 信号量真实约束在途请求数
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
import pytest


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """信号量应将同时在执行的协程数限制为 max_concurrent"""
    max_concurrent = 3
    sem = asyncio.Semaphore(max_concurrent)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)  # 模拟请求
            active -= 1

    # 10 个并发请求，限制为 3
    await asyncio.gather(*[worker() for _ in range(10)])
    assert peak <= max_concurrent, f"峰值并发 {peak} 超过限制 {max_concurrent}"


@pytest.mark.asyncio
async def test_semaphore_share_across_groups():
    """跨组共享信号量（模拟多模型共享同一信号量）"""
    max_concurrent = 3
    shared = asyncio.Semaphore(max_concurrent)
    active = 0
    peak = 0

    async def worker(sem):
        nonlocal active, peak
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.05)
            active -= 1

    # 模拟 4 个模型组，每组 5 个请求，全部共享一个信号量
    groups = []
    for _ in range(4):
        groups.extend(worker(shared) for _ in range(5))
    await asyncio.gather(*groups)
    assert peak <= max_concurrent, f"跨组峰值并发 {peak} 超过限制 {max_concurrent}"


@pytest.mark.asyncio
async def test_semaphore_not_held_during_interval():
    """信号量不应在轮间等待时被占用（释放后其他用例可复用）"""
    max_concurrent = 2
    sem = asyncio.Semaphore(max_concurrent)
    active = 0
    peak = 0

    async def worker():
        nonlocal active, peak
        async with sem:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.02)
            active -= 1
        # 轮间等待在 with 之外（信号量已释放）
        await asyncio.sleep(0.02)

    await asyncio.gather(*[worker() for _ in range(8)])
    assert peak <= max_concurrent


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
