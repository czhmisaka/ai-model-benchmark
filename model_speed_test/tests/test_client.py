"""
统一API客户端测试
（已同步当前实现：ModelClient 基于 Provider 系统，RetryConfig 位于 src.providers.base）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from src.client import ModelClient, StreamChunk
from src.providers.base import RetryConfig


class TestRetryConfig:
    """RetryConfig 测试（src/providers/base.py 当前接口）"""
    
    def test_default_values(self):
        """测试默认值"""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
    
    def test_custom_values(self):
        """测试自定义值"""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=10.0,
            backoff_factor=3.0
        )
        
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 10.0
        assert config.backoff_factor == 3.0
    
    def test_get_delay(self):
        """测试延迟计算（指数退避，封顶 max_delay）"""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=30.0,
            backoff_factor=2.0
        )
        
        # 第0次尝试: 1 * 2^0 = 1
        assert config.get_delay(0) == 1.0
        
        # 第1次尝试: 1 * 2^1 = 2
        assert config.get_delay(1) == 2.0
        
        # 第2次尝试: 1 * 2^2 = 4
        assert config.get_delay(2) == 4.0
    
    def test_get_delay_max(self):
        """测试延迟上限"""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=10.0,
            backoff_factor=2.0
        )
        
        # 超过最大值时应该被限制
        assert config.get_delay(10) == 10.0
    
    def test_should_retry(self):
        """测试可重试错误判断"""
        config = RetryConfig()
        
        assert config.should_retry(ConnectionError("net down")) is True
        assert config.should_retry(TimeoutError("timeout")) is True
        assert config.should_retry(ValueError("bad value")) is False


class TestModelClient:
    """ModelClient 测试（当前基于 Provider 系统的实现）"""
    
    @pytest.mark.asyncio
    async def test_init(self):
        """测试客户端初始化"""
        client = ModelClient(
            name="test-model",
            endpoint="https://api.example.com/v1/chat/completions",
            api_key="test-key",
            model="test-model"
        )
        
        assert client.name == "test-model"
        assert client.endpoint == "https://api.example.com/v1/chat/completions"
        assert client.api_key == "test-key"
        assert client.model == "test-model"
        assert client.timeout == 300.0
        assert client.provider is not None
        assert client.provider.get_provider_name() == "openai"
    
    @pytest.mark.asyncio
    async def test_init_unknown_provider_fallback(self):
        """测试未知 Provider 回退到 openai"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test-key",
            model="test",
            provider="not-exist-provider"
        )
        
        # 回退到 openai，不应抛异常
        assert client.provider is not None
    
    @pytest.mark.asyncio
    async def test_init_with_extra_params(self):
        """测试自定义参数传递"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test-key",
            model="test",
            timeout=120.0,
            temperature=0.3,
            max_tokens=2048,
            extra_params={"verify_ssl": False}
        )
        
        assert client.timeout == 120.0
        assert client.temperature == 0.3
        assert client.max_tokens == 2048
        assert client.extra_params == {"verify_ssl": False}
    
    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭连接"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test-key",
            model="test"
        )
        
        # 关闭不应抛异常
        await client.close()


class TestStreamChunk:
    """StreamChunk 测试"""
    
    def test_creation(self):
        """测试创建"""
        chunk = StreamChunk(
            content="Hello",
            is_first=True,
            timestamp=1234567890.0
        )
        
        assert chunk.content == "Hello"
        assert chunk.is_first is True
        assert chunk.timestamp == 1234567890.0
    
    def test_defaults(self):
        """测试默认值"""
        chunk = StreamChunk()
        
        assert chunk.content == ""
        assert chunk.is_first is False
        assert chunk.is_think is False
        assert chunk.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
