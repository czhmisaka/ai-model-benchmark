"""
LLM 客户端适配器
提供统一的接口访问各种 LLM API
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass
import aiohttp

from .providers import get_provider_registry, BaseLLMProvider
from .providers.base import Message

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """流式响应块"""
    content: str = ""
    is_first: bool = False
    timestamp: float = 0.0
    is_think: bool = False
    is_think_end: bool = False
    error: Optional[str] = None
    reasoning_content: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class ModelClient:
    """
    模型客户端 - 统一接口
    支持 OpenAI、MiniMax、Anthropic、Google Gemini 等多种 API
    """
    
    def __init__(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        model: str,
        provider: str = "openai",
        timeout: float = 300.0,
        extra_params: Dict[str, Any] = None,
        temperature: float = 0.7,
        top_p: float = 1.0,
        max_tokens: int = 4096,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
        thinking_enabled: bool = True
    ):
        self.name = name
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.provider_type = provider
        self.timeout = timeout
        self.extra_params = extra_params or {}
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.thinking_enabled = thinking_enabled
        
        registry = get_provider_registry()
        provider_class = registry.get(provider)
        if provider_class is None:
            provider_class = registry.get("openai")
        
        from .providers.base import ModelConfig
        config = ModelConfig(
            name=name,
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            provider=provider,
            timeout=timeout,
            extra_params=extra_params,
            thinking_enabled=thinking_enabled,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty
        )
        
        self.provider = provider_class(config)
        logger.info(f"[ModelClient] 初始化 {name} (provider={provider}, model={model})")
    
    async def chat(
        self,
        prompt: str = None,
        messages: list = None,
        system_prompt: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        chat_messages = []
        
        if system_prompt:
            chat_messages.append(Message(role="system", content=system_prompt))
        
        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    chat_messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))
                else:
                    chat_messages.append(msg)
        elif prompt:
            chat_messages.append(Message(role="user", content=prompt))
        
        if stream:
            full_content = ""
            reasoning_content = ""
            first_token_time = None
            chunks = []
            
            async for chunk in self.provider.stream_chat(chat_messages, max_tokens=max_tokens, temperature=temperature, **kwargs):
                if chunk.error:
                    return {"error": chunk.error}
                
                if chunk.is_first and first_token_time is None:
                    first_token_time = time.time()
                
                if chunk.reasoning_content:
                    reasoning_content += chunk.reasoning_content
                    full_content += chunk.reasoning_content
                
                full_content += chunk.content
                
                chunks.append({
                    "content": chunk.content,
                    "timestamp": chunk.timestamp,
                    "is_think": chunk.is_think
                })
            
            return {
                "content": full_content,
                "reasoning_content": reasoning_content if reasoning_content else None,
                "chunks": chunks,
                "usage": chunks[-1].get("usage") if chunks else None
            }
        else:
            result = await self.provider.chat(chat_messages, max_tokens=max_tokens, temperature=temperature, **kwargs)
            
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
                } if result.input_tokens or result.output_tokens else None
            }
    
    async def chat_stream(
        self,
        prompt: str = None,
        messages: list = None,
        system_prompt: str = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """发送流式聊天请求"""
        chat_messages = []
        
        if system_prompt:
            chat_messages.append(Message(role="system", content=system_prompt))
        
        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    chat_messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))
                else:
                    chat_messages.append(msg)
        elif prompt:
            chat_messages.append(Message(role="user", content=prompt))
        
        is_first = True
        is_in_think = False
        
        async for chunk in self.provider.stream_chat(chat_messages, max_tokens=max_tokens, temperature=temperature, **kwargs):
            # 检查是否有错误
            chunk_error = getattr(chunk, 'error', None)
            if chunk_error:
                yield StreamChunk(content="", error=chunk_error)
                continue
            
            content = getattr(chunk, 'content', '') or ''
            is_think = getattr(chunk, 'is_think', False)
            is_think_end = getattr(chunk, 'is_think_end', False)
            
            # 如果有 reasoning_content，标记为 think
            chunk_reasoning = getattr(chunk, 'reasoning_content', None)
            if chunk_reasoning:
                is_think = True
            
            # 如果是 miniMax 格式，检测 <begin_of_thought> 标签
            if '<begin_of_thought>' in content:
                is_in_think = True
                is_think = True
            if '<end_of_thought>' in content:
                is_in_think = False
                is_think_end = True
            
            yield StreamChunk(
                content=content,
                is_first=is_first,
                timestamp=getattr(chunk, 'timestamp', time.perf_counter()),
                is_think=is_think or is_in_think,
                is_think_end=is_think_end,
                reasoning_content=chunk_reasoning,
                usage=getattr(chunk, 'usage', None)
            )
            
            is_first = False
    
    async def close(self):
        """关闭客户端连接"""
        await self.provider.close()


def create_model_clients(config: Dict[str, Any]) -> List[ModelClient]:
    """从配置创建多个模型客户端"""
    clients = []
    models = config.get("models", [])
    
    for model_config in models:
        if not model_config.get("enabled", True):
            continue
        
        try:
            client = ModelClient(
                name=model_config["name"],
                endpoint=model_config.get("endpoint", ""),
                api_key=model_config.get("api_key", ""),
                model=model_config.get("model", model_config["name"]),
                provider=model_config.get("provider", "openai"),
                timeout=model_config.get("timeout", 300.0),
                extra_params=model_config.get("extra_params")
            )
            clients.append(client)
            logger.info(f"[ModelClient] 创建客户端: {model_config['name']}")
        except Exception as e:
            logger.error(f"[ModelClient] 创建客户端失败 {model_config.get('name', 'unknown')}: {e}")
    
    return clients