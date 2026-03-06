"""
统一API客户端测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from src.client import ModelClient, RetryConfig, StreamChunk


class TestRetryConfig:
    """RetryConfig 测试"""
    
    def test_default_values(self):
        """测试默认值"""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
    
    def test_custom_values(self):
        """测试自定义值"""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=10.0,
            exponential_base=3.0
        )
        
        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential_base == 3.0
    
    def test_get_delay(self):
        """测试延迟计算"""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0
        )
        
        # 第0次尝试: 1 * 2^0 = 1
        assert config.get_delay(0) == 1.0
        
        # 第1次尝试: 1 * 2^1 = 2
        assert config.get_delay(1) == 2.0
        
        # 第2次尝试: 1 * 2^2 = 4
        assert config.get_delay(2) == 4.0
        
        # 第3次尝试: 1 * 2^3 = 8
        assert config.get_delay(3) == 8.0
    
    def test_get_delay_max(self):
        """测试延迟上限"""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0
        )
        
        # 超过最大值时应该被限制
        assert config.get_delay(10) == 10.0


class TestModelClient:
    """ModelClient 测试"""
    
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
        assert client.timeout == 120
        assert client.retry_config is not None
    
    @pytest.mark.asyncio
    async def test_init_with_retry_config(self):
        """测试带重试配置的初始化"""
        retry_config = RetryConfig(max_retries=5)
        client = ModelClient(
            name="test-model",
            endpoint="https://api.example.com/v1/chat/completions",
            api_key="test-key",
            model="test-model",
            retry_config=retry_config
        )
        
        assert client.retry_config.max_retries == 5
    
    def test_get_headers_without_key(self):
        """测试无API Key的请求头"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="",
            model="test"
        )
        
        headers = client._get_headers()
        assert "Authorization" not in headers
    
    def test_get_headers_with_key(self):
        """测试带API Key的请求头"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test-key-123",
            model="test"
        )
        
        headers = client._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-key-123"
    
    def test_get_headers_expands_env_vars(self):
        """测试环境变量展开"""
        import os
        os.environ["TEST_API_KEY"] = "env-key-123"
        
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="${TEST_API_KEY}",
            model="test"
        )
        
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer env-key-123"
        
        del os.environ["TEST_API_KEY"]
    
    def test_build_messages_with_prompt(self):
        """测试使用简单prompt构建消息"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test",
            model="test"
        )
        
        messages = client._build_messages(prompt="Hello")
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
    
    def test_build_messages_with_system_prompt(self):
        """测试使用系统提示词构建消息"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test",
            model="test"
        )
        
        messages = client._build_messages(
            prompt="Hello",
            system_prompt="You are a helpful assistant."
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"
    
    def test_build_messages_with_messages(self):
        """测试使用消息数组"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test",
            model="test"
        )
        
        input_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ]
        
        messages = client._build_messages(messages=input_messages)
        
        assert messages == input_messages
    
    def test_build_messages_default(self):
        """测试默认消息"""
        client = ModelClient(
            name="test",
            endpoint="https://api.example.com",
            api_key="test",
            model="test"
        )
        
        messages = client._build_messages()
        
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "你好"


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])