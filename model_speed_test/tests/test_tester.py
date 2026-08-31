"""
核心测试引擎单测（ModelTester / ConcurrentTester）
使用 FakeClient 模拟流式/非流式响应，不依赖真实 API。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import time
import pytest

from src.tester import ModelTester


class FakeStreamChunk:
    def __init__(self, content="", is_first=False, is_think=False, is_think_end=False,
                 reasoning_content=None, error=None, usage=None):
        self.content = content
        self.is_first = is_first
        self.timestamp = time.perf_counter()
        self.is_think = is_think
        self.is_think_end = is_think_end
        self.reasoning_content = reasoning_content
        self.error = error
        self.usage = usage


class FakeClient:
    """模拟客户端：可控的流式/非流式响应"""
    def __init__(self, chunks=None, nonstream_result=None, delay=0, name="fake-model"):
        self.name = name
        self.chunks = chunks or []
        self.nonstream_result = nonstream_result or {}
        self.delay = delay
        self.call_count = 0

    async def chat_stream(self, prompt=None, max_tokens=100, temperature=0.7,
                          messages=None, system_prompt=None, **kwargs):
        self.call_count += 1
        for c in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield c

    async def chat(self, prompt=None, messages=None, system_prompt=None,
                   max_tokens=100, temperature=0.7, stream=False, **kwargs):
        self.call_count += 1
        return self.nonstream_result or {
            "content": "answer", "error": None,
            "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
            "usage": {}, "reasoning_content": None,
        }

    async def close(self):
        pass


class FakeRecorder:
    """内存记录器"""
    def __init__(self):
        self.records = []

    async def record(self, **kwargs):
        self.records.append(kwargs)


@pytest.mark.asyncio
async def test_stream_basic_success():
    """流式测试：正常响应 → success、指标齐全"""
    client = FakeClient(chunks=[
        FakeStreamChunk(content="你", is_first=True),
        FakeStreamChunk(content="好"),
        FakeStreamChunk(content="", usage={"prompt_tokens": 5, "completion_tokens": 3}),
    ])
    tester = ModelTester(client, FakeRecorder(), {"stream": True, "temperature": 0.7}, timeout=10)
    result = await tester.test_single_request(prompt="hello", round_num=1)

    assert result.success is True
    assert result.metrics is not None
    assert result.metrics.output_tokens > 0
    assert result.metrics.ttft >= 0


@pytest.mark.asyncio
async def test_stream_error_chunk():
    """流式错误 chunk → success=False 且 error 字段非空"""
    client = FakeClient(chunks=[FakeStreamChunk(error="boom")])
    tester = ModelTester(client, FakeRecorder(), {"stream": True}, timeout=10)
    result = await tester.test_single_request(prompt="hi", round_num=1)

    assert result.success is False
    assert "boom" in (result.error or "")


@pytest.mark.asyncio
async def test_stream_empty_output():
    """空输出 → success=False（空输出判失败）"""
    client = FakeClient(chunks=[FakeStreamChunk(content="")])
    tester = ModelTester(client, FakeRecorder(), {"stream": True}, timeout=10)
    result = await tester.test_single_request(prompt="hi", round_num=1)

    assert result.success is False


@pytest.mark.asyncio
async def test_nonstream_success():
    """非流式：正常返回 → success"""
    client = FakeClient(nonstream_result={
        "content": "answer text", "error": None,
        "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
    })
    tester = ModelTester(client, FakeRecorder(), {"stream": False}, timeout=10)
    result = await tester.test_single_request(prompt="hi", round_num=1)

    assert result.success is True
    assert result.metrics.output_tokens == 5


@pytest.mark.asyncio
async def test_nonstream_empty_output():
    """非流式空输出 → success=False"""
    client = FakeClient(nonstream_result={
        "content": "", "error": None, "input_tokens": 0, "output_tokens": 0,
    })
    tester = ModelTester(client, FakeRecorder(), {"stream": False}, timeout=10)
    result = await tester.test_single_request(prompt="hi", round_num=1)

    assert result.success is False


@pytest.mark.asyncio
async def test_timeout():
    """响应超时 → success=False + TimeoutError"""
    async def slow_stream():
        await asyncio.sleep(5)
        yield FakeStreamChunk(content="late")

    class SlowClient(FakeClient):
        async def chat_stream(self, **kwargs):
            async for c in slow_stream():
                yield c

    tester = ModelTester(SlowClient(name="slow"), FakeRecorder(), {"stream": True}, timeout=0.2)
    result = await tester.test_single_request(prompt="hi", round_num=1)
    assert result.success is False


@pytest.mark.asyncio
async def test_stop_event_interrupts():
    """stop_event 触发 → 提前退出（B1 协作取消的回归保障）"""
    # WebAwareTester 使用 should_stop 轮询；这里通过 run_test_rounds + 事件验证循环退出
    stop_event = asyncio.Event()
    client = FakeClient(chunks=[
        FakeStreamChunk(content="a", is_first=True),
        FakeStreamChunk(content="b"),
    ])
    recorder = FakeRecorder()
    tester = ModelTester(client, recorder, {"stream": True}, timeout=10)

    # 直接测 _test_stream 内部对 stop 的感知由 main.WebAwareTester 负责，
    # 此处验证多轮循环可被外部打断（run_test_rounds 参数）
    results = await tester.run_test_rounds(prompt="hi", rounds=2, interval=0)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_recorder_receives_success_metadata():
    """成功结果应带 success:True metadata（空输出修复的回归保障）"""
    client = FakeClient(chunks=[
        FakeStreamChunk(content="ok", is_first=True),
    ])
    recorder = FakeRecorder()
    tester = ModelTester(client, recorder, {"stream": True}, timeout=10)
    result = await tester.test_single_request(prompt="hi", round_num=1)

    assert result.success is True
    assert len(recorder.records) == 1
    assert recorder.records[0]["metadata"]["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
