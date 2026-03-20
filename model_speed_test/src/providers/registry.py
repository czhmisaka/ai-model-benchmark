"""
Provider 注册表
管理和注册所有 LLM Provider
"""

from typing import Dict, Type, List, Optional, Any
from .base import BaseLLMProvider, ModelConfig, PROVIDER_CAPABILITIES, ProviderCapability


class ProviderRegistry:
    """
    Provider 注册表
    管理所有可用的 LLM Provider
    """
    
    def __init__(self):
        self._providers: Dict[str, Type[BaseLLMProvider]] = {}
        self._capabilities: Dict[str, ProviderCapability] = {}
        
        # 初始化预定义能力
        self._capabilities.update(PROVIDER_CAPABILITIES)
    
    def register(
        self,
        name: str,
        provider_class: Type[BaseLLMProvider],
        capability: Optional[ProviderCapability] = None
    ) -> None:
        """
        注册一个 Provider
        
        Args:
            name: Provider 名称
            provider_class: Provider 类
            capability: Provider 能力描述（可选）
        """
        if not issubclass(provider_class, BaseLLMProvider):
            raise TypeError(f"{provider_class} 必须继承自 BaseLLMProvider")
        
        self._providers[name.lower()] = provider_class
        
        if capability:
            self._capabilities[name.lower()] = capability
    
    def get(self, name: str) -> Optional[Type[BaseLLMProvider]]:
        """
        获取 Provider 类
        
        Args:
            name: Provider 名称
            
        Returns:
            Provider 类，如果不存在则返回 None
        """
        return self._providers.get(name.lower())
    
    def create(self, name: str, config: ModelConfig) -> Optional[BaseLLMProvider]:
        """
        创建 Provider 实例
        
        Args:
            name: Provider 名称
            config: 模型配置
            
        Returns:
            Provider 实例，如果不存在则返回 None
        """
        provider_class = self.get(name)
        if not provider_class:
            return None
        
        # 确保配置中的 provider 名称一致
        if config.provider != name:
            config.provider = name
        
        return provider_class(config)
    
    def list_providers(self) -> List[str]:
        """
        列出所有注册的 Provider
        
        Returns:
            Provider 名称列表
        """
        return list(self._providers.keys())
    
    def get_capability(self, name: str) -> Optional[ProviderCapability]:
        """
        获取 Provider 能力描述
        
        Args:
            name: Provider 名称
            
        Returns:
            Provider 能力描述
        """
        return self._capabilities.get(name.lower())
    
    def get_all_capabilities(self) -> Dict[str, ProviderCapability]:
        """
        获取所有 Provider 能力描述
        
        Returns:
            能力描述字典
        """
        return self._capabilities.copy()
    
    def is_registered(self, name: str) -> bool:
        """
        检查 Provider 是否已注册
        
        Args:
            name: Provider 名称
            
        Returns:
            是否已注册
        """
        return name.lower() in self._providers
    
    def unregister(self, name: str) -> bool:
        """
        注销 Provider
        
        Args:
            name: Provider 名称
            
        Returns:
            是否成功注销
        """
        name_lower = name.lower()
        if name_lower in self._providers:
            del self._providers[name_lower]
            return True
        return False


# 全局注册装饰器
def register_provider(
    name: str,
    capability: Optional[ProviderCapability] = None
):
    """
    Provider 注册装饰器
    
    用法:
        @register_provider("openai")
        class MyOpenAIProvider(BaseLLMProvider):
            ...
    
    Args:
        name: Provider 名称
        capability: Provider 能力描述（可选）
    """
    def decorator(cls: Type[BaseLLMProvider]):
        registry = ProviderRegistry()
        registry.register(name, cls, capability)
        return cls
    return decorator


class ProviderFactory:
    """
    Provider 工厂类
    简化 Provider 创建流程
    """
    
    def __init__(self, registry: Optional[ProviderRegistry] = None):
        self.registry = registry or ProviderRegistry()
    
    def create_from_dict(self, config_dict: Dict[str, Any]) -> Optional[BaseLLMProvider]:
        """
        从字典配置创建 Provider
        
        Args:
            config_dict: 配置字典，包含:
                - provider: Provider 类型
                - name: 显示名称
                - endpoint: API 端点
                - api_key: API 密钥
                - model: 模型名称
                - 及其他可选参数
                
        Returns:
            Provider 实例
        """
        # 创建配置对象
        config = ModelConfig(
            name=config_dict.get("name", "Unknown"),
            provider=config_dict.get("provider", "openai"),
            endpoint=config_dict.get("endpoint", ""),
            api_key=config_dict.get("api_key", ""),
            model=config_dict.get("model", ""),
            temperature=config_dict.get("temperature", 0.7),
            top_p=config_dict.get("top_p", 1.0),
            max_tokens=config_dict.get("max_tokens", 4096),
            presence_penalty=config_dict.get("presence_penalty", 0.0),
            frequency_penalty=config_dict.get("frequency_penalty", 0.0),
            thinking_enabled=config_dict.get("thinking_enabled", True),
            timeout=config_dict.get("timeout", 300.0),
            extra_params=config_dict.get("extra_params", {})
        )
        
        return self.create(config)
    
    def create(self, config: ModelConfig) -> Optional[BaseLLMProvider]:
        """
        从 ModelConfig 创建 Provider
        
        Args:
            config: 模型配置
            
        Returns:
            Provider 实例
        """
        return self.registry.create(config.provider, config)
    
    def list_available(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的 Provider
        
        Returns:
            Provider 信息列表
        """
        result = []
        for name in self.registry.list_providers():
            capability = self.registry.get_capability(name)
            provider_class = self.registry.get(name)
            
            info = {
                "name": name,
                "display_name": capability.display_name if capability else name,
                "description": capability.description if capability else "",
                "supports_streaming": capability.supports_streaming if capability else True,
                "supports_thinking": capability.supports_thinking if capability else False,
                "requires_api_key": capability is None or getattr(provider_class, 'requires_api_key', True) if provider_class else True,
                "default_max_tokens": capability.default_max_tokens if capability else 4096,
            }
            result.append(info)
        
        return result


# 便捷函数
def get_default_factory() -> ProviderFactory:
    """获取默认的 Provider 工厂"""
    from . import get_provider_registry
    return ProviderFactory(get_provider_registry())