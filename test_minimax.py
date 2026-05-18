#!/usr/bin/env python3
"""
测试移动云 codingPlan 模型的原始输出格式
用于调试 think/answer 分割问题
"""
import asyncio
import aiohttp
import json
import os
import time

API_ENDPOINT = "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1/chat/completions"
API_KEY = os.environ.get("YIDONGYUN_API_KEY", "")
TEST_PROMPT = "你好啊"

async def test_stream_api():
    """测试流式 API 的原始输出"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "minimax-m2.5",
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "stream": True
    }
    
    print("=" * 80)
    print("测试移动云 codingPlan 模型原始输出")
    print("=" * 80)
    
    try:
        start_time = time.perf_counter()
        first_token_time = None
        token_count = 0
        full_content = ""
        
        async with aiohttp.ClientSession() as session:
            async with session.post(API_ENDPOINT, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status != 200:
                    print(f"❌ API 错误 {response.status}: {await response.text()}")
                    return
                
                print("✅ 连接成功，开始接收流式响应...\n")
                
                async for chunk_data in response.content.iter_chunked(1024):
                    text = chunk_data.decode('utf-8', errors='replace')
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line or line == '[DONE]':
                            continue
                        
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        
                        token_count += 1
                        
                        try:
                            data = json.loads(line)
                            content = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                full_content += content
                                print(f"[{token_count}] {repr(content)}")
                        except json.JSONDecodeError:
                            pass
                
                total_time = time.perf_counter() - start_time
                
                print("\n" + "=" * 80)
                print("测试结果统计")
                print("=" * 80)
                print(f"首 Token 时间 (TTFT): {(first_token_time - start_time):.3f}s" if first_token_time else "N/A")
                print(f"总耗时: {total_time:.3f}s")
                print(f"收到 Chunk 数: {token_count}")
                print(f"总内容长度: {len(full_content)} 字符")
                
                print("\n" + "=" * 80)
                print("完整输出内容:")
                print("=" * 80)
                print(full_content)
                
                # 分析 think 标记
                print("\n" + "=" * 80)
                print("Think/Answer 分割分析")
                print("=" * 80)
                
                # 检查各种可能的 think 标记
                think_markers = [
                    ("<think>", "<｜"),  # MiniMax 内部格式
                    ("<think>", "</think>"),
                    ("<think>", "<｜end_turn｜>"),
                    ("[think]", "[/think]"),
                    ("<think>", "\n\n")
                ]
                
                found_pattern = None
                for start, end in think_markers:
                    if start in full_content:
                        found_pattern = (start, end)
                        idx = full_content.find(start)
                        print(f"✅ 发现 think 标记: {start}")
                        
                        # 找到结束标记
                        end_idx = full_content.find(end, idx)
                        if end_idx > idx:
                            think_part = full_content[idx + len(start):end_idx]
                            answer_part = full_content[end_idx + len(end):]
                            print(f"   Think 部分长度: {len(think_part)} 字符")
                            print(f"   Answer 部分长度: {len(answer_part)} 字符")
                            print(f"\n   Think 内容预览:\n{think_part[:200]}")
                            print(f"\n   Answer 内容预览:\n{answer_part[:200]}")
                        break
                
                if not found_pattern:
                    print("❌ 未发现标准 think 标记")
                    print(f"\n输出开头 100 字符:\n{full_content[:100]}")
                    
                    # 检查是否包含特殊符号
                    special_chars = ['⟲', '▌', '思考', 'think', 'Think']
                    for char in special_chars:
                        if char in full_content:
                            print(f"✅ 发现特殊字符: {char}")
                            
    except asyncio.TimeoutError:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_stream_api())