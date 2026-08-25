"""
指标计算测试补充
覆盖：多模态 token 估算、think/answer 翻转（标签型/无标签型）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import time
from src.metrics import count_tokens, estimate_tokens, estimate_input_tokens
from src.metrics import MetricsCalculator


class TestMultimodalTokens:
    """多模态 content（part 列表）token 估算测试"""
    
    def test_count_tokens_multimodal_list(self):
        """多模态 part 列表不应崩溃，且图片有固定估算"""
        content = [
            {"type": "text", "text": "描述这张图片"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}}
        ]
        result = count_tokens(content)
        assert isinstance(result, int)
        assert result > 0
    
    def test_estimate_tokens_list(self):
        """estimate_tokens 对 list 输入不崩溃"""
        content = [
            {"type": "text", "text": "hello"},
            {"type": "image_url", "image_url": {"url": "http://x/y.png"}}
        ]
        result = estimate_tokens(content)
        assert isinstance(result, int)
    
    def test_estimate_input_tokens_multimodal(self):
        """estimate_input_tokens 对多模态消息不崩溃"""
        content = [
            {"type": "text", "text": "描述这张图片"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}}
        ]
        result = estimate_input_tokens([{"role": "user", "content": content}])
        assert isinstance(result, int)
        assert result > 0
    
    def test_string_parts(self):
        """纯字符串 part 列表"""
        result = count_tokens(["纯字符串"])
        assert isinstance(result, int)
        assert result > 0
    
    def test_empty_and_none(self):
        assert count_tokens(None) == 0
        assert count_tokens([]) == 0
        assert estimate_tokens(None) == 0


class TestThinkAnswerFlip:
    """think→answer 翻转守卫测试"""
    
    def test_deepseek_style(self):
        """无标签型（reasoning_content 持续 is_think=True 后变 False）"""
        start = time.time()
        chunks = [
            {"content": "思考过程", "timestamp": start + 1.0, "is_think": True},
            {"content": "思考继续", "timestamp": start + 2.0, "is_think": True},
            {"content": "回答内容", "timestamp": start + 3.0, "is_think": False},
        ]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        assert m.think_tokens > 0
        assert m.answer_tokens > 0
    
    def test_tag_style(self):
        """标签型（<think> 标签 chunk is_think=False + is_think_end 结束）"""
        start = time.time()
        chunks = [
            {"content": "<begin_of_thought>思考内容</begin_of_thought>", "timestamp": start + 1.0, "is_think": False},
            {"content": "更多思考", "timestamp": start + 2.0, "is_think": False},
            {"content": "<end_of_thought>", "timestamp": start + 3.0, "is_think": False, "is_think_end": True},
            {"content": "最终答案", "timestamp": start + 4.0, "is_think": False},
        ]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        # 修复回归：标签型 think_tokens 不应为 0
        assert m.think_tokens > 0
        assert m.answer_tokens > 0
    
    def test_plain_answer(self):
        """纯 answer 无 think"""
        start = time.time()
        chunks = [{"content": "你好", "timestamp": start + 1.0, "is_think": False}]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        assert m.think_tokens == 0
        assert m.answer_tokens > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
