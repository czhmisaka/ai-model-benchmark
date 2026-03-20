#!/usr/bin/env python3
"""
测试移动云 codingPlan API 的原始输出格式
用于调试 think/answer 分割问题
"""
import asyncio
import aiohttp
import json
import time

# 移动云 codingPlan API 配置
API_ENDPOINT = "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1/chat/completions"
API_KEY = "olpkbJRoT81NC1uNa6hEvg-aG0kMeRnEi7b840_wyLY"
MODEL = "minimax-m2.5"

# 测试用例
TEST_PROMPT = "你好啊"

async def test_stream_api():
    """测试流式 API 的原始输出"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": TEST_PROMPT}
        ],
        "stream": True,
        "temperature": 0.7
    }
    
    print("=" * 80)
    print("测试移动云 codingPlan 模型原始输出")
    print("=" * 80)
    print(f"Prompt: {TEST_PROMPT}")
    print(f"Endpoint: {API_ENDPOINT}")
    print(f"Model: {MODEL}")
    print("-" * 80)
    
    try:
        start_time = time.perf_counter()
        first_token_time = None
        token_count = 0
        full_content = ""
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ API 错误 {response.status}: {error_text}")
                    return
                
                print("✅ 连接成功，开始接收流式响应...\n")
                print("原始数据流：")
                print("-" * 80)
                
                buffer = ""
                
                async for chunk_data in response.content.iter_chunked(1024):
                    try:
                        text = chunk_data.decode('utf-8')
                    except UnicodeDecodeError:
                        text = chunk_data.decode('utf-8', errors='replace')
                    
                    buffer += text
                    
                    # 处理可能的多条消息
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if not line or line == '[DONE]':
                            continue
                        
                        # 记录第一个 token 的时间
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                        
                        token_count += 1
                        
                        # 解析并打印原始 JSON
                        try:
                            data = json.loads(line)
                            print(f"[Chunk {token_count}] 原始 JSON:")
                            print(json.dumps(data, indent=2, ensure_ascii=False))
                            print("-" * 80)
                            
                            # 提取 content
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    full_content += delta['content']
                        except json.JSONDecodeError:
                            print(f"[Raw] {line}")
                
                total_time = time.perf_counter() - start_time
                
                print("\n" + "=" * 80)
                print("测试结果统计")
                print("=" * 80)
                print(f"首 Token 时间 (TTFT): {(first_token_time - start_time):.3f}s" if first_token_time else "N/A")
                print(f"总耗时: {total_time:.3f}s")
                print(f"收到 Token 数: {token_count}")
                print(f"输出速度: {token_count / total_time:.2f} tokens/s" if total_time > 0 else "N/A")
                
                print("\n" + "=" * 80)
                print("完整内容")
                print("=" * 80)
                print(full_content)
                
                # 分析 think/answer 分割
                print("\n" + "=" * 80)
                print("Think/Answer 分割分析")
                print("=" * 80)
                analyze_think_answer(full_content)
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_nonstream_api():
    """测试非流式 API 的原始输出"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": TEST_PROMPT}
        ],
        "stream": False,
        "temperature": 0.7
    }
    
    print("=" * 80)
    print("测试非流式 API 输出")
    print("=" * 80)
    
    try:
        start_time = time.perf_counter()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ API 错误 {response.status}: {error_text}")
                    return
                
                data = await response.json()
                total_time = time.perf_counter() - start_time
                
                print(f"总耗时: {total_time:.3f}s")
                print("\n原始响应 JSON:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # 分析响应结构
                print("\n" + "=" * 80)
                print("响应结构分析")
                print("=" * 80)
                
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    message = choice.get("message", {})
                    
                    content = message.get('content', '')
                    print(f"\n完整内容:")
                    print(content)
                    print("-" * 80)
                    
                    # 检查是否有 reasoning 字段
                    if "reasoning" in message:
                        print(f"Reasoning 字段: {message['reasoning'][:200]}...")
                    
                    # 检查其他可能的字段
                    for key in message.keys():
                        if key not in ["role", "content"]:
                            print(f"其他字段 {key}: {message[key]}")
                    
                    # 分析 think/answer 分割
                    print("\n" + "=" * 80)
                    print("Think/Answer 分割分析")
                    print("=" * 80)
                    analyze_think_answer(content)
                
                # 检查 usage
                if "usage" in data:
                    print(f"\nUsage: {json.dumps(data['usage'], indent=2)}")
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_think_answer(content):
    """分析 think/answer 分割"""
    if not content:
        print("内容为空")
        return
    
    # 常见的 think 标记
    think_patterns = [
        ("<think>", "</think>"),
        ("<think>", "</think>"),
        ("[think]", "[/think]"),
        ("THINK:", "THINK_END"),
        ("思考中", "思考结束"),
        ("正在思考", "思考完成"),
    ]
    
    found_think = False
    for start_tag, end_tag in think_patterns:
        if start_tag.lower() in content.lower():
            found_think = True
            print(f"✅ 发现 think 标记: {start_tag} ... {end_tag}")
            
            # 提取 think 部分
            start_lower = content.lower()
            start_idx = start_lower.find(start_tag.lower())
            end_idx = start_lower.find(end_tag.lower(), start_idx + len(start_tag))
            
            if start_idx >= 0 and end_idx > start_idx:
                think_content = content[start_idx + len(start_tag):end_idx]
                answer_content = content[end_idx + len(end_tag):]
                print(f"Think 内容长度: {len(think_content)} 字符")
                print(f"Answer 内容长度: {len(answer_content)} 字符")
                print(f"\nThink 部分预览:\n{think_content[:200]}...")
                print(f"\nAnswer 部分预览:\n{answer_content[:200]}...")
            break
    
    if not found_think:
        print("❌ 未发现明显的 think 标记")
        print("可能的原因:")
        print("1. 模型没有使用 think 模式")
        print("2. think 内容被合并到普通输出中")
        print("3. 模型使用不同的标记格式")
        
        # 检查是否在输出开头就有内容
        first_100 = content[:100]
        print(f"\n输出开头: {first_100}")
        
        # 检查是否有换行分隔的不同部分
        lines = content.split('\n')
        if len(lines) > 1:
            print(f"\n内容分段分析 ({len(lines)} 行):")
            for i, line in enumerate(lines[:5]):
                print(f"  行 {i+1}: {line[:50]}...")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--nonstream":
        asyncio.run(test_nonstream_api())
    else:
        asyncio.run(test_stream_api())