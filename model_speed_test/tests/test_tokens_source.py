"""tokens_source 透明化测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import pytest
from src.metrics import MetricsCalculator


class TestTokensSource:
    def test_api_usage_preferred(self):
        """流末尾 usage 块存在 → api_usage"""
        start = time.time()
        chunks = [
            {"content": "hello world", "timestamp": start + 0.1, "is_think": False},
            {"content": "", "timestamp": start + 0.2, "is_think": False,
             "usage": {"prompt_tokens": 10, "completion_tokens": 55}},
        ]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        assert m.tokens_source == "api_usage"
        assert m.output_tokens == 55

    def test_tiktoken_fallback(self):
        """无 usage → tiktoken_estimate"""
        start = time.time()
        chunks = [
            {"content": "hello world", "timestamp": start + 0.1, "is_think": False},
        ]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        assert m.tokens_source == "tiktoken_estimate"
        assert m.output_tokens > 0

    def test_api_usage_zero_falls_back(self):
        """usage 存在但值为0 → 回退 tiktoken"""
        start = time.time()
        chunks = [
            {"content": "hello world", "timestamp": start + 0.1, "is_think": False},
            {"content": "", "timestamp": start + 0.2, "is_think": False,
             "usage": {"completion_tokens": 0}},
        ]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        assert m.tokens_source == "tiktoken_estimate"
        assert m.output_tokens > 0

    def test_to_dict_contains_source(self):
        start = time.time()
        chunks = [{"content": "hi", "timestamp": start + 0.1, "is_think": False}]
        m = MetricsCalculator.calculate_stream_metrics(start_time=start, chunks=chunks)
        d = m.to_dict()
        assert d["tokens_source"] in ("api_usage", "tiktoken_estimate")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
