"""
LLM Provider 模块
支持多种 LLM API：OpenAI、Anthropic Claude、Google Gemini、LMStudio、Ollama、Azure OpenAI 等
"""

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig
from .registry import ProviderRegistry, register_provider

# 导入所有 Provider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .local import LMStudioProvider, OllamaProvider
from .azure import AzureOpenAIProvider

# 默认注册所有 Provider
def _register_all_providers():
    registry = ProviderRegistry()
    
    # OpenAI 兼容 Provider（默认，包含 MiniMax、硅基流动等）
    registry.register('openai', OpenAIProvider)
    registry.register('compatible', OpenAIProvider)  # 别名
    
    # Anthropic Claude
    registry.register('anthropic', AnthropicProvider)
    registry.register('claude', AnthropicProvider)  # 别名
    
    # Google Gemini
    registry.register('gemini', GeminiProvider)
    
    # 本地模型（LMStudio、Ollama）
    registry.register('lmstudio', LMStudioProvider)
    registry.register('ollama', OllamaProvider)
    
    # Azure OpenAI
    registry.register('azure', AzureOpenAIProvider)
    
    return registry

# 全局注册表实例
_provider_registry = _register_all_providers()

def get_provider_registry() -> ProviderRegistry:
    """获取 Provider 注册表"""
    return _provider_registry

__all__ = [
    'BaseLLMProvider',
    'LLMResponse',
    'StreamChunk',
    'Message',
    'ModelConfig',
    'ProviderRegistry',
    'register_provider',
    'OpenAIProvider',
    'AnthropicProvider',
    'GeminiProvider',
    'LMStudioProvider',
    'OllamaProvider',
    'AzureOpenAIProvider',
    'get_provider_registry',
]
