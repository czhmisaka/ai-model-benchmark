"""
统一API客户端
支持OpenAI格式的API调用，包括流式响应
支持请求重试机制
"""
import os
import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """流式响应块"""
    content: str
    is_first: bool
    timestamp: float
    is_think: bool = False  # 是否在 think 标签内
    is_think_end: bool = False  # 是否是 think 标签结束标记


class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def get_delay(self, attempt: int) -> float:
        """计算指数退避延迟"""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


class ModelClient:
    """统一模型客户端"""
    
    def __init__(
        self,
        name: str,
        endpoint: str,
        api_key: str,
        model: str,
        timeout: int = 120,
        retry_config: Optional[RetryConfig] = None
    ):
        self.name = name
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self.retry_config = retry_config or RetryConfig()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        # 始终创建新 session 以避免连接复用导致的 HTTP/2 问题
        # 禁用 SSL 证书验证（用于自签名证书或内部 CA）
        if self._session and not self._session.closed:
            await self._session.close()
        
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(ssl=False, force_close=True)
        )
        return self._session
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        发送带重试的HTTP请求
        
        Args:
            method: HTTP方法
            url: 请求URL
            **kwargs: 其他参数
            
        Returns:
            响应对象
            
        Raises:
            最后一次尝试的异常
        """
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                session = await self._get_session()
                
                # 不使用 async with，避免 continue 时提前关闭 response
                response = await session.request(method, url, **kwargs)
                try:
                    # 如果是服务器错误 (5xx) 或限流 (429)，重试
                    if response.status >= 500 or response.status == 429:
                        if attempt < self.retry_config.max_retries:
                            delay = self.retry_config.get_delay(attempt)
                            logger.warning(
                                f"[{self.name}] 请求失败 (状态码: {response.status}), "
                                f"{attempt + 1}/{self.retry_config.max_retries + 1} 次尝试, "
                                f"{delay:.1f}秒后重试..."
                            )
                            await asyncio.sleep(delay)
                            response.close()
                            continue
                    
                    response.raise_for_status()
                    return response
                except Exception:
                    response.close()
                    raise
                    
            except aiohttp.ClientError as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"[{self.name}] 网络错误: {e}, "
                        f"{attempt + 1}/{self.retry_config.max_retries + 1} 次尝试, "
                        f"{delay:.1f}秒后重试..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.name}] 请求失败，已达到最大重试次数")
            except asyncio.TimeoutError as e:
                last_exception = e
                if attempt < self.retry_config.max_retries:
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"[{self.name}] 请求超时, "
                        f"{attempt + 1}/{self.retry_config.max_retries + 1} 次尝试, "
                        f"{delay:.1f}秒后重试..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.name}] 请求超时，已达到最大重试次数")
        
        raise last_exception
    
    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # 处理API Key
        api_key = os.path.expandvars(self.api_key)
        
        # 调试：检查 API Key 展开结果
        if not api_key or api_key.startswith("${"):
            logger.warning(
                f"[{self.name}] API Key 未正确展开！"
                f"原始值: {self.api_key}, 展开后: {api_key}"
            )
        
        if api_key and api_key != "not-needed" and not api_key.startswith("${"):
            headers["Authorization"] = f"Bearer {api_key}"
        
        # 调试：打印部分请求头（不打印完整 API Key）
        if "Authorization" in headers:
            auth_key = headers["Authorization"]
            if len(auth_key) > 20:
                masked_key = auth_key[:15] + "..." + auth_key[-5:]
            else:
                masked_key = "***"
            logger.debug(f"[{self.name}] Authorization: Bearer {masked_key}")
        
        return headers
    
    def _is_local_lmstudio(self) -> bool:
        """检测是否是 LM Studio 本地 API"""
        # LM Studio 通常运行在 localhost 或 127.0.0.1
        return "localhost" in self.endpoint.lower() or "127.0.0.1" in self.endpoint.lower()
    
    def _is_input_format(self) -> bool:
        """检测是否使用 input 格式（某些本地模型如 qwen3-0.6b 使用此格式）"""
        # 检测 endpoint 是否为 /api/v1/chat 格式
        return "/api/v1/chat" in self.endpoint and "/v1/chat/completions" not in self.endpoint
    
    def _is_custom_sse_format(self) -> bool:
        """检测是否使用自定义 SSE 格式（如 qwen3-0.6b）"""
        return self._is_input_format()
    
    def _build_payload(
        self,
        prompt: str = None,
        messages: list = None,
        system_prompt: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = True
    ) -> dict:
        """构建请求载荷，兼容 LM Studio 和 OpenAI 格式"""
        
        # 检测是否使用 input 格式（某些本地模型如 qwen3-0.6b）
        if self._is_input_format():
            # 使用 input 格式（某些本地模型 API）
            user_content = ""
            if messages:
                # 从 messages 数组中提取最后一条 user 消息
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_content = msg.get("content", "")
                        break
            elif prompt:
                user_content = prompt
            
            payload = {
                "model": self.model,
                "input": user_content,
                "temperature": temperature,
                "stream": stream
            }
            
            if system_prompt:
                payload["system_prompt"] = system_prompt
            
            # 注意：某些本地模型 API（如 qwen3-0.6b）不支持 max_tokens 参数
            # 如果需要限制输出长度，可能需要在其他地方处理
            
            return payload
        
        # 标准 OpenAI/LM Studio 格式，使用 messages 数组
        msg_list = self._build_messages(prompt, messages, system_prompt)
        
        payload = {
            "model": self.model,
            "messages": msg_list,
            "temperature": temperature,
            "stream": stream
        }
        
        if max_tokens > 0:
            payload["max_tokens"] = max_tokens
        
        return payload
    
    def _build_messages(
        self,
        prompt: str = None,
        messages: list = None,
        system_prompt: str = None
    ) -> list:
        """构建消息数组"""
        if messages:
            # 使用传入的messages数组
            return messages
        elif prompt:
            # 使用简单的prompt
            if system_prompt:
                return [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            else:
                return [{"role": "user", "content": prompt}]
        else:
            # 默认空消息
            return [{"role": "user", "content": "你好"}]
    
    async def chat(
        self,
        prompt: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        stream: bool = True,
        messages: list = None,
        system_prompt: str = None
    ) -> Dict[str, Any]:
        """
        发送聊天请求（非流式）
        
        Args:
            prompt: 简单的prompt字符串
            max_tokens: 最大token数
            temperature: 温度参数
            stream: 是否流式
            messages: 消息数组，优先于prompt
            system_prompt: 系统提示词
        
        Returns:
            包含响应内容和元数据的字典
        """
        payload = self._build_payload(
            prompt=prompt,
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False
        )
        
        start_time = time.perf_counter()
        
        response = await self._request_with_retry(
            "POST",
            self.endpoint,
            headers=self._get_headers(),
            json=payload
        )
        
        result = await response.json()
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        
        # 提取内容 - 兼容不同 API 格式
        content = ""
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            # 优先使用 content，如果为空则使用 reasoning（Qwen3.5 等模型的思考过程）
            content = message.get("content", "")
            if not content:
                # Qwen3.5 等模型使用 reasoning 字段
                content = message.get("reasoning", "")
        elif "response" in result:
            # LM Studio 格式
            content = result.get("response", "")
        elif "output" in result and isinstance(result["output"], list):
            # 本地模型格式（如 qwen3-0.6b）
            for item in result["output"]:
                if item.get("type") == "message":
                    content = item.get("content", "")
                    break
        
        # 提取性能统计信息（如果有）
        stats = result.get("stats", {})
        
        # 提取token使用量 - 优先使用 stats 中的信息
        input_tokens = stats.get("input_tokens", result.get("usage", {}).get("prompt_tokens", 0))
        output_tokens = stats.get("total_output_tokens", result.get("usage", {}).get("completion_tokens", 0))
        
        # 提取 tokens per second（如果有）
        tokens_per_second = stats.get("tokens_per_second", 0)
        time_to_first_token = stats.get("time_to_first_token_seconds", 0)
        
        return {
            "content": content,
            "total_time": total_time,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_second": tokens_per_second,
            "time_to_first_token": time_to_first_token,
            "raw_response": result
        }
    
    async def chat_stream(
        self,
        prompt: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        messages: list = None,
        system_prompt: str = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        发送流式聊天请求
        
        Args:
            prompt: 简单的prompt字符串
            max_tokens: 最大token数
            temperature: 温度参数
            messages: 消息数组，优先于prompt
            system_prompt: 系统提示词
        
        Yields:
            StreamChunk对象
        """
        payload = self._build_payload(
            prompt=prompt,
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )
        
        # 流式请求不使用重试，直接发送请求
        session = await self._get_session()
        
        try:
            async with session.post(
                self.endpoint,
                headers=self._get_headers(),
                json=payload
            ) as response:
                response.raise_for_status()
                
                first_chunk_received = False
                
                # 检测是否使用自定义 SSE 格式
                if self._is_custom_sse_format():
                    # 处理自定义 SSE 格式（event: xxx\ndata: {...}）
                    buffer = ""
                    async for chunk_data in response.content.iter_chunked(1024):
                        try:
                            text = chunk_data.decode('utf-8')
                        except UnicodeDecodeError:
                            text = chunk_data.decode('utf-8', errors='replace')
                        
                        buffer += text
                        
                        # 按行分割处理
                        lines = buffer.split('\n')
                        buffer = lines[-1]  # 保留不完整的行
                        
                        for line in lines[:-1]:
                            line = line.strip()
                            if not line:
                                continue
                            
                            # 解析 event: xxx 和 data: {...}
                            if line.startswith('event:'):
                                # 事件类型行，忽略
                                continue
                            elif line.startswith('data:'):
                                data = line[5:].strip()
                                print(data)
                                if data == '[DONE]':
                                    break
                                try:
                                    chunk_json = json.loads(data)
                                    chunk_type = chunk_json.get("type", "")
                                    
                                    # 只提取最终消息内容，过滤掉推理内容
                                    content = ""
                                    if chunk_type == "message.delta":
                                        content = chunk_json.get("content", "")
                                    
                                    if content:
                                        is_first = not first_chunk_received
                                        if is_first:
                                            first_chunk_received = True
                                        
                                        yield StreamChunk(
                                            content=content,
                                            is_first=is_first,
                                            timestamp=time.perf_counter()
                                        )
                                except json.JSONDecodeError:
                                    continue
                else:
                    # 标准 OpenAI SSE 格式
                    # 用于追踪 think 标签状态
                    in_think = False
                    think_end_detected = False

                    async for chunk_data in response.content.iter_chunked(1024):
                        # 解码 chunk，处理不完整的UTF-8序列
                        try:
                            text = chunk_data.decode('utf-8')
                        except UnicodeDecodeError:
                            text = chunk_data.decode('utf-8', errors='replace')

                        # 按行分割
                        lines = text.split('\n')

                        for line in lines:
                            line = line.strip()

                            if not line:
                                continue

                            # 处理 SSE 格式: data: {...}
                            if line.startswith('data:'):
                                data = line[5:].strip()
                                if data == '[DONE]':
                                    break

                                try:
                                    chunk_json = json.loads(data)
                                    # 兼容 OpenAI 和 MiniMax 格式
                                    choices = chunk_json.get("choices", [])
                                except json.JSONDecodeError:
                                    continue
                                
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    # 优先使用 content，如果为空则使用 reasoning（Qwen3.5 等模型的思考过程）
                                    content = delta.get("content", "")
                                    if not content:
                                        content = delta.get("reasoning", "")
                                    
                                    if content:
                                        is_first = not first_chunk_received
                                        if is_first:
                                            first_chunk_received = True
                                        
                                        # 检测 think 标签
                                        is_think = False
                                        is_think_end = False
                                        
                                        # 检测是否开始 think 标签
                                        if not in_think and not think_end_detected and '<think>' in content:
                                            in_think = True
                                            is_think = True
                                        
                                        # 检测是否结束 think 标签
                                        if in_think and '</think>' in content:
                                            in_think = False
                                            think_end_detected = True
                                            is_think_end = True
                                        
                                        yield StreamChunk(
                                            content=content,
                                            is_first=is_first,
                                            timestamp=time.perf_counter(),
                                            is_think=in_think or is_think,
                                            is_think_end=is_think_end
                                        )
                        # 也支持直接返回 JSON（某些 API 格式）
                        else:
                            try:
                                chunk_json = json.loads(line)
                                choices = chunk_json.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        is_first = not first_chunk_received
                                        if is_first:
                                            first_chunk_received = True
                                        
                                        # 检测 think 标签
                                        is_think = False
                                        is_think_end = False
                                        
                                        # 检测是否开始 think 标签
                                        if not in_think and not think_end_detected and '<think>' in content:
                                            in_think = True
                                            is_think = True
                                        
                                        # 检测是否结束 think 标签
                                        if in_think and '</think>' in content:
                                            in_think = False
                                            think_end_detected = True
                                            is_think_end = True
                                        
                                        yield StreamChunk(
                                            content=content,
                                            is_first=is_first,
                                            timestamp=time.perf_counter(),
                                            is_think=in_think or is_think,
                                            is_think_end=is_think_end
                                        )
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"[{self.name}] 流式请求错误: {e}")
            raise


async def test_client_connection():
    """测试客户端连接（调试用）"""
    client = ModelClient(
        name="test",
        endpoint="https://api.openai.com/v1/chat/completions",
        api_key="${OPENAI_API_KEY}",
        model="gpt-4o-mini"
    )
    
    try:
        result = await client.chat(
            prompt="你好",
            max_tokens=10,
            stream=False
        )
        print("连接测试成功:", result)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_client_connection())