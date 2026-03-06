"""
性能指标计算模块测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import time
from src.metrics import TestMetrics, MetricsCalculator


class TestTestMetrics:
    """TestMetrics 数据类测试"""
    
    def test_default_values(self):
        """测试默认值"""
        metrics = TestMetrics()
        assert metrics.ttft == 0.0
        assert metrics.tpft == 0.0
        assert metrics.total_time == 0.0
        assert metrics.input_tokens == 0
        assert metrics.output_tokens == 0
    
    def test_tokens_per_second_calculation(self):
        """测试吞吐量计算"""
        metrics = TestMetrics()
        metrics.tpft = 10.0  # 10秒
        metrics.output_tokens = 100  # 100 tokens
        
        assert metrics.tokens_per_second == 10.0  # 100 / 10 = 10
    
    def test_tokens_per_second_zero_tpft(self):
        """测试零TPFT的吞吐量"""
        metrics = TestMetrics()
        metrics.tpft = 0.0
        metrics.output_tokens = 100
        
        assert metrics.tokens_per_second == 0.0
    
    def test_total_tokens_per_second(self):
        """测试总时间吞吐量"""
        metrics = TestMetrics()
        metrics.total_time = 20.0
        metrics.output_tokens = 100
        
        assert metrics.total_tokens_per_second == 5.0
    
    def test_to_dict(self):
        """测试转换为字典"""
        metrics = TestMetrics()
        metrics.ttft = 1.5
        metrics.tpft = 8.5
        metrics.total_time = 10.0
        metrics.output_tokens = 50
        metrics.input_tokens = 20
        
        result = metrics.to_dict()
        
        assert result["ttft_seconds"] == 1.5
        assert result["tpft_seconds"] == 8.5
        assert result["total_time_seconds"] == 10.0
        assert result["output_tokens"] == 50
        assert result["input_tokens"] == 20


class TestMetricsCalculator:
    """MetricsCalculator 测试"""
    
    def test_calculate_stream_metrics_empty_chunks(self):
        """测试空chunks处理"""
        metrics = MetricsCalculator.calculate_stream_metrics(
            start_time=time.time(),
            chunks=[]
        )
        
        assert metrics.ttft == 0.0
        assert metrics.tpft == 0.0
    
    def test_calculate_stream_metrics_with_chunks(self):
        """测试带chunks的指标计算"""
        start = time.time()
        chunks = [
            {"content": "Hello", "is_first": True, "timestamp": start + 1.0},
            {"content": " ", "is_first": False, "timestamp": start + 1.1},
            {"content": "World", "is_first": False, "timestamp": start + 1.5},
        ]
        
        metrics = MetricsCalculator.calculate_stream_metrics(
            start_time=start,
            chunks=chunks
        )
        
        assert metrics.ttft == pytest.approx(1.0, rel=0.1)
        assert metrics.total_time == pytest.approx(0.5, rel=0.1)
        assert metrics.output_tokens > 0
    
    def test_calculate_nonstream_metrics(self):
        """测试非流式指标计算"""
        start = time.time()
        end = start + 5.0
        
        metrics = MetricsCalculator.calculate_nonstream_metrics(
            start_time=start,
            end_time=end,
            input_tokens=100,
            output_tokens=50
        )
        
        assert metrics.total_time == 5.0
        assert metrics.ttft == 5.0  # 非流式TTFT等于总时间
        assert metrics.tpft == 0
        assert metrics.input_tokens == 100
        assert metrics.output_tokens == 50
    
    def test_aggregate_metrics_empty(self):
        """测试空列表聚合"""
        result = MetricsCalculator.aggregate_metrics([])
        assert result == {}
    
    def test_aggregate_metrics_single(self):
        """测试单条记录聚合"""
        metrics_list = [
            TestMetrics(ttft=1.0, tpft=9.0, total_time=10.0, output_tokens=100)
        ]
        
        result = MetricsCalculator.aggregate_metrics(metrics_list)
        
        assert result["count"] == 1
        assert result["ttft"]["avg"] == 1.0
        assert result["ttft"]["min"] == 1.0
        assert result["ttft"]["max"] == 1.0
    
    def test_aggregate_metrics_multiple(self):
        """测试多条记录聚合"""
        metrics_list = [
            TestMetrics(ttft=1.0, tpft=9.0, total_time=10.0, output_tokens=100),
            TestMetrics(ttft=2.0, tpft=8.0, total_time=10.0, output_tokens=100),
            TestMetrics(ttft=1.5, tpft=8.5, total_time=10.0, output_tokens=100),
        ]
        
        result = MetricsCalculator.aggregate_metrics(metrics_list)
        
        assert result["count"] == 3
        assert result["ttft"]["avg"] == pytest.approx(1.5, rel=0.1)
        assert result["ttft"]["min"] == 1.0
        assert result["ttft"]["max"] == 2.0
        assert result["tpft"]["avg"] == pytest.approx(8.5, rel=0.1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])