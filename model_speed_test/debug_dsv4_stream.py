#!/usr/bin/env python3
"""诊断 DSv4 流式响应 - 打印原始 SSE 数据"""
import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

load_dotenv()

DSV4_ENDPOINT = os.getenv("DSV4_ENDPOINT", "https://api.siliconflow.cn/v1/chat/completions")
DSV4_API_KEY = os.getenv("DSV4_API_KEY", "")
DSV4_MODEL = os.getenv("DSV4_MODEL", "deepseek-ai/DeepSeek-V3")

async def test_dsv4_stream():
    headers = {
        "Authorization": f"Bearer {DSV4_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DSV4_MODEL,
        "messages": [
            {"role": "user", "content": "用一句话介绍你自己"}
        ],
        "stream": True,
        "max_tokens": 200
    }
    
    print(f"=== DSv4 流式诊断 ===")
    print(f"Endpoint: {DSV4_ENDPOINT}")
    print(f"Model: {DSV4_MODEL}")
    print(f"Payload: {json.dumps(payload, ensure_ascii=False)}\n")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DSV4_ENDPOINT, json=payload, headers=headers) as response:
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}\n")
                
                if response.status != 200:
                    text = await response.text()
                    print(f"Error body: {text}")
                    return
                
                line_count = 0
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8").strip()
                    line_count += 1
                    
                    if not line:
                        print(f"[{line_count}] EMPTY LINE")
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            print(f"[{line_count}] >>> [DONE] <<<")
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                role = delta.get("role")
                                content = delta.get("content", "")
                                finish = choices[0].get("finish_reason")
                                
                                # 打印详细信息
                                parts = []
                                if role: parts.append(f"role={role}")
                                if content: parts.append(f"content={repr(content)}")
                                if finish: parts.append(f"finish={finish}")
                                
                                print(f"[{line_count}] delta: {', '.join(parts) if parts else '(empty)'}")
                            else:
                                # 检查 usage
                                usage = chunk.get("usage")
                                if usage:
                                    print(f"[{line_count}] usage: {usage}")
                                else:
                                    print(f"[{line_count}] no choices: {json.dumps(chunk)[:200]}")
                        except json.JSONDecodeError:
                            print(f"[{line_count}] INVALID JSON: {data_str[:200]}")
                    else:
                        print(f"[{line_count}] NON-DATA: {line[:200]}")
                
                print(f"\n=== 共 {line_count} 行 ===")
                
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dsv4_stream())