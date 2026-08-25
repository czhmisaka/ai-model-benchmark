"""
Provider 适配器
将新的 Provider 系统适配到现有的 ModelClient 接口
"""

import asyncio
from typing import Optional, Dict, Any, List
import logging

from .providers import get_provider_registry, BaseLLMProvider, ModelConfig
from .client import ModelClient, StreamChunk as OldStreamChunk

logger = logging.getLogger(__name__)


class ProviderAdapter:
    """
    Provider 适配器
    
    将新的 Provider 系统适配到现有的 ModelClient 接口
    使得现有代码可以使用新的 Provider 系统
    """
    
    def __init__(self, name: str, provider: str, **kwargs):
        """
        初始化适配器
        
        Args:
            name: 模型名称
            provider: Provider 类型 (openai, anthropic, gemini, lmstudio, ollama, azure)
            **kwargs: 其他参数（endpoint, api_key, model 等）
        """
        self.name = name
        self.provider_name = provider
        
        # 创建配置
        config = ModelConfig(
            name=name,
            provider=provider,
            endpoint=kwargs.get("endpoint", ""),
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", ""),
            temperature=kwargs.get("temperature", 0.7),
            top_p=kwargs.get("top_p", 1.0),
            max_tokens=kwargs.get("max_tokens", 4096),
            presence_penalty=kwargs.get("presence_penalty", 0.0),
            frequency_penalty=kwargs.get("frequency_penalty", 0.0),
            thinking_enabled=kwargs.get("thinking_enabled", True),
            timeout=kwargs.get("timeout", 300.0),
            extra_params=kwargs.get("extra_params") or {}
        )
        
        # 创建 Provider
        registry = get_provider_registry()
        self._provider = registry.create(provider, config)
        
        if not self._provider:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def chat(
        self,
        prompt: str = None,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
        stream: bool = False,
        system: Optional[str] = None,
        messages: list = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        发送聊天请求（兼容 ModelClient.chat 调用契约）
        
        Args:
            prompt: 提示词
            max_tokens: 最大 token 数
            temperature: 温度参数
            stream: 是否使用流式
            system: 系统提示（兼容别名）
            messages: 消息数组（优先于 prompt）
            system_prompt: 系统提示词（优先于 system）
            
        Returns:
            响应结果（兼容 ModelClient 格式）
        """
        # 构建消息：优先使用 messages/system_prompt（tester.py 的调用方式）
        if messages is not None:
            chat_messages = []
            sys_prompt = system_prompt if system_prompt is not None else system
            if sys_prompt:
                chat_messages.append({"role": "system", "content": sys_prompt})
            chat_messages.extend(messages)
            messages = chat_messages
        else:
            messages = []
            if system_prompt is not None:
                messages.append({"role": "system", "content": system_prompt})
            elif system:
                messages.append({"role": "system", "content": system})
            if prompt:
                messages.append({"role": "user", "content": prompt})
        
        if stream:
            return await self._stream_chat(messages, max_tokens, temperature)
        else:
            return await self._non_stream_chat(messages, max_tokens, temperature)
    
    async def _non_stream_chat(
        self,
        messages: List[Dict],
        max_tokens: int,
        temperature: Optional[float]
    ) -> Dict[str, Any]:
        """非流式聊天"""
        from .providers import Message
        
        # 转换消息格式
        provider_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        
        # 调用 Provider
        kwargs = {}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        result = await self._provider.chat(provider_messages, **kwargs)
        
        # 转换结果格式（与 ModelClient.chat 契约一致：
        # 顶层必须有 input_tokens/output_tokens，tester._test_nonstream 依赖它们判断有效性）
        return {
            "content": result.content,
            "error": result.error,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "usage": {
                "prompt_tokens": result.input_tokens,
                "completion_tokens": result.output_tokens,
                "total_tokens": result.total_tokens
            },
            "model": result.model,
            "think_content": result.think_content,
            "finish_reason": result.finish_reason
        }
    
    async def _stream_chat(
        self,
        messages: List[Dict],
        max_tokens: int,
        temperature: Optional[float]
    ) -> Dict[str, Any]:
        """流式聊天"""
        from .providers import Message
        
        # 转换消息格式
        provider_messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
        ]
        
        # 调用 Provider
        kwargs = {}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        content_parts = []
        think_content_parts = []
        
        async for chunk in self._provider.stream_chat(provider_messages, **kwargs):
            # 思考内容只进 think_content_parts，绝不同时进 content（避免双重计数）
            if chunk.is_think:
                if hasattr(chunk, 'reasoning_content') and chunk.reasoning_content:
                    think_content_parts.append(chunk.reasoning_content)
                elif chunk.content:
                    think_content_parts.append(chunk.content)
            elif chunk.content:
                content_parts.append(chunk.content)
        
        return {
            "content": "".join(content_parts),
            "error": None,
            "usage": {},
            "model": self._provider.config.model,
            "think_content": "".join(think_content_parts),
            "finish_reason": "stop"
        }
    
    async def chat_stream(
        self,
        prompt: str = None,
        max_tokens: int = 4096,
        temperature: Optional[float] = None,
        messages: list = None,
        system_prompt: str = None
    ):
        """
        发送流式聊天请求
        
        Args:
            prompt: 提示词（用于兼容旧接口）
            max_tokens: 最大 token 数
            temperature: 温度参数
            messages: 消息数组（优先于 prompt）
            system_prompt: 系统提示词
            
        Yields:
            StreamChunk 对象（兼容 ModelClient 格式）
        """
        from .providers import Message
        
        # 构建消息列表
        provider_messages = []
        
        # 添加系统消息
        if system_prompt:
            provider_messages.append(Message(role="system", content=system_prompt))
        
        # 添加对话消息
        if messages:
            for msg in messages:
                provider_messages.append(Message(role=msg["role"], content=msg["content"]))
        elif prompt:
            provider_messages.append(Message(role="user", content=prompt))
        
        # 调用参数
        kwargs = {}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        
        # 调用 Provider 的流式接口
        first_chunk_sent = False
        async for provider_chunk in self._provider.stream_chat(provider_messages, **kwargs):
            # 转换为旧格式的 StreamChunk
            yield OldStreamChunk(
                content=provider_chunk.content,
                is_first=not first_chunk_sent,
                timestamp=provider_chunk.timestamp,
                is_think=provider_chunk.is_think,
                is_think_end=provider_chunk.is_think_end,
                reasoning_content=getattr(provider_chunk, 'reasoning_content', None)
            )
            first_chunk_sent = True
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        return await self._provider.test_connection()
    
    async def close(self):
        """关闭连接"""
        await self._provider.close()


def create_client_from_config(config: Dict[str, Any]) -> ProviderAdapter:
    """
    从配置创建客户端
    
    Args:
        config: 模型配置
        
    Returns:
        Provider 适配器
    """
    return ProviderAdapter(
        name=config.get("name", "unknown"),
        provider=config.get("provider", "openai"),
        endpoint=config.get("endpoint", ""),
        api_key=config.get("api_key", ""),
        model=config.get("model", ""),
        temperature=config.get("temperature", 0.7),
        top_p=config.get("top_p", 1.0),
        max_tokens=config.get("max_tokens", 4096),
        presence_penalty=config.get("presence_penalty", 0.0),
        frequency_penalty=config.get("frequency_penalty", 0.0),
        thinking_enabled=config.get("thinking_enabled", True),
        timeout=config.get("timeout", 300.0),
        extra_params=config.get("extra_params", {})
    )


# 兼容性别名
ModelClientAdapter = ProviderAdapter