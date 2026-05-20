#!/usr/bin/env python3
"""测试单个模型"""
import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.client import ModelClient

db_path = Path(__file__).parent / "results" / "config.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# 获取第一个启用的模型
cursor = conn.cursor()
cursor.execute("""
    SELECT name, provider, endpoint, api_key, model, temperature, 
           top_p, max_tokens, thinking_enabled
    FROM models WHERE enabled = 1 LIMIT 1
""")
row = cursor.fetchone()
conn.close()

if not row:
    print("没有启用的模型")
    sys.exit(1)

print(f"测试模型: {row['name']}")
print(f"Provider: {row['provider']}")
print(f"Endpoint: {row['endpoint']}")

async def main():
    client = ModelClient(
        name=row['name'],
        endpoint=row['endpoint'],
        api_key=row['api_key'],
        model=row['model'],
        provider=row['provider'],
        temperature=row['temperature'] or 0.7,
        top_p=row['top_p'] or 1.0,
        max_tokens=row['max_tokens'] or 4096,
        thinking_enabled=bool(row['thinking_enabled']) if row['thinking_enabled'] is not None else True,
    )
    
    messages = [{"role": "user", "content": "Hi"}]
    
    print("\n开始流式测试...")
    count = 0
    async for chunk in client.chat_stream(messages=messages, max_tokens=50):
        count += 1
        content = getattr(chunk, 'content', '') or ''
        print(f"Chunk {count}: {content[:50]}...")
        if count >= 10:
            print("已接收10个chunk，停止")
            break
    
    await client.close()
    print("\n✅ 测试完成!")

asyncio.run(main())
