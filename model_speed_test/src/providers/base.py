"""
LLM Provider 基类和通用数据结构
定义所有 Provider 必须实现的接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
import time


@dataclass
class StreamChunk:
    """流式响应数据块"""
    content: str = ""                    # 内容
    is_first: bool = False               # 是否是第一个块
    timestamp: float = 0.0              # 时间戳
    is_think: bool = False               # 是否是思考内容（think标签内）
    is_think_end: bool = False           # 是否是思考结束
    reasoning_content: str = ""          # 推理内容（某些Provider使用）
    usage: Dict[str, int] = field(default_factory=dict)  # Token使用量
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.perf_counter()


@dataclass
class LLMResponse:
    """非流式响应数据"""
    content: str = ""                    # 响应内容
    input_tokens: int = 0                # 输入Token数
    output_tokens: int = 0               # 输出Token数
    total_tokens: int = 0                # 总Token数
    finish_reason: str = ""               # 结束原因（stop, length, content_filter, etc）
    model: str = ""                       # 实际使用的模型
    response_id: str = ""                 # 响应ID
    created: int = 0                      # 创建时间戳
    raw_response: Dict[str, Any] = field(default_factory=dict)  # 原始响应
    think_content: str = ""               # 思考内容（如果有）
    error: Optional[str] = None           # 错误信息（如果有）


@dataclass
class Message:
    """消息数据结构"""
    role: str                             # system, user, assistant
    content: str                           # 消息内容
    name: Optional[str] = None             # 名称（用于function调用）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建"""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name")
        )


@dataclass
class ModelConfig:
    """模型配置"""
    name: str                              # 显示名称
    provider: str = "openai"                # Provider类型
    endpoint: str = ""                      # API端点
    api_key: str = ""                       # API密钥
    model: str = ""                         # 模型名称
    temperature: float = 0.7                # 温度
    top_p: float = 1.0                     # Top-P
    max_tokens: int = 4096                 # 最大Token数
    presence_penalty: float = 0.0           # Presence Penalty
    frequency_penalty: float = 0.0          # Frequency Penalty
    thinking_enabled: bool = True           # 是否启用思考模式
    timeout: float = 300.0                 # 超时时间（秒）
    extra_params: Dict[str, Any] = field(default_factory=dict)  # 额外参数
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "thinking_enabled": self.thinking_enabled,
            "timeout": self.timeout,
            **self.extra_params
        }


class BaseLLMProvider(ABC):
    """
    LLM Provider 基类
    所有 Provider 必须实现以下抽象方法
    """
    
    # Provider 元信息
    provider_name: str = "base"
    provider_display_name: str = "Base Provider"
    supports_streaming: bool = True
    supports_thinking: bool = False
    requires_api_key: bool = True
    
    def __init__(self, config: ModelConfig):
        """
        初始化 Provider
        
        Args:
            config: 模型配置
        """
        self.config = config
        self._session = None  # HTTP会话（子类实现）
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求（非流式）
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 响应对象
        """
        pass
    
    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        发送流式聊天请求
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            StreamChunk: 流式数据块
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            Dict: 包含 success, latency_ms, error 等字段
        """
        pass
    
    def get_provider_name(self) -> str:
        """获取 Provider 名称"""
        return self.provider_name
    
    def get_display_name(self) -> str:
        """获取显示名称"""
        return self.provider_display_name
    
    async def close(self):
        """关闭连接，清理资源"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _build_error_response(self, error: Exception) -> LLMResponse:
        """构建错误响应"""
        return LLMResponse(
            content="",
            error=str(error),
            raw_response={"error_type": type(error).__name__}
        )
    
    def _build_test_error(self, error: str, latency_ms: float = 0) -> Dict[str, Any]:
        """构建测试连接错误结果"""
        return {
            "success": False,
            "error": error,
            "latency_ms": latency_ms,
            "provider": self.provider_name
        }
    
    def _build_test_success(self, latency_ms: float, response_preview: str = "") -> Dict[str, Any]:
        """构建测试连接成功结果"""
        return {
            "success": True,
            "latency_ms": latency_ms,
            "response_preview": response_preview,
            "provider": self.provider_name
        }


class ThinkingConfig:
    """思考模式配置"""
    
    def __init__(
        self,
        enabled: bool = True,
        budget_tokens: Optional[int] = None,
        include_thoughts: bool = True
    ):
        self.enabled = enabled
        self.budget_tokens = budget_tokens
        self.include_thoughts = include_thoughts


class ProviderCapability:
    """Provider 能力描述"""
    
    def __init__(
        self,
        name: str,
        display_name: str,
        api_format: str,  # openai, anthropic, gemini, etc.
        supports_streaming: bool = True,
        supports_thinking: bool = False,
        supports_functions: bool = False,
        supports_vision: bool = False,
        supports_json_mode: bool = False,
        default_max_tokens: int = 4096,
        max_context_length: int = 128000,
        description: str = ""
    ):
        self.name = name
        self.display_name = display_name
        self.api_format = api_format
        self.supports_streaming = supports_streaming
        self.supports_thinking = supports_thinking
        self.supports_functions = supports_functions
        self.supports_vision = supports_vision
        self.supports_json_mode = supports_json_mode
        self.default_max_tokens = default_max_tokens
        self.max_context_length = max_context_length
        self.description = description


# 预定义的 Provider 能力
PROVIDER_CAPABILITIES = {
    "openai": ProviderCapability(
        name="openai",
        display_name="OpenAI 兼容",
        api_format="openai",
        supports_streaming=True,
        supports_thinking=False,
        supports_functions=True,
        supports_vision=True,
        supports_json_mode=True,
        default_max_tokens=4096,
        max_context_length=128000,
        description="OpenAI 兼容格式，支持 GPT-4、GPT-3.5 等模型"
    ),
    "anthropic": ProviderCapability(
        name="anthropic",
        display_name="Anthropic Claude",
        api_format="anthropic",
        supports_streaming=True,
        supports_thinking=True,
        supports_functions=False,
        supports_vision=True,
        supports_json_mode=True,
        default_max_tokens=4096,
        max_context_length=200000,
        description="Anthropic Claude 系列模型，支持 Extended Thinking"
    ),
    "gemini": ProviderCapability(
        name="gemini",
        display_name="Google Gemini",
        api_format="gemini",
        supports_streaming=True,
        supports_thinking=False,
        supports_functions=True,
        supports_vision=True,
        supports_json_mode=True,
        default_max_tokens=8192,
        max_context_length=2000000,
        description="Google Gemini 系列模型，超长上下文"
    ),
    "local": ProviderCapability(
        name="local",
        display_name="本地模型 (LMStudio/Ollama)",
        api_format="openai",
        supports_streaming=True,
        supports_thinking=True,  # 取决于模型
        supports_functions=False,
        supports_vision=False,
        supports_json_mode=True,
        default_max_tokens=4096,
        max_context_length=128000,
        description="本地部署的模型，如 LMStudio、Ollama 等"
    ),
    "azure": ProviderCapability(
        name="azure",
        display_name="Azure OpenAI",
        api_format="openai",
        supports_streaming=True,
        supports_thinking=False,
        supports_functions=True,
        supports_vision=True,
        supports_json_mode=True,
        default_max_tokens=4096,
        max_context_length=128000,
        description="微软 Azure OpenAI Service"
    )
}