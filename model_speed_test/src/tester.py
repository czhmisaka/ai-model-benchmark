"""
核心测试逻辑模块
负责执行模型测试、收集指标、协调各组件
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .client import ModelClient, StreamChunk
from .metrics import TestMetrics, MetricsCalculator, estimate_input_tokens
from .recorder import IORecorder
from .rate_limiter import RateLimiter, ProgressTracker, ConcurrencyConfig
from .providers.base import extract_text_for_log, has_image_parts, normalize_content


@dataclass
class TestResult:
    """单次测试结果"""
    success: bool
    model_name: str
    metrics: Optional[TestMetrics]
    error: Optional[str] = None
    response_content: str = ""
    prompt: str = ""


def _collect_input_images(messages) -> List[Dict[str, Any]]:
    """从 messages 中抽取所有图片 part（用于 recorder 记录输入溯源）"""
    out: List[Dict[str, Any]] = []
    if not messages:
        return out
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url" and part.get("image_url"):
                out.append({"type": "image_url", "image_url": part["image_url"]})
    return out


class ModelTester:
    """模型测试器"""
    
    def __init__(
        self,
        client: ModelClient,
        recorder: IORecorder,
        test_config: Dict[str, Any],
        timeout: float = 300.0
    ):
        self.client = client
        self.recorder = recorder
        self.test_config = test_config
        self.timeout = timeout  # 超时时间（秒），默认300秒
    
    async def test_single_request(
        self,
        prompt: str = None,
        round_num: int = 1,
        messages: list = None,
        system_prompt: str = None,
        timeout: float = None
    ) -> TestResult:
        """
        执行单次测试请求
        
        Args:
            prompt: 测试用提示词
            round_num: 测试轮次
            messages: 消息数组（优先于prompt）
            system_prompt: 系统提示词
            timeout: 超时时间（秒），默认使用 self.timeout
            
        Returns:
            TestResult对象
        """
        # max_tokens 固定为 -1（不限制），测试 case 不可调整
        max_tokens = -1
        temperature = self.test_config.get("temperature", 0.7)
        stream = self.test_config.get("stream", True)

        # 确定使用的prompt（用于记录）。content 可能是 list（多模态），需抽取文本部分
        if prompt:
            display_prompt = prompt
        elif messages:
            last = messages[-1]
            last_content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
            display_prompt = extract_text_for_log(last_content)
        else:
            display_prompt = ""
        
        # 使用传入的超时参数或默认超时
        timeout = timeout or self.timeout
        
        try:
            if stream:
                return await asyncio.wait_for(
                    self._test_stream(
                        prompt, max_tokens, temperature, 
                        messages=messages, system_prompt=system_prompt
                    ),
                    timeout=timeout
                )
            else:
                return await asyncio.wait_for(
                    self._test_nonstream(
                        prompt, max_tokens, temperature,
                        messages=messages, system_prompt=system_prompt
                    ),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error=f"Request timeout ({timeout}s)",
                prompt=display_prompt
            )
        except Exception as e:
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error=str(e),
                prompt=display_prompt
            )
    
    async def _test_stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        messages: list = None,
        system_prompt: str = None
    ) -> TestResult:
        """执行流式测试"""
        start_time = time.perf_counter()
        chunks = []
        full_content = ""

        # 确定显示用的prompt
        if prompt:
            display_prompt = prompt
        elif messages:
            last = messages[-1]
            last_content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
            display_prompt = extract_text_for_log(last_content)
        else:
            display_prompt = ""
        
        # 输出详细信息标题
        print(f"\n{'='*60}")
        print(f"【流式测试】模型: {self.client.name}")
        print(f"{'='*60}")
        
        # 输出 Input
        print(f"\n📥 【INPUT 输入】:")
        print(f"-" * 40)
        if messages:
            # 如果有消息数组，显示完整对话
            for i, msg in enumerate(messages):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                print(f"[{role}]: {content[:200]}{'...' if len(content) > 200 else ''}")
            if system_prompt:
                print(f"[system]: {system_prompt[:200]}{'...' if len(system_prompt) > 200 else ''}")
        else:
            print(f"{display_prompt[:500]}{'...' if len(display_prompt) > 500 else ''}")
        print(f"-" * 40)
        
        print(f"\n🔄 正在等待响应...")
        
        # 分别追踪 think 和 answer 内容
        think_content = ""
        answer_content = ""
        is_in_think = False
        
        try:
            async for chunk in self.client.chat_stream(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=getattr(self.client, 'temperature', temperature),
                messages=messages,
                system_prompt=system_prompt
            ):
                # 检查 chunk 中的错误
                chunk_error = getattr(chunk, 'error', None)
                if chunk_error:
                    print(f"\n❌ 【流式错误】: {chunk_error}")
                    return TestResult(
                        success=False,
                        model_name=self.client.name,
                        metrics=None,
                        error=str(chunk_error),
                        prompt=display_prompt
                    )
                
                # 构建 chunk 内容（包含 reasoning_content 和 content）
                chunk_content = chunk.content
                chunk_reasoning = getattr(chunk, 'reasoning_content', None)
                # 透传 API 返回的 usage（通常是最后一个 chunk 携带精确 token 统计）
                chunk_usage = getattr(chunk, 'usage', None)
                
                # 如果有 reasoning_content，也加入 chunks 用于 metrics 计算
                if chunk_reasoning:
                    base_entry = {
                        "content": chunk_reasoning,
                        "is_first": chunk.is_first and not chunk_reasoning,
                        "timestamp": chunk.timestamp,
                        "is_think": True,
                        "is_think_end": False,
                        "reasoning_content": chunk_reasoning
                    }
                    if chunk_usage is not None:
                        base_entry["usage"] = chunk_usage
                    chunks.append(base_entry)
                    # answer 部分作为单独的 chunk
                    if chunk_content:
                        answer_entry = {
                            "content": chunk_content,
                            "is_first": False,
                            "timestamp": chunk.timestamp + 0.001,  # 稍微延后
                            "is_think": False,
                            "is_think_end": chunk.is_think_end
                        }
                        if chunk_usage is not None:
                            answer_entry["usage"] = chunk_usage
                        chunks.append(answer_entry)
                else:
                    entry = {
                        "content": chunk.content,
                        "is_first": chunk.is_first,
                        "timestamp": chunk.timestamp,
                        "is_think": chunk.is_think,
                        "is_think_end": chunk.is_think_end
                    }
                    if chunk_usage is not None:
                        entry["usage"] = chunk_usage
                    chunks.append(entry)
                
                # 分别记录 think 和 answer 内容
                # 优先使用 reasoning_content 判断
                chunk_reasoning = getattr(chunk, 'reasoning_content', None)
                if chunk_reasoning:
                    # 有 reasoning_content 就是 think 内容
                    think_content += chunk_reasoning
                    is_in_think = True
                elif chunk.is_think:
                    think_content += chunk.content
                    is_in_think = True
                else:
                    # 当 think 结束，开始记录 answer
                    if is_in_think:
                        is_in_think = False
                    answer_content += chunk.content
                
                # full_content 包含所有内容
                if chunk_reasoning:
                    full_content += chunk_reasoning
                else:
                    full_content += chunk.content
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) or "Unknown error"
            # 记录完整错误信息用于调试
            import traceback
            error_details = traceback.format_exc()
            print(f"\n❌ 【测试失败】: Stream error ({error_type}): {error_msg}")
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error=f"Stream error ({error_type}): {error_msg}",
                prompt=display_prompt
            )
        
        # 估算 input_tokens（流式响应不返回 usage 信息）
        input_tokens = 0
        if messages or system_prompt:
            input_tokens = estimate_input_tokens(messages or [], system_prompt)
        
        # 检查模型是否返回了有效输出
        if not full_content:
            print(f"\n❌ 【测试失败】: 模型返回空输出（output_tokens: 0）")
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error="模型返回空输出（output_tokens: 0）",
                prompt=display_prompt
            )
        
        # 计算指标
        metrics = MetricsCalculator.calculate_stream_metrics(
            start_time=start_time,
            chunks=chunks,
            input_tokens=input_tokens
        )

        # 收集输入中的图片 part（用于多模态用例溯源）
        input_images = _collect_input_images(messages)

        # 记录结果（包含分离的 think 和 answer 内容）
        # 修复：添加 success 字段到 metadata，确保空输出被正确标记为失败
        await self.recorder.record(
            model_name=self.client.name,
            prompt=display_prompt,
            response=full_content,
            metrics=metrics.to_dict(),
            metadata={
                "test_type": "stream",
                "messages_count": len(messages) if messages else 0,
                "success": True  # 流式测试成功（走到这里说明 output_tokens > 0）
            },
            think_content=think_content if think_content else None,
            answer_content=answer_content if answer_content else None,
            input_images=input_images,
        )
        
        # 输出 Output
        print(f"\n📤 【OUTPUT 输出】:")
        print(f"-" * 40)
        # 截断显示，过长时显示部分
        output_display = full_content[:1000] if len(full_content) > 1000 else full_content
        print(output_display)
        if len(full_content) > 1000:
            print(f"... [输出过长，已截断，总长度: {len(full_content)} 字符]")
        print(f"-" * 40)
        
        # 输出性能指标
        print(f"\n📊 【性能指标】:")
        print(f"  - 输入Token数: {metrics.input_tokens}")
        print(f"  - 输出Token数: {metrics.output_tokens}")
        print(f"  - 首Token时间(TTFT): {metrics.ttft:.3f}s")
        print(f"  - 生成时间(TPFT): {metrics.tpft:.3f}s")
        print(f"  - 总耗时: {metrics.total_time:.3f}s")
        print(f"  - 输出速度: {metrics.tokens_per_second:.2f} tokens/s")
        if metrics.think_time > 0:
            print(f"  - Think时间: {metrics.think_time:.3f}s")
            print(f"  - Think Tokens: {metrics.think_tokens}")
        if metrics.answer_time > 0:
            print(f"  - Answer时间: {metrics.answer_time:.3f}s")
            print(f"  - Answer Tokens: {metrics.answer_tokens}")
        print(f"\n✅ 【测试成功】")
        
        return TestResult(
            success=True,
            model_name=self.client.name,
            metrics=metrics,
            response_content=full_content,
            prompt=display_prompt
        )
    
    async def _test_nonstream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        messages: list = None,
        system_prompt: str = None
    ) -> TestResult:
        """执行非流式测试"""
        start_time = time.perf_counter()

        # 确定显示用的prompt
        if prompt:
            display_prompt = prompt
        elif messages:
            last = messages[-1]
            last_content = last.get("content", "") if isinstance(last, dict) else getattr(last, "content", "")
            display_prompt = extract_text_for_log(last_content)
        else:
            display_prompt = ""
        
        # 输出详细信息标题
        print(f"\n{'='*60}")
        print(f"【非流式测试】模型: {self.client.name}")
        print(f"{'='*60}")
        
        # 输出 Input
        print(f"\n📥 【INPUT 输入】:")
        print(f"-" * 40)
        if messages:
            # 如果有消息数组，显示完整对话
            for i, msg in enumerate(messages):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                print(f"[{role}]: {content[:200]}{'...' if len(content) > 200 else ''}")
            if system_prompt:
                print(f"[system]: {system_prompt[:200]}{'...' if len(system_prompt) > 200 else ''}")
        else:
            print(f"{display_prompt[:500]}{'...' if len(display_prompt) > 500 else ''}")
        print(f"-" * 40)
        
        print(f"\n🔄 正在等待响应...")
        
        try:
            result = await self.client.chat(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
                messages=messages,
                system_prompt=system_prompt
            )
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) or "Unknown error"
            print(f"\n❌ 【测试失败】: Non-stream error ({error_type}): {error_msg}")
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error=f"Non-stream error ({error_type}): {error_msg}",
                prompt=display_prompt
            )
        
        end_time = time.perf_counter()
        
        # 检查模型是否返回了有效输出
        content = result.get("content", "")
        output_tokens = result.get("output_tokens", 0)
        
        if not content or output_tokens == 0:
            print(f"\n❌ 【测试失败】: 模型返回空输出（output_tokens: 0）")
            return TestResult(
                success=False,
                model_name=self.client.name,
                metrics=None,
                error="模型返回空输出（output_tokens: 0）",
                prompt=display_prompt
            )
        
        # 计算指标
        metrics = MetricsCalculator.calculate_nonstream_metrics(
            start_time=start_time,
            end_time=end_time,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=output_tokens
        )
        
        # 记录结果
        # 修复：添加 success 字段到 metadata，确保空输出被正确标记为失败
        input_images = _collect_input_images(messages)
        await self.recorder.record(
            model_name=self.client.name,
            prompt=display_prompt,
            response=content,
            metrics=metrics.to_dict(),
            metadata={
                "test_type": "non-stream",
                "messages_count": len(messages) if messages else 0,
                "success": True  # 非流式测试成功（走到这里说明 output_tokens > 0）
            },
            input_images=input_images,
        )
        
        # 输出 Output
        print(f"\n📤 【OUTPUT 输出】:")
        print(f"-" * 40)
        # 截断显示，过长时显示部分
        output_display = content[:1000] if len(content) > 1000 else content
        print(output_display)
        if len(content) > 1000:
            print(f"... [输出过长，已截断，总长度: {len(content)} 字符]")
        print(f"-" * 40)
        
        # 输出性能指标
        print(f"\n📊 【性能指标】:")
        print(f"  - 输入Token数: {metrics.input_tokens}")
        print(f"  - 输出Token数: {metrics.output_tokens}")
        print(f"  - 总耗时: {metrics.total_time:.3f}s")
        print(f"  - 输出速度: {metrics.tokens_per_second:.2f} tokens/s")
        print(f"\n✅ 【测试成功】")
        
        return TestResult(
            success=True,
            model_name=self.client.name,
            metrics=metrics,
            response_content=content,
            prompt=display_prompt
        )
    
    async def run_test_rounds(
        self,
        prompt: str = None,
        rounds: int = 3,
        interval: float = 1.0,
        messages: list = None,
        system_prompt: str = None
    ) -> List[TestResult]:
        """
        执行多轮测试
        
        Args:
            prompt: 测试用提示词
            rounds: 测试轮次
            interval: 每轮间隔（秒）
            messages: 消息数组（优先于prompt）
            system_prompt: 系统提示词
            
        Returns:
            测试结果列表
        """
        results = []
        
        for i in range(rounds):
            print(f"[{self.client.name}] 第 {i+1}/{rounds} 轮测试...")
            
            result = await self.test_single_request(
                prompt=prompt, 
                round_num=i+1,
                messages=messages,
                system_prompt=system_prompt
            )
            results.append(result)
            
            if result.success:
                metrics = result.metrics
                # 计算输出速度
                output_speed = metrics.tokens_per_second if metrics.tpft > 0 else 0
                print(f"  首Token时间(TTFT): {metrics.ttft:.3f}s, "
                      f"生成时间(TPFT): {metrics.tpft:.3f}s, "
                      f"总耗时: {metrics.total_time:.3f}s, "
                      f"输出Token数: {metrics.output_tokens}, "
                      f"输出速度: {output_speed:.2f} tokens/s")
            else:
                print(f"  错误: {result.error}")
            
            # 间隔
            if i < rounds - 1 and interval > 0:
                await asyncio.sleep(interval)
        
        return results


class ConcurrentTester:
    """并发测试器 - 支持多模型+多轮并发"""
    
    def __init__(
        self,
        clients: List[ModelClient],
        recorder: IORecorder,
        test_config: Dict[str, Any]
    ):
        self.clients = clients
        self.recorder = recorder
        self.test_config = test_config
    
    async def run_concurrent_test(
        self,
        prompt: str,
        concurrency: int = 5,
        rounds: int = 10,
        interval: float = 1.0,
        messages: list = None,
        system_prompt: str = None
    ) -> Dict[str, List[TestResult]]:
        """
        执行增强的并发测试 - 多模型+多轮并发
        
        Args:
            prompt: 测试用提示词
            concurrency: 每轮并发数量（同时发送的请求数）
            rounds: 测试总轮次
            interval: 每轮间隔时间（秒）
            messages: 消息数组
            system_prompt: 系统提示词
            
        Returns:
            按模型分组的测试结果
        """
        print(f"\n{'='*60}")
        print(f"并发测试配置:")
        print(f"  模型数量: {len(self.clients)}")
        print(f"  并发数: {concurrency}")
        print(f"  测试轮次: {rounds}")
        print(f"  每轮间隔: {interval}s")
        print(f"{'='*60}\n")
        
        # 为每个客户端创建独立的测试器
        testers = {client.name: ModelTester(client, self.recorder, self.test_config) for client in self.clients}
        
        all_results = {client.name: [] for client in self.clients}
        
        for round_num in range(rounds):
            print(f"[并发测试] 第 {round_num + 1}/{rounds} 轮...")
            
            # 为本轮创建并发任务
            tasks = []
            task_clients = []
            
            # 选择参与本轮的模型（循环使用）
            for i in range(concurrency):
                client = self.clients[i % len(self.clients)]
                tester = testers[client.name]
                task_clients.append(client)
                
                # 创建测试任务
                task = tester.test_single_request(
                    prompt=prompt,
                    round_num=round_num + 1,
                    messages=messages,
                    system_prompt=system_prompt
                )
                tasks.append(task)
            
            # 并发执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for i, result in enumerate(results):
                model_name = task_clients[i].name
                
                if isinstance(result, Exception):
                    all_results[model_name].append(TestResult(
                        success=False,
                        model_name=model_name,
                        metrics=None,
                        error=str(result),
                        prompt=prompt
                    ))
                    print(f"  [{model_name}] 失败: {str(result)}")
                else:
                    all_results[model_name].append(result)
                    if result.success:
                        speed = result.metrics.tokens_per_second if result.metrics.tpft > 0 else 0
                        print(f"  [{model_name}] 成功 - TTFT: {result.metrics.ttft:.3f}s, "
                              f"速度: {speed:.2f} tokens/s")
                    else:
                        print(f"  [{model_name}] 失败: {result.error}")
            
            # 轮次间隔
            if round_num < rounds - 1 and interval > 0:
                print(f"  等待 {interval}s...\n")
                await asyncio.sleep(interval)
        
        return all_results
    
    async def run_parallel_rounds(
        self,
        prompt: str,
        rounds: int = 10,
        messages: list = None,
        system_prompt: str = None
    ) -> Dict[str, List[TestResult]]:
        """
        并行执行多轮测试 - 每一轮所有模型同时测试
        
        Args:
            prompt: 测试用提示词
            rounds: 测试轮次
            messages: 消息数组
            system_prompt: 系统提示词
            
        Returns:
            按模型分组的测试结果
        """
        print(f"\n{'='*60}")
        print(f"并行多轮测试:")
        print(f"  模型数量: {len(self.clients)}")
        print(f"  测试轮次: {rounds}")
        print(f"{'='*60}\n")
        
        # 为每个客户端创建独立的测试器
        testers = {client.name: ModelTester(client, self.recorder, self.test_config) for client in self.clients}
        
        all_results = {client.name: [] for client in self.clients}
        
        for round_num in range(rounds):
            print(f"[并行测试] 第 {round_num + 1}/{rounds} 轮 - 同时测试 {len(self.clients)} 个模型...")
            
            # 本轮：所有模型同时测试
            tasks = []
            for client in self.clients:
                tester = testers[client.name]
                task = tester.test_single_request(
                    prompt=prompt,
                    round_num=round_num + 1,
                    messages=messages,
                    system_prompt=system_prompt
                )
                tasks.append(task)
            
            # 并发执行
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for i, result in enumerate(results):
                model_name = self.clients[i].name
                
                if isinstance(result, Exception):
                    all_results[model_name].append(TestResult(
                        success=False,
                        model_name=model_name,
                        metrics=None,
                        error=str(result),
                        prompt=prompt
                    ))
                    print(f"  [{model_name}] ✗ 失败")
                else:
                    all_results[model_name].append(result)
                    if result.success:
                        speed = result.metrics.tokens_per_second if result.metrics.tpft > 0 else 0
                        print(f"  [{model_name}] ✓ TTFT: {result.metrics.ttft:.3f}s, "
                              f"速度: {speed:.2f} tokens/s")
                    else:
                        print(f"  [{model_name}] ✗ 错误: {result.error}")
            
            # 每轮结束后显示汇总
            print()
            for model_name, results in all_results.items():
                success_count = sum(1 for r in results if r.success)
                print(f"  [{model_name}] 进度: {success_count}/{len(results)} 成功")
            print()
        
        return all_results
    
    async def run_enhanced_concurrent_test(
        self,
        prompt: str,
        concurrency: int = 10,
        rounds: int = 10,
        messages: list = None,
        system_prompt: str = None,
        concurrency_config: ConcurrencyConfig = None,
        progress_callback=None
    ) -> Dict[str, List[TestResult]]:
        """
        增强的并发测试 - 支持限流和进度跟踪
        
        Args:
            prompt: 测试用提示词
            concurrency: 并发数
            rounds: 测试轮次
            messages: 消息数组
            system_prompt: 系统提示词
            concurrency_config: 并发配置（可选）
            progress_callback: 进度回调函数
        
        Returns:
            按模型分组的测试结果
        """
        # 使用默认配置或自定义配置
        config = concurrency_config or ConcurrencyConfig(
            max_concurrent=concurrency,
            rate_limit=10.0,
            burst_size=concurrency
        )
        
        # 计算总请求数
        total_requests = concurrency * rounds
        
        print(f"\n{'='*60}")
        print(f"增强并发测试配置:")
        print(f"  模型数量: {len(self.clients)}")
        print(f"  并发数: {concurrency}")
        print(f"  测试轮次: {rounds}")
        print(f"  总请求数: {total_requests}")
        print(f"  速率限制: {config.rate_limit} req/s")
        print(f"  最大并发: {config.max_concurrent}")
        
        # 预估完成时间
        estimated_time = total_requests / config.rate_limit
        print(f"  预估完成时间: {estimated_time:.1f}秒")
        print(f"{'='*60}\n")
        
        # 创建速率限制器和进度跟踪器
        rate_limiter = RateLimiter(config)
        progress = ProgressTracker(total_requests)
        
        # 为每个客户端创建独立的测试器
        testers = {client.name: ModelTester(client, self.recorder, self.test_config) for client in self.clients}
        
        all_results = {client.name: [] for client in self.clients}
        
        async def run_single_request(client, client_name, round_num):
            """运行单个请求（带速率限制）"""
            async with rate_limiter:
                tester = testers[client_name]
                try:
                    result = await tester.test_single_request(
                        prompt=prompt,
                        round_num=round_num,
                        messages=messages,
                        system_prompt=system_prompt
                    )
                    await progress.increment(success=result.success)
                    return result
                except Exception as e:
                    await progress.increment(success=False)
                    return TestResult(
                        success=False,
                        model_name=client_name,
                        metrics=None,
                        error=str(e),
                        prompt=prompt
                    )
        
        # 执行所有请求
        request_id = 0
        for round_num in range(1, rounds + 1):
            print(f"[增强并发测试] 第 {round_num}/{rounds} 轮...")
            
            # 为本轮创建并发任务
            tasks = []
            for i in range(concurrency):
                client = self.clients[i % len(self.clients)]
                tasks.append(run_single_request(client, client.name, round_num))
                request_id += 1
            
            # 并发执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for i, result in enumerate(results):
                model_name = self.clients[i % len(self.clients)].name
                
                if isinstance(result, Exception):
                    all_results[model_name].append(TestResult(
                        success=False,
                        model_name=model_name,
                        metrics=None,
                        error=str(result),
                        prompt=prompt
                    ))
                else:
                    all_results[model_name].append(result)
            
            # 显示进度
            progress_info = progress.get_progress()
            print(f"  进度: {progress_info['completed']}/{progress_info['total']} "
                  f"({progress_info['progress_percent']}%) "
                  f"ETA: {progress_info['eta_seconds']:.0f}s")
            
            # 调用进度回调
            if progress_callback:
                progress_callback(round_num, rounds, progress_info)
        
        # 最终统计
        print(f"\n{'='*60}")
        print("增强并发测试完成")
        print(f"{'='*60}")
        
        progress_info = progress.get_progress()
        print(f"  总请求: {progress_info['total']}")
        print(f"  成功: {progress_info['success']}")
        print(f"  失败: {progress_info['failed']}")
        print(f"  总耗时: {progress_info['elapsed_seconds']:.1f}s")
        print(f"  平均速率: {progress_info['requests_per_second']:.2f} req/s")
        
        return all_results
