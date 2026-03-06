"""
令牌桶限流器
用于控制 API 请求速率，避免触发限流
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    max_concurrent: int = 10       # 最大并发数
    rate_limit: float = 10.0       # 每秒最大请求数
    burst_size: int = 20            # 突发大小
    backpressure: bool = True        # 是否启用背压
    timeout: float = 120.0          # 单个请求超时（秒）


class TokenBucket:
    """令牌桶限流器"""
    
    def __init__(self, rate: float, burst: int):
        """
        初始化令牌桶
        
        Args:
            rate: 每秒生成的令牌数
            burst: 令牌桶容量
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        获取令牌
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
        
        Returns:
            是否成功获取令牌
        
        Raises:
            asyncio.TimeoutError: 获取令牌超时
        """
        start_time = time.monotonic()
        
        while True:
            async with self._lock:
                now = time.monotonic()
                # 计算时间间隔内生成的令牌数
                elapsed = now - self.last_update
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
            
            # 检查是否超时
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    raise asyncio.TimeoutError()
            
            # 等待一小段时间后重试
            await asyncio.sleep(0.01)
    
    async def release(self):
        """释放令牌（可选实现，用于归还）"""
        # 令牌桶模型中，获取的令牌通常不需要归还
        pass
    
    @property
    def available_tokens(self) -> float:
        """当前可用令牌数"""
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.burst, self.tokens + elapsed * self.rate)


class RateLimiter:
    """速率限制器（支持多个令牌桶）"""
    
    def __init__(self, config: ConcurrencyConfig):
        self.config = config
        # 主要的令牌桶用于速率限制
        self._bucket = TokenBucket(config.rate_limit, config.burst_size)
        # 信号量用于并发控制
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        # 先等待信号量（控制并发数）
        if self.config.backpressure:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.config.timeout
            )
        else:
            # 不使用背压，只在超时时抛出异常
            self._semaphore.acquire()
        
        # 再获取令牌（控制速率）
        await asyncio.wait_for(
            self._bucket.acquire(timeout=self.config.timeout),
            timeout=self.config.timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        self._semaphore.release()
        return False
    
    async def acquire(self):
        """手动获取许可（不使用上下文管理器时）"""
        await self._semaphore.acquire()
        await self._bucket.acquire()
    
    def release(self):
        """手动释放许可"""
        self._semaphore.release()
    
    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "available_tokens": round(self._bucket.available_tokens, 2),
            "max_concurrent": self.config.max_concurrent,
            "rate_limit": self.config.rate_limit,
            "burst_size": self.config.burst_size,
        }


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.start_time = time.time()
        self._lock = asyncio.Lock()
    
    async def increment(self, success: bool = True):
        """增加完成数"""
        async with self._lock:
            self.completed += 1
            if not success:
                self.failed += 1
    
    def get_progress(self) -> dict:
        """获取进度信息"""
        elapsed = time.time() - self.start_time
        if self.completed > 0:
            avg_time = elapsed / self.completed
            remaining = self.total - self.completed
            eta = avg_time * remaining
        else:
            eta = 0
        
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "success": self.completed - self.failed,
            "progress_percent": round(self.completed / self.total * 100, 1) if self.total > 0 else 0,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1),
            "requests_per_second": round(self.completed / elapsed, 2) if elapsed > 0 else 0,
        }