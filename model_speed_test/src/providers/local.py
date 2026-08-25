"""
本地模型 Provider
支持 LMStudio、Ollama 等本地部署的模型
"""

import json
import time
from typing import Dict, List, Any, Optional, AsyncIterator
import aiohttp
import logging

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig
from .base import extract_text_for_log

logger = logging.getLogger(__name__)


class LMStudioProvider(BaseLLMProvider):
    """
    LMStudio 本地模型 Provider
    LMStudio 使用 OpenAI 兼容的 API 格式
    """
    
    provider_name = "lmstudio"
    provider_display_name = "LM Studio"
    supports_thinking = True  # 取决于具体模型
    requires_api_key = False  # 本地部署不需要 API Key
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # LMStudio 默认配置
        if not self.config.endpoint:
            self.config.endpoint = "http://localhost:1234/v1"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json"
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求（非流式）
        """
        self.validate_vision_capability(messages)
        start_time = time.time()
        session = await self._get_session()

        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)

            # 构建请求体（OpenAI 兼容格式）
            body = {
                "messages": [msg.to_dict() for msg in messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "model": self.config.model or "local-model",
            }
            
            if self.config.top_p != 1.0:
                body["top_p"] = self.config.top_p
            
            if self.config.presence_penalty != 0.0:
                body["presence_penalty"] = self.config.presence_penalty
            
            if self.config.frequency_penalty != 0.0:
                body["frequency_penalty"] = self.config.frequency_penalty
            
            # LMStudio 特定的参数
            extra_params = self.config.extra_params or {}
            if "seed" in extra_params:
                body["seed"] = extra_params["seed"]
            if "stop" in extra_params:
                body["stop"] = extra_params["stop"]
            
            # 发送请求
            async with session.post(
                f"{self.config.endpoint}/chat/completions",
                headers=self._get_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[LMStudio] API error: {response.status} - {error_text}")
                    return LLMResponse(
                        error=f"API error {response.status}: {error_text}"
                    )
                
                data = await response.json()
                
                # 解析响应（OpenAI 格式）
                choices = data.get("choices", [])
                if not choices:
                    return LLMResponse(error="No response from model")
                
                message = choices[0].get("message", {})
                usage = data.get("usage", {})
                
                return LLMResponse(
                    content=message.get("content", ""),
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    finish_reason=choices[0].get("finish_reason", ""),
                    model=data.get("model", self.config.model),
                    response_id=data.get("id", ""),
                    created=data.get("created", int(time.time())),
                    raw_response=data
                )
                
        except Exception as e:
            logger.error(f"[LMStudio] Chat error: {e}")
            return self._build_error_response(e)
    
    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        发送流式聊天请求
        """
        self.validate_vision_capability(messages)
        session = await self._get_session()

        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)

            body = {
                "messages": [msg.to_dict() for msg in messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                "model": self.config.model or "local-model",
            }
            
            async with session.post(
                f"{self.config.endpoint}/chat/completions",
                headers=self._get_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[LMStudio] Stream error: {response.status} - {error_text}")
                    yield StreamChunk(content="", error=f"API error {response.status}")
                    return
                
                # 解析 SSE 流
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line or line.startswith(':'):
                        continue
                    
                    if line.startswith('data: '):
                        data_str = line[6:]
                        
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            # 兼容 reasoning_content / reasoning 字段（思考型模型）
                            reasoning_content = delta.get("reasoning_content") or delta.get("reasoning") or ""
                            finish_reason = choices[0].get("finish_reason") or ""
                            
                            has_content = bool(content) or bool(reasoning_content)
                            # 跳过纯 role 初始化块（不消耗 is_first）
                            if not has_content and not finish_reason:
                                continue
                            
                            is_think = bool(reasoning_content)
                            yield StreamChunk(
                                content=content,
                                is_first=has_content and not is_think,
                                timestamp=time.perf_counter(),
                                is_think=is_think,
                                reasoning_content=reasoning_content or None,
                                finish_reason=finish_reason,
                                usage=data.get("usage", {})
                            )
                        
                        except json.JSONDecodeError:
                            continue
                
        except Exception as e:
            logger.error(f"[LMStudio] Stream error: {e}")
            yield StreamChunk(content="", error=str(e))
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # 尝试获取模型列表
            async with session.get(
                f"{self.config.endpoint}/models",
                headers=self._get_headers()
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    return self._build_test_success(
                        latency_ms,
                        "Connection successful"
                    )
                else:
                    # 如果 /models 端点不可用，尝试聊天请求
                    test_messages = [Message(role="user", content="Hi")]
                    result = await self.chat(test_messages, max_tokens=10)
                    
                    if result.error:
                        return self._build_test_error(result.error, latency_ms)
                    
                    return self._build_test_success(
                        latency_ms,
                        result.content[:100] if result.content else ""
                    )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return self._build_test_error(str(e), latency_ms)
    
    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


class OllamaProvider(BaseLLMProvider):
    """
    Ollama 本地模型 Provider
    Ollama 使用自己特有的 API 格式
    """
    
    provider_name = "ollama"
    provider_display_name = "Ollama"
    supports_thinking = False
    requires_api_key = False  # 本地部署不需要 API Key
    
    # Ollama API 配置
    API_BASE = "http://localhost:11434/api"
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Ollama 默认配置
        if not self.config.endpoint:
            self.config.endpoint = self.API_BASE
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _convert_messages(self, messages: List[Message]) -> str:
        """
        转换消息格式

        Ollama 使用简单的文本格式，不支持多模态。
        多模态 content 已由 validate_vision_capability() 在 chat/stream_chat 入口拒绝。
        """
        text = ""
        for msg in messages:
            content_text = extract_text_for_log(msg.content)
            if msg.role == "system":
                text += f"System: {content_text}\n"
            else:
                role = "User" if msg.role == "user" else "Assistant"
                text += f"{role}: {content_text}\n"

        return text.strip()
    
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求（非流式）
        """
        self.validate_vision_capability(messages)
        start_time = time.time()
        session = await self._get_session()

        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)

            # Ollama 特定的请求格式
            body = {
                "model": self.config.model,
                "prompt": self._convert_messages(messages),
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            
            # 发送请求
            async with session.post(
                f"{self.config.endpoint}/generate",
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Ollama] API error: {response.status} - {error_text}")
                    return LLMResponse(
                        error=f"API error {response.status}: {error_text}"
                    )
                
                data = await response.json()
                
                return LLMResponse(
                    content=data.get("response", ""),
                    input_tokens=0,  # Ollama 不总是提供这个
                    output_tokens=data.get("eval_count", 0),
                    total_tokens=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
                    finish_reason=data.get("done_reason", ""),
                    model=self.config.model,
                    raw_response=data
                )
                
        except Exception as e:
            logger.error(f"[Ollama] Chat error: {e}")
            return self._build_error_response(e)
    
    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        发送流式聊天请求
        """
        self.validate_vision_capability(messages)
        session = await self._get_session()

        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)

            body = {
                "model": self.config.model,
                "prompt": self._convert_messages(messages),
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
                "stream": True
            }
            
            async with session.post(
                f"{self.config.endpoint}/generate",
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Ollama] Stream error: {response.status} - {error_text}")
                    yield StreamChunk(content="", error=f"API error {response.status}")
                    return
                
                # 解析流式响应（每行一个 JSON）
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        
                        content = data.get("response", "")
                        if content:
                            yield StreamChunk(
                                content=content,
                                is_first=False,
                                timestamp=time.perf_counter()
                            )
                        
                        if data.get("done", False):
                            break
                    
                    except json.JSONDecodeError:
                        continue
                
        except Exception as e:
            logger.error(f"[Ollama] Stream error: {e}")
            yield StreamChunk(content="", error=str(e))
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # 检查 Ollama 服务是否运行
            async with session.get(
                f"{self.config.endpoint}/tags"
            ) as response:
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status == 200:
                    models_data = await response.json()
                    models = models_data.get("models", [])
                    model_names = [m.get("name", "") for m in models[:5]]
                    
                    return {
                        "success": True,
                        "latency_ms": latency_ms,
                        "message": f"Connected. Available models: {', '.join(model_names)}"
                    }
                else:
                    return self._build_test_error(
                        f"Connection failed: {response.status}",
                        latency_ms
                    )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return self._build_test_error(str(e), latency_ms)
    
    async def close(self):
        """关闭连接"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None