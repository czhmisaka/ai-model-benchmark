#!/usr/bin/env python3
"""测试公网可访问的模型"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.client import ModelClient

async def main():
    # 测试 DeepSeek
    client = ModelClient(
        name="DeepSeek-Chat",
        endpoint="https://api.deepseek.com/v1/chat/completions",
        api_key="",  # 需要填入 API key
        model="deepseek-chat",
        provider="openai",  # DeepSeek 使用 OpenAI 兼容格式
        temperature=0.7,
        max_tokens=100,
    )
    
    messages = [{"role": "user", "content": "Hi, 简单介绍一下自己"}]
    
    print("测试 DeepSeek API...")
    count = 0
    async for chunk in client.chat_stream(messages=messages, max_tokens=100):
        count += 1
        content = getattr(chunk, 'content', '') or ''
        reasoning = getattr(chunk, 'reasoning_content', None) or ''
        print(f"Chunk {count}: content='{content[:30]}...' reasoning='{reasoning[:20] if reasoning else 'None'}...'")
        if count >= 5:
            print("已接收5个chunk，停止")
            break
    
    await client.close()
    print("✅ 测试完成!")

asyncio.run(main())
