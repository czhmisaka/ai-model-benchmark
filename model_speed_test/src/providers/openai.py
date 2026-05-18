"""
OpenAI 兼容 Provider 实现
支持 OpenAI、MiniMax、硅基流动等 OpenAI 兼容格式的 API
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
import aiohttp

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI 兼容 Provider

    支持以下 API：
    - OpenAI (api.openai.com)
    - MiniMax (coding.dashscope.aliyuncs.com)
    - 硅基流动 (siliconflow.cn)
    - 其他 OpenAI 兼容 API
    """

    provider_name = "openai"
    provider_display_name = "OpenAI 兼容"
    supports_streaming = True
    supports_thinking = False  # OpenAI 原生不支持，但兼容模式下可能支持

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None

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
            "Accept": "application/json"
        }

        # 添加 API Key
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        return headers

    def _build_payload(
        self,
        messages: List[Message],
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """构建请求载荷"""
        payload = {
            "model": self.config.model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": stream,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        # 添加可选参数
        if self.config.presence_penalty != 0:
            payload["presence_penalty"] = self.config.presence_penalty

        if self.config.frequency_penalty != 0:
            payload["frequency_penalty"] = self.config.frequency_penalty

        # 添加 thinking 参数（对于支持思考模式的模型）
        if self.config.thinking_enabled:
            payload["thinking"] = {"type": "enabled"}
            # 某些 API 可能需要不同的格式
            # 例如 MiniMax 可能需要 thoughtfulness 或其他参数

        # 合并 extra_params
        if self.config.extra_params:
            for key, value in self.config.extra_params.items():
                if key not in payload:
                    payload[key] = value

        return payload

    async def chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """发送聊天请求（非流式）"""
        session = await self._get_session()
        payload = self._build_payload(messages, stream=False, **kwargs)
        headers = self._build_headers()

        try:
            async with session.post(
                self.config.endpoint,
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return LLMResponse(
                        error=f"HTTP {response.status}: {error_text}",
                        raw_response={"status": response.status, "text": error_text}
                    )

                data = await response.json()
                
                # 解析响应
                choices = data.get("choices", [])
                if not choices:
                    return LLMResponse(error="No choices in response", raw_response=data)

                choice = choices[0]
                message = choice.get("message", {})

                # 获取 usage 信息
                usage = data.get("usage", {})

                return LLMResponse(
                    content=message.get("content", ""),
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason", ""),
                    model=data.get("model", self.config.model),
                    response_id=data.get("id", ""),
                    created=data.get("created", 0),
                    raw_response=data
                )
        except Exception as e:
            return LLMResponse(error=f"Parse error: {str(e)}", raw_response={})

    async def stream_chat(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """发送流式聊天请求"""
        session = await self._get_session()
        payload = self._build_payload(messages, stream=True, **kwargs)
        headers = self._build_headers()

        try:
            async with session.post(
                self.config.endpoint,
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    yield StreamChunk(content="", error=f"HTTP {response.status}: {error_text}")
                    return

                # 处理流式响应
                first_chunk = True
                in_think = False

                async for line in response.content:
                    line = line.decode("utf-8").strip()

                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # 去掉 "data: " 前缀

                    if data_str == "[DONE]":
                        break

                    chunk = self._parse_stream_chunk(data_str, first_chunk, in_think)
                    if chunk:
                        # 更新 think 状态
                        if chunk.is_think:
                            in_think = True
                        if chunk.is_think_end:
                            in_think = False

                        yield chunk
                        first_chunk = False

        except aiohttp.ClientError as e:
            yield StreamChunk(content="", error=f"Connection error: {str(e)}")
        except Exception as e:
            yield StreamChunk(content="", error=f"Stream error: {str(e)}")

    def _parse_stream_chunk(
        self,
        data_str: str,
        first_chunk: bool,
        in_think: bool
    ) -> Optional[StreamChunk]:
        """解析流式数据块"""
        try:
            data = json.loads(data_str)
            
            # OpenAI 格式
            if "choices" in data:
                choices = data.get("choices", [])
                if not choices:
                    return None
                
                delta = choices[0].get("delta", {})
                
                # 提取 content
                content = delta.get("content") or ""
                
                # 兼容多种字段名：reasoning_content（标准）或 reasoning（移动云）
                reasoning_content = delta.get("reasoning_content") or delta.get("reasoning") or ""
                
                # DSv4 等模型的首个 chunk 仅含 role 初始化（无 content/reasoning）
                # 必须跳过，否则 first_chunk 被空 chunk 消耗，导致真正首 Token 的 is_first=False
                has_content = bool(content) or bool(reasoning_content)
                finish_reason = choices[0].get("finish_reason") or ""
                has_usage = bool(data.get("usage"))
                
                if not has_content and not finish_reason and not has_usage:
                    # 纯 role 初始化块，静默跳过（不消耗 first_chunk 标志）
                    return None
                
                # 判断是否为 think 内容
                is_first = first_chunk and has_content
                is_think = bool(reasoning_content)
                is_think_end = False
                
                # 检测 think 标签（某些模型使用标签）
                if not in_think:
                    if '<begin_of_thought>' in content:
                        is_think = True
                    if '<end_of_thought>' in content:
                        is_think_end = True
                    # 也支持 <think> 标签
                    if '<begin_of_think>' in content:
                        is_think = True
                    if '<end_of_think>' in content:
                        is_think_end = True
                
                # 判断是否为最终块（纯 finish_reason 块，无内容/推理）
                is_final = bool(finish_reason) and not has_content
                
                # 返回内容（content 只包含 answer，reasoning_content 单独传递）
                return StreamChunk(
                    content=content,  # 只包含 answer
                    is_first=is_first,
                    timestamp=time.perf_counter(),
                    is_think=is_think,  # 有 reasoning_content 就是 think
                    is_think_end=is_think_end,
                    reasoning_content=reasoning_content if reasoning_content else None,
                    usage=data.get("usage", {}),
                    finish_reason=finish_reason,
                    is_final=is_final
                )
            
            return None
            
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.error(f"[OpenAI] Parse error: {e}")
            return None

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