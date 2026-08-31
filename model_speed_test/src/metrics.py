"""
性能指标计算模块
支持精确和估算两种Token统计方式
"""
import time
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# 尝试导入tiktoken用于精确Token统计
try:
    import tiktoken
    _tiktoken_available = True
except ImportError:
    _tiktoken_available = False

# 缓存 tiktoken 编码器
_token_encoder_cache = {}


def get_token_encoder(encoding_name: str = "cl100k_base"):
    """获取或创建 tiktoken 编码器（带缓存）"""
    if encoding_name in _token_encoder_cache:
        return _token_encoder_cache[encoding_name]
    
    if not _tiktoken_available:
        return None
    
    try:
        encoder = tiktoken.get_encoding(encoding_name)
        _token_encoder_cache[encoding_name] = encoder
        return encoder
    except Exception:
        return None


# 多模态图片固定 token 估算（OpenAI 低细节图像近似值）
_IMAGE_TOKENS_ESTIMATE = 85


def _count_single_text(text: str, encoding_name: str = "cl100k_base") -> int:
    """单个文本的 token 计数：tiktoken 优先，失败回退估算"""
    if not text:
        return 0
    
    encoder = get_token_encoder(encoding_name)
    if encoder:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    
    # 回退到估算方法
    return estimate_tokens(text)


def _count_multimodal_content(content: list, encoding_name: str = "cl100k_base") -> int:
    """统计多模态 content（part 列表）的 token 数
    
    支持 ContentPart 两种常见形态：
      - {"type": "text", "text": "..."}
      - {"type": "image_url", "image_url": {"url": "..."}}
    以及纯字符串 part。
    """
    total = 0
    for part in content:
        if isinstance(part, str):
            total += _count_single_text(part, encoding_name)
        elif isinstance(part, dict):
            part_type = part.get("type", "")
            if part_type == "text":
                total += _count_single_text(part.get("text", "") or "", encoding_name)
            elif part_type == "image_url":
                # 图片无法逐字符计数，按固定估算值
                total += _IMAGE_TOKENS_ESTIMATE
            else:
                # 未知 part 类型：兜底取 text 字段
                text_val = part.get("text", "")
                if text_val:
                    total += _count_single_text(text_val, encoding_name)
    return total


def count_tokens(text, encoding_name: str = "cl100k_base") -> int:
    """
    使用 tiktoken 精确计算 token 数
    
    Args:
        text: 待计算的文本；也支持多模态 part 列表（content 为 list 的场景）
        encoding_name: 编码名称，默认 cl100k_base (GPT-4/GPT-3.5 使用)
    
    Returns:
        token 数量
    """
    if not text:
        return 0
    
    # 多模态 content（part 列表）支持
    if isinstance(text, list):
        return _count_multimodal_content(text, encoding_name)
    
    return _count_single_text(text, encoding_name)


def estimate_input_tokens(messages: list, system_prompt: str = None) -> int:
    """
    估算输入 token 数（包括 messages 和 system_prompt）
    
    基于 OpenAI 的 token 计算方式:
    - 每条消息: ~4 tokens (role + content overhead)
    - 每条消息内容: 使用 tiktoken 或估算
    - system_prompt: +3 tokens
    - 请求结束: +3 tokens
    
    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}]
        system_prompt: 系统提示词
    
    Returns:
        估算的输入 token 数
    """
    total = 0
    
    # 计算每条消息的 token
    for msg in messages:
        # 消息 overhead: role + content
        total += 4
        content = msg.get("content", "")
        if content:
            total += count_tokens(content)
    
    # system_prompt
    if system_prompt:
        total += 3  # message overhead
        total += count_tokens(system_prompt)
    
    # completion overhead
    total += 3
    
    return total


def estimate_tokens(text) -> int:
    """
    估算文本的Token数量
    使用多种语言的中文/英文混合估算方法
    
    对于中文：约1.5个字符 = 1个token
    对于英文：约4个字符 = 1个token
    混合文本取平均值
    """
    if not text:
        return 0
    
    # 防御：若误传入多模态 part 列表，抽取文本/图片分别估算
    if isinstance(text, list):
        return _count_multimodal_content(text)
    
    # 非文本类型防御
    if not isinstance(text, str):
        text = str(text)
    
    # 计算中文字符数量
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    
    # 计算英文字符数量
    english_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    
    # 其他字符
    other_chars = len(text) - chinese_chars - english_chars
    
    # 估算
    chinese_tokens = chinese_chars / 1.5
    english_tokens = english_chars / 4.0
    other_tokens = other_chars / 3.0
    
    return int(chinese_tokens + english_tokens + other_tokens)


@dataclass
class TestMetrics:
    """单次测试的完整指标"""
    # 时间指标（秒）
    ttft: float = 0.0           # Time To First Token - 首Token时间
    tpft: float = 0.0           # Time Per First Token - 排除首Token后的生成时间
    total_time: float = 0.0     # 总响应时间
    
    # Think/Answer 时间指标（秒）
    think_time: float = 0.0      # Think 部分生成时间
    answer_time: float = 0.0     # Answer 部分生成时间（真正用户可见内容的生成时间）
    
    # Token指标
    input_tokens: int = 0       # 输入token数
    output_tokens: int = 0      # 输出token数
    
    # Think/Answer Token指标
    think_tokens: int = 0       # Think 部分 token 数
    answer_tokens: int = 0       # Answer 部分 token 数
    
    # 吞吐量计算
    @property
    def tokens_per_second(self) -> float:
        """每秒输出token数（包含think）"""
        # TPFT 太小时（< 0.01s），可能是异常数据，使用总时间计算
        if self.tpft > 0.01:
            return self.output_tokens / self.tpft
        elif self.total_time > 0.01:
            # 使用总时间计算，避免异常值
            return self.output_tokens / self.total_time
        return 0.0
    
    @property
    def total_tokens_per_second(self) -> float:
        """总时间每秒输出token数"""
        if self.total_time > 0:
            return self.output_tokens / self.total_time
        return 0.0
    
    @property
    def think_tokens_per_second(self) -> float:
        """Think 部分每秒生成 token 数"""
        if self.think_time > 0.01:
            return self.think_tokens / self.think_time
        return 0.0
    
    @property
    def answer_tokens_per_second(self) -> float:
        """Answer 部分每秒生成 token 数（真正的输出速度）"""
        if self.answer_time > 0.01:
            return self.answer_tokens / self.answer_time
        return 0.0
    
    # 原始数据
    timestamps: List[float] = field(default_factory=list)
    chunk_contents: List[str] = field(default_factory=list)
    
    # Token 计数来源（"api_usage"=API返回精确值 | "tiktoken_estimate"=本地重算）
    tokens_source: str = "tiktoken_estimate"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "ttft_seconds": round(self.ttft, 4),
            "tpft_seconds": round(self.tpft, 4),
            "total_time_seconds": round(self.total_time, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tokens_per_second": round(self.tokens_per_second, 2),
            "total_tokens_per_second": round(self.total_tokens_per_second, 2),
            # Think/Answer 统计
            "think_time_seconds": round(self.think_time, 4),
            "answer_time_seconds": round(self.answer_time, 4),
            "think_tokens": self.think_tokens,
            "answer_tokens": self.answer_tokens,
            "think_tokens_per_second": round(self.think_tokens_per_second, 2),
            "answer_tokens_per_second": round(self.answer_tokens_per_second, 2),
            # Token 计数来源
            "tokens_source": self.tokens_source,
        }


class MetricsCalculator:
    """指标计算器"""
    
    @staticmethod
    def calculate_stream_metrics(
        start_time: float,
        chunks: List[Dict[str, Any]],
        input_tokens: int = 0
    ) -> TestMetrics:
        """
        从流式响应计算指标
        
        Args:
            start_time: 请求开始时间
            chunks: 流式响应块列表
            input_tokens: 输入token数（可选）
            
        Returns:
            TestMetrics对象
        """
        metrics = TestMetrics()
        metrics.input_tokens = input_tokens
        
        if not chunks:
            return metrics
        
        # 收集时间戳和内容
        timestamps = []
        contents = []
        
        for chunk in chunks:
            timestamps.append(chunk["timestamp"])
            contents.append(chunk["content"])
        
        metrics.timestamps = timestamps
        metrics.chunk_contents = contents
        
        # 首Token时间 (TTFT)
        if timestamps:
            first_timestamp = timestamps[0]
            metrics.ttft = max(0, first_timestamp - start_time)
        
        # 总时间
        if timestamps:
            last_timestamp = timestamps[-1]
            metrics.total_time = max(0, last_timestamp - start_time)
        
        # TPFT = 总时间 - 首Token时间
        metrics.tpft = max(0, metrics.total_time - metrics.ttft)
        
        # ===== Think/Answer 统计 =====
        # 分析 chunks 中的 think 标签
        think_start_time = None
        think_end_time = None
        think_contents = []
        answer_contents = []
        
        in_think = False
        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "")
            timestamp = chunk.get("timestamp", 0)
            is_think = chunk.get("is_think", False)
            is_think_end = chunk.get("is_think_end", False)
            
            # 检测 think 开始 - 支持多种格式的 think 标签
            # 1. is_think 标志（适用于 LMStudio 等使用 reasoning_content 的模型）
            # 2. '<think>' 标签（适用于 OpenAI 格式）
            # 3. '<begin_of_thought>' 标签（适用于 MiniMax 等）
            has_think_start = (
                is_think or 
                '<think>' in content or 
                '<begin_of_thought>' in content or
                '<think>' in content.lower()
            )
            
            opened_this_chunk = False
            if not in_think and has_think_start:
                in_think = True
                if not think_start_time:
                    think_start_time = timestamp
                # 记录：本 chunk 刚打开 think，其自身不触发翻转
                opened_this_chunk = True
            
            # 检测 think→answer 转换：is_think 标记从 True 变为 False
            # 这处理了使用 reasoning_content 字段（无标签）的模型，
            # 如 DeepSeek V3/V4，它们的 think 内容通过单独的 reasoning_content 字段传递
            # 注意：跳过"刚打开 think 的同一 chunk"，否则标签型模型
            # （<think> 标签、is_think=False 的 chunk 同时携带开始标记）会在
            # 打开 think 的瞬间立即退出，导致 think 统计归零（回归）。
            if in_think and not opened_this_chunk and not is_think and not is_think_end:
                in_think = False
                think_end_time = timestamp
            
            if in_think:
                think_contents.append(content)
            else:
                answer_contents.append(content)
            
            # 检测 think 结束 - 支持多种格式
            # 1. is_think_end 标志
            # 2. '</think>' 标签
            # 3. '<end_of_thought>' 标签
            has_think_end = (
                is_think_end or 
                '</think>' in content or 
                '<end_of_thought>' in content or
                '</think>' in content.lower()
            )
            
            if in_think and has_think_end:
                in_think = False
                think_end_time = timestamp
        
        # 计算 Think 时间
        if think_start_time:
            if think_end_time:
                metrics.think_time = think_end_time - think_start_time
            else:
                # 如果没有明确的结束标记，使用最后一个 think chunk 的时间
                metrics.think_time = timestamps[-1] - think_start_time
        
        # 计算 Answer 时间 = 总时间 - Think 时间（如果检测到 think）
        if metrics.think_time > 0:
            metrics.answer_time = max(0, metrics.total_time - metrics.think_time)
        else:
            # 没有 think 部分，整个时间都是 answer
            metrics.answer_time = metrics.total_time
        
        # 计算 Think Tokens
        if think_contents:
            think_text = "".join(think_contents)
            # 移除各种格式的 think 标签，只计算实际内容
            think_text = think_text.replace('<think>', '').replace('</think>', '')
            think_text = think_text.replace('<begin_of_thought>', '').replace('<end_of_thought>', '')
            think_text = think_text.replace('<think>', '').replace('</think>', '')
            metrics.think_tokens = count_tokens(think_text)
        
        # 计算 Answer Tokens = 总输出 - Think Tokens
        # 优先使用 API 返回的准确值
        if chunks and "output_tokens" in chunks[-1] and chunks[-1].get("output_tokens"):
            total_output_tokens = chunks[-1].get("output_tokens", 0)
            metrics.tokens_source = "api_usage"
        elif chunks and "usage" in chunks[-1]:
            usage = chunks[-1].get("usage", {})
            total_output_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            if total_output_tokens:
                metrics.tokens_source = "api_usage"
            else:
                # usage 存在但无有效值 → 回退 tiktoken 重算
                full_content = "".join(contents)
                total_output_tokens = count_tokens(full_content)
                metrics.tokens_source = "tiktoken_estimate"
        else:
            # 回退：使用 tiktoken 精确计算
            full_content = "".join(contents)
            total_output_tokens = count_tokens(full_content)
            metrics.tokens_source = "tiktoken_estimate"
        
        metrics.output_tokens = total_output_tokens
        
        # Answer Tokens = 总输出 - Think Tokens（如果检测到 think）
        if metrics.think_tokens > 0:
            metrics.answer_tokens = max(0, total_output_tokens - metrics.think_tokens)
        else:
            # 没有 think 部分，所有都是 answer
            metrics.answer_tokens = total_output_tokens
        
        return metrics
        
        # Answer Tokens = 总输出 - Think Tokens（如果检测到 think）
        if metrics.think_tokens > 0:
            metrics.answer_tokens = max(0, total_output_tokens - metrics.think_tokens)
        else:
            # 没有 think 部分，所有都是 answer
            metrics.answer_tokens = total_output_tokens
        
        return metrics
    
    @staticmethod
    def calculate_nonstream_metrics(
        start_time: float,
        end_time: float,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> TestMetrics:
        """
        从非流式响应计算指标
        
        Args:
            start_time: 请求开始时间
            end_time: 响应结束时间
            input_tokens: 输入token数
            output_tokens: 输出token数
            
        Returns:
            TestMetrics对象
        """
        metrics = TestMetrics()
        
        total_time = end_time - start_time
        metrics.total_time = total_time
        metrics.ttft = total_time  # 非流式无法区分，设为总时间
        metrics.tpft = 0
        metrics.input_tokens = input_tokens
        metrics.output_tokens = output_tokens
        
        return metrics
    
    @staticmethod
    def aggregate_metrics(metrics_list: List[TestMetrics]) -> Dict[str, Any]:
        """
        聚合多次测试结果
        
        Args:
            metrics_list: 多次测试的指标列表
            
        Returns:
            聚合后的统计结果
        """
        if not metrics_list:
            return {}
        
        ttft_values = [m.ttft for m in metrics_list]
        tpft_values = [m.tpft for m in metrics_list]
        total_times = [m.total_time for m in metrics_list]
        tps_values = [m.tokens_per_second for m in metrics_list]
        output_tokens = [m.output_tokens for m in metrics_list]
        
        return {
            "count": len(metrics_list),
            "ttft": {
                "avg": round(sum(ttft_values) / len(ttft_values), 4),
                "min": round(min(ttft_values), 4),
                "max": round(max(ttft_values), 4),
            },
            "tpft": {
                "avg": round(sum(tpft_values) / len(tpft_values), 4),
                "min": round(min(tpft_values), 4),
                "max": round(max(tpft_values), 4),
            },
            "total_time": {
                "avg": round(sum(total_times) / len(total_times), 4),
                "min": round(min(total_times), 4),
                "max": round(max(total_times), 4),
            },
            "tokens_per_second": {
                "avg": round(sum(tps_values) / len(tps_values), 2),
                "min": round(min(tps_values), 2),
                "max": round(max(tps_values), 2),
            },
            "output_tokens": {
                "avg": round(sum(output_tokens) / len(output_tokens), 2),
                "min": min(output_tokens),
                "max": max(output_tokens),
            }
        }

    @staticmethod
    def aggregate_metrics_advanced(metrics_list: List[TestMetrics], exclude_outliers: bool = True) -> Dict[str, Any]:
        """
        增强的聚合统计 - 包含百分位、标准差、异常值检测
        
        Args:
            metrics_list: 多次测试的指标列表
            exclude_outliers: 是否排除异常值
        
        Returns:
            聚合后的详细统计结果
        """
        if not metrics_list:
            return {}
        
        # 提取各项指标
        ttft_values = [m.ttft for m in metrics_list]
        tpft_values = [m.tpft for m in metrics_list]
        total_times = [m.total_time for m in metrics_list]
        tps_values = [m.tokens_per_second for m in metrics_list]
        output_tokens = [m.output_tokens for m in metrics_list]
        
        # 基础统计函数
        def calc_basic(values: list) -> dict:
            return {
                "avg": round(sum(values) / len(values), 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
            }
        
        # 百分位统计
        def calc_percentiles(values: list) -> dict:
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            def percentile(p: float) -> float:
                if n == 0:
                    return 0
                k = (n - 1) * p / 100
                f = int(k)
                c = f + 1
                if c >= n:
                    return sorted_values[f]
                d0 = sorted_values[f] * (c - k)
                d1 = sorted_values[c] * (k - f)
                return round(d0 + d1, 4)
            
            return {
                "p50": percentile(50),
                "p75": percentile(75),
                "p90": percentile(90),
                "p95": percentile(95),
                "p99": percentile(99),
            }
        
        # 标准差和变异系数
        def calc_std(values: list) -> dict:
            n = len(values)
            if n < 2:
                return {"std_dev": 0, "cv": 0}
            
            avg = sum(values) / n
            variance = sum((x - avg) ** 2 for x in values) / (n - 1)
            std_dev = variance ** 0.5
            cv = (std_dev / avg * 100) if avg > 0 else 0
            
            return {
                "std_dev": round(std_dev, 4),
                "cv": round(cv, 2)  # 变异系数百分比
            }
        
        # 异常值检测 (IQR 方法)
        def detect_outliers(values: list) -> dict:
            if len(values) < 4:
                return {"count": 0, "percentage": 0, "values": []}
            
            sorted_values = sorted(values)
            n = len(sorted_values)
            
            # 计算百分位
            k25 = int((n - 1) * 0.25)
            k75 = int((n - 1) * 0.75)
            f25 = int(k25)
            c25 = f25 + 1
            q1 = sorted_values[f25] * (c25 - k25) + sorted_values[c25] * (k25 - f25) if c25 < n else sorted_values[f25]
            
            f75 = int(k75)
            c75 = f75 + 1
            q3 = sorted_values[f75] * (c75 - k75) + sorted_values[c75] * (k75 - f75) if c75 < n else sorted_values[f75]
            
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            
            outliers = [v for v in values if v < lower or v > upper]
            
            return {
                "count": len(outliers),
                "percentage": round(len(outliers) / len(values) * 100, 2),
                "values": outliers,
                "bounds": {"lower": round(lower, 4), "upper": round(upper, 4)}
            }
        
        # 计算各项统计
        return {
            "count": len(metrics_list),
            "ttft": {
                **calc_basic(ttft_values),
                **calc_percentiles(ttft_values),
                **calc_std(ttft_values),
                "outliers": detect_outliers(ttft_values)
            },
            "tpft": {
                **calc_basic(tpft_values),
                **calc_percentiles(tpft_values),
                **calc_std(tpft_values),
                "outliers": detect_outliers(tpft_values)
            },
            "total_time": {
                **calc_basic(total_times),
                **calc_percentiles(total_times),
                **calc_std(total_times),
                "outliers": detect_outliers(total_times)
            },
            "tokens_per_second": {
                **calc_basic(tps_values),
                **calc_percentiles(tps_values),
                **calc_std(tps_values),
                "outliers": detect_outliers(tps_values)
            },
            "output_tokens": {
                **calc_basic(output_tokens),
                **calc_percentiles(output_tokens),
                **calc_std(output_tokens),
                "outliers": detect_outliers(output_tokens)
            }
        }