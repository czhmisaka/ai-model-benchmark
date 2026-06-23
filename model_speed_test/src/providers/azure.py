"""
Azure OpenAI Provider
支持 Azure OpenAI 服务的 API
"""

import json
import time
from typing import Dict, List, Any, Optional, AsyncIterator
import aiohttp
import logging

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Azure OpenAI Service Provider
    支持 Azure 部署的 OpenAI 模型
    """
    
    provider_name = "azure"
    provider_display_name = "Azure OpenAI"
    supports_thinking = True  # 取决于具体部署
    requires_api_key = True
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None

        # Azure 特定的参数
        ep = config.extra_params or {}
        self.api_version = ep.get("api_version", "2024-02-01")
        self.deployment_name = ep.get("deployment_name", config.model)
        
        # Azure 使用特殊的端点格式
        # 格式: https://{resource}.openai.azure.com/openai/deployments/{deployment}/
        if not self.config.endpoint:
            raise ValueError("Azure OpenAI requires an endpoint URL")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "api-key": self.config.api_key
        }
        return headers
    
    def _get_endpoint(self, path: str) -> str:
        """构建完整的 API 端点"""
        # 移除末尾的斜杠
        base = self.config.endpoint.rstrip('/')
        deployment = self.deployment_name.rstrip('/')
        api_version = self.api_version
        
        # 构建完整 URL
        return f"{base}/deployments/{deployment}/{path}?api-version={api_version}"
    
    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """
        发送聊天请求（非流式）
        """
        start_time = time.time()
        session = await self._get_session()
        
        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            # 构建请求体
            body = {
                "messages": [msg.to_dict() for msg in messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            if self.config.top_p != 1.0:
                body["top_p"] = self.config.top_p
            
            if self.config.presence_penalty != 0.0:
                body["presence_penalty"] = self.config.presence_penalty
            
            if self.config.frequency_penalty != 0.0:
                body["frequency_penalty"] = self.config.frequency_penalty
            
            # 发送请求
            async with session.post(
                self._get_endpoint("chat/completions"),
                headers=self._get_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Azure] API error: {response.status} - {error_text}")
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
                    model=self.deployment_name,
                    response_id=data.get("id", ""),
                    created=data.get("created", int(time.time())),
                    raw_response=data
                )
                
        except Exception as e:
            logger.error(f"[Azure] Chat error: {e}")
            return self._build_error_response(e)
    
    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        发送流式聊天请求
        """
        session = await self._get_session()
        
        try:
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            body = {
                "messages": [msg.to_dict() for msg in messages],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            
            async with session.post(
                self._get_endpoint("chat/completions"),
                headers=self._get_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Azure] Stream error: {response.status} - {error_text}")
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
                            
                            if content:
                                yield StreamChunk(
                                    content=content,
                                    is_first=False,
                                    timestamp=time.perf_counter()
                                )
                        
                        except json.JSONDecodeError:
                            continue
                
        except Exception as e:
            logger.error(f"[Azure] Stream error: {e}")
            yield StreamChunk(content="", error=str(e))
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # 发送简单的测试请求
            test_messages = [Message(role="user", content="Hi")]
            result = await self.chat(test_messages, max_tokens=10)
            
            latency_ms = (time.time() - start_time) * 1000
            
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