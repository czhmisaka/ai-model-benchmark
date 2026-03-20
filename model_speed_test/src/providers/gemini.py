"""
Google Gemini Provider
支持 Gemini 系列模型的 API
"""

import json
import time
from typing import Dict, List, Any, Optional, AsyncIterator
import aiohttp
import logging

from .base import BaseLLMProvider, LLMResponse, StreamChunk, Message, ModelConfig

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API Provider
    支持 Gemini 1.5+ 系列模型
    """
    
    provider_name = "gemini"
    provider_display_name = "Google Gemini"
    supports_thinking = False  # Gemini 有自己的思考方式
    requires_api_key = True
    
    # Gemini API 配置
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Gemini 特定的参数
        self.safety_settings = config.extra_params.get("safety_settings", [])
        self.generation_config = config.extra_params.get("generation_config", {})
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _get_endpoint(self) -> str:
        """获取 API 端点"""
        return f"{self.API_BASE}/models/{self.config.model}:"
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Content-Type": "application/json"
        }
    
    def _convert_messages(self, messages: List[Message]) -> Dict[str, Any]:
        """
        转换消息格式
        
        Gemini 使用 contents 格式:
        - parts 包含文本内容
        - system 消息使用 system_instruction
        """
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == "system":
                if not system_instruction:
                    system_instruction = {"parts": [{"text": msg.content}]}
                else:
                    system_instruction["parts"][0]["text"] += "\n" + msg.content
            else:
                # Gemini 使用不同的 role 映射
                gemini_role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": msg.content}]
                })
        
        return {
            "contents": contents,
            "system_instruction": system_instruction
        }
    
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
            # 转换消息格式
            converted = self._convert_messages(messages)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            # 构建请求体
            body = {
                "contents": converted["contents"],
            }
            
            if converted["system_instruction"]:
                body["system_instruction"] = converted["system_instruction"]
            
            # 生成配置
            body["generationConfig"] = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": self.config.top_p,
                **self.generation_config
            }
            
            # 安全设置
            if self.safety_settings:
                body["safetySettings"] = self.safety_settings
            
            # API Key 作为查询参数
            params = {"key": self.config.api_key}
            
            # 发送请求
            url = f"{self._get_endpoint()}generateContent"
            async with session.post(
                url,
                headers=self._build_headers(),
                json=body,
                params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Gemini] API error: {response.status} - {error_text}")
                    return LLMResponse(
                        error=f"API error {response.status}: {error_text}"
                    )
                
                data = await response.json()
                
                # 解析响应
                return self._parse_response(data, start_time)
                
        except Exception as e:
            logger.error(f"[Gemini] Chat error: {e}")
            return self._build_error_response(e)
    
    def _parse_response(self, data: Dict[str, Any], start_time: float) -> LLMResponse:
        """解析 Gemini 响应"""
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                # 检查是否有安全反馈
                prompt_feedback = data.get("promptFeedback", {})
                if prompt_feedback:
                    safety_ratings = prompt_feedback.get("safetyRatings", [])
                    if safety_ratings:
                        return LLMResponse(
                            error=f"Content blocked by safety filters: {safety_ratings}"
                        )
                return LLMResponse(error="No response from model")
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            # 提取文本内容
            text = ""
            for part in parts:
                if "text" in part:
                    text += part["text"]
            
            # 获取 usage 信息（可能在 finishReason 中）
            usage_metadata = data.get("usageMetadata", {})
            
            return LLMResponse(
                content=text,
                input_tokens=usage_metadata.get("promptTokenCount", 0),
                output_tokens=usage_metadata.get("candidatesTokenCount", 0),
                total_tokens=usage_metadata.get("totalTokenCount", 0),
                finish_reason=candidate.get("finishReason", ""),
                model=self.config.model,
                raw_response=data
            )
            
        except Exception as e:
            return LLMResponse(error=f"Parse error: {e}")
    
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
            # 转换消息格式
            converted = self._convert_messages(messages)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            temperature = kwargs.get("temperature", self.config.temperature)
            
            # 构建请求体
            body = {
                "contents": converted["contents"],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "topP": self.config.top_p,
                    **self.generation_config
                },
                "safetySettings": self.safety_settings if self.safety_settings else None
            }
            
            if converted["system_instruction"]:
                body["system_instruction"] = converted["system_instruction"]
            
            # API Key 作为查询参数
            params = {"key": self.config.api_key}
            
            # 发送流式请求
            url = f"{self._get_endpoint()}streamGenerateContent"
            async with session.post(
                url,
                headers=self._build_headers(),
                json=body,
                params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Gemini] Stream error: {response.status} - {error_text}")
                    yield StreamChunk(content="", error=f"API error {response.status}")
                    return
                
                # 解析流式响应
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line:
                        continue
                    
                    # Gemini 流式响应也是 JSON lines 格式
                    try:
                        data = json.loads(line)
                        
                        # 解析 chunk
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield StreamChunk(
                                        content=part["text"],
                                        is_first=False,
                                        timestamp=time.perf_counter()
                                    )
                        
                        # 检查是否完成
                        if data.get("done", False):
                            break
                            
                    except json.JSONDecodeError:
                        continue
                
        except Exception as e:
            logger.error(f"[Gemini] Stream error: {e}")
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