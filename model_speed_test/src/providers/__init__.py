"""
LLM Provider 模块
支持多种 LLM API：OpenAI、Anthropic Claude、Google Gemini、LMStudio、Ollama、Azure OpenAI 等
"""

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig, PROVIDER_CAPABILITIES
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

# 创建全局注册表实例
_provider_registry = ProviderRegistry()

# 注册所有 Provider
def _register_all_providers():
    # 共享同一 capability 的注册名集合。
    # 注意：注册名 ≠ PROVIDER_CAPABILITIES 字典键时，必须显式传 capability，
    # 否则 registry.create() 查不到 capability，provider_capability 不会挂上。
    openai_cap = PROVIDER_CAPABILITIES["openai"]
    anthropic_cap = PROVIDER_CAPABILITIES["anthropic"]
    local_cap = PROVIDER_CAPABILITIES["lmstudio"]

    # OpenAI 兼容 Provider（默认，包含 MiniMax、硅基流动等）
    _provider_registry.register('openai', OpenAIProvider, openai_cap)
    _provider_registry.register('compatible', OpenAIProvider, openai_cap)  # 别名
    _provider_registry.register('minimax', OpenAIProvider, openai_cap)     # MiniMax 使用 OpenAI 兼容格式
    _provider_registry.register('custom', OpenAIProvider, openai_cap)      # custom 也使用 OpenAI 兼容格式

    # Anthropic Claude
    _provider_registry.register('anthropic', AnthropicProvider, anthropic_cap)
    _provider_registry.register('claude', AnthropicProvider, anthropic_cap)  # 别名

    # Google Gemini
    _provider_registry.register('gemini', GeminiProvider, PROVIDER_CAPABILITIES["gemini"])

    # 本地模型（LMStudio、Ollama）共享 "lmstudio" capability
    _provider_registry.register('lmstudio', LMStudioProvider, local_cap)
    _provider_registry.register('ollama', OllamaProvider, local_cap)

    # Azure OpenAI
    _provider_registry.register('azure', AzureOpenAIProvider, PROVIDER_CAPABILITIES["azure"])

# 初始化注册
_register_all_providers()

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
