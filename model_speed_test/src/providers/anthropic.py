"""
Anthropic Claude Provider
支持 Claude 系列模型的 API
"""

import json
import time
from typing import Dict, List, Any, Optional, AsyncIterator, AsyncGenerator
import aiohttp
import logging

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig
from .base import normalize_content, extract_text_for_log

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude API Provider
    支持 Claude 3.5+ 系列模型的 Extended Thinking
    """
    
    provider_name = "anthropic"
    provider_display_name = "Anthropic Claude"
    supports_thinking = True
    requires_api_key = True
    
    # Anthropic API 配置
    API_BASE = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Anthropic 特定的参数
        self.thinking_budget = config.extra_params.get("thinking_budget_tokens", 10000)
        self.include_thoughts = config.thinking_enabled
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": self.API_VERSION,
            "anthropic-dangerous-direct-browser-access": "true"
        }
        return headers
    
    def _convert_messages(self, messages: List[Message]) -> Dict[str, Any]:
        """
        转换消息格式

        Anthropic 使用不同的消息格式:
        - system 消息作为单独字段
        - 不支持 function 调用
        - 多模态：content 是 block 列表；图片支持 url 与 base64 两种 source
        """
        # 分离 system 消息
        system_prompt = ""
        converted_messages = []

        for msg in messages:
            if msg.role == "system":
                # system 始终是纯文本
                system_prompt += extract_text_for_log(msg.content) + "\n"
                continue

            parts = normalize_content(msg.content)
            blocks: List[Dict[str, Any]] = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    blocks.append({"type": "text", "text": part.get("text", "")})
                elif ptype in ("image_url", "image"):
                    url = ""
                    if ptype == "image_url":
                        url = (part.get("image_url") or {}).get("url", "")
                    else:
                        # 已构造好的 Anthropic 风格 image block
                        src = part.get("source") or {}
                        url = src.get("url") or src.get("data") or ""
                    if url.startswith(("http://", "https://")):
                        blocks.append({
                            "type": "image",
                            "source": {"type": "url", "url": url},
                        })
                    elif url.startswith("data:"):
                        # data:<mime>;base64,<b64>
                        try:
                            header, b64 = url.split(",", 1)
                            mime = header.split(":", 1)[1].split(";", 1)[0]
                        except Exception:
                            mime, b64 = "image/png", url
                        blocks.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": mime, "data": b64},
                        })
                    else:
                        # 兜底当作 base64 处理
                        blocks.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": url},
                        })

            if not blocks:
                blocks = [{"type": "text", "text": ""}]

            converted_messages.append({
                "role": msg.role,
                "content": blocks,
            })

        return {
            "system": system_prompt.strip() or None,
            "messages": converted_messages
        }
    
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
            # 构建请求体
            converted = self._convert_messages(messages)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            body = {
                "model": self.config.model,
                "messages": converted["messages"],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            if converted["system"]:
                body["system"] = converted["system"]
            
            # 添加 thinking 扩展（如果启用）
            if self.config.thinking_enabled:
                body["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                }
            
            # 发送请求
            async with session.post(
                f"{self.API_BASE}/messages",
                headers=self._build_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Anthropic] API error: {response.status} - {error_text}")
                    return LLMResponse(
                        error=f"API error {response.status}: {error_text}"
                    )
                
                data = await response.json()
                
                # 解析响应
                content = data.get("content", [])
                thinking_content = ""
                answer_content = ""
                
                for block in content:
                    if block.get("type") == "thinking":
                        thinking_content += block.get("thinking", "")
                    elif block.get("type") == "text":
                        answer_content += block.get("text", "")
                
                # 获取 usage 信息
                usage = data.get("usage", {})
                
                return LLMResponse(
                    content=answer_content,
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    finish_reason=data.get("stop_reason", ""),
                    model=data.get("model", self.config.model),
                    response_id=data.get("id", ""),
                    created=int(time.time()),
                    think_content=thinking_content,
                    raw_response=data
                )
                
        except Exception as e:
            logger.error(f"[Anthropic] Chat error: {e}")
            return self._build_error_response(e)
    
    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        发送流式聊天请求

        Anthropic 的流式响应使用 server-sent events 格式
        """
        self.validate_vision_capability(messages)
        session = await self._get_session()
        
        try:
            # 构建请求体
            converted = self._convert_messages(messages)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            body = {
                "model": self.config.model,
                "messages": converted["messages"],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }
            
            if converted["system"]:
                body["system"] = converted["system"]
            
            # 添加 thinking 扩展
            if self.config.thinking_enabled:
                body["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                }
            
            # 发送流式请求
            async with session.post(
                f"{self.API_BASE}/messages",
                headers=self._build_headers(),
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Anthropic] Stream error: {response.status} - {error_text}")
                    yield StreamChunk(content="", error=f"API error {response.status}")
                    return
                
                # 解析 SSE 流
                in_think = False
                think_start_time = None
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
                            event_type = data.get("type", "")
                            
                            if event_type == "message_start":
                                yield StreamChunk(
                                    content="",
                                    is_first=True,
                                    timestamp=time.perf_counter()
                                )
                            
                            elif event_type == "content_block_start":
                                block_type = data.get("content_block", {}).get("type", "")
                                if block_type == "thinking":
                                    in_think = True
                                    if think_start_time is None:
                                        think_start_time = time.perf_counter()
                                else:
                                    in_think = False
                            
                            elif event_type == "content_block_delta":
                                delta_type = data.get("delta", {}).get("type", "")
                                delta_content = data.get("delta", {}).get("text", "") or data.get("delta", {}).get("thinking", "")
                                
                                if delta_content:
                                    chunk = StreamChunk(
                                        content=delta_content,
                                        is_first=False,
                                        timestamp=time.perf_counter(),
                                        is_think=in_think,
                                        is_think_end=False
                                    )
                                    yield chunk
                            
                            elif event_type == "content_block_stop":
                                if in_think:
                                    in_think = False
                                    yield StreamChunk(
                                        content="",
                                        is_first=False,
                                        timestamp=time.perf_counter(),
                                        is_think=False,
                                        is_think_end=True
                                    )
                            
                            elif event_type == "message_delta":
                                usage = data.get("usage", {})
                                yield StreamChunk(
                                    content="",
                                    is_first=False,
                                    timestamp=time.perf_counter(),
                                    usage={
                                        "input_tokens": usage.get("input_tokens", 0),
                                        "output_tokens": usage.get("output_tokens", 0)
                                    }
                                )
                        
                        except json.JSONDecodeError:
                            continue
                
        except Exception as e:
            logger.error(f"[Anthropic] Stream error: {e}")
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