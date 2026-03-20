#!/usr/bin/env python3
"""
测试移动云模型是否支持 thinking 模式
"""
import asyncio
import json
import time

# 添加项目路径
import sys
sys.path.insert(0, '/Volumes/mobileDisk/test/模型速度测试/model_speed_test')

from src.client import ModelClient


async def test_yidongyun():
    """测试移动云模型的思考模式"""
    
    # 移动云 API 配置
    client = ModelClient(
        name="移动云codingPlan-test",
        endpoint="https://api.e.space.cn/v1/chat/completions",  # 移动云 API 端点
        api_key="olpkbJRoT81NC1uNa6hEvg-aG0kMeRnEi7b840_wyLY",
        model="codingPlan",  # 模型名称
        provider="openai"  # 使用 OpenAI 兼容格式
    )
    
    test_prompt = "你好，请用一句话打个招呼"
    
    print("=" * 60)
    print("测试移动云模型思考模式")
    print("=" * 60)
    print(f"\n测试提示: {test_prompt}\n")
    
    # 测试1: 不带 thinking 参数
    print("【测试1】不带 thinking 参数:")
    print("-" * 40)
    try:
        result = await client.chat(
            prompt=test_prompt,
            max_tokens=200,
            temperature=0.7,
            stream=False
        )
        
        if result.get("error"):
            print(f"错误: {result['error']}")
        else:
            content = result.get("content", "")
            print(f"响应:\n{content}")
            print(f"\n响应长度: {len(content)} 字符")
            
            # 检查是否包含思考标签
            if '<begin_of_thought>' in content or '<think>' in content:
                print("✓ 检测到思考标签")
            else:
                print("✗ 未检测到思考标签")
                
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 60)
    print("【测试2】带 thinking=true 参数:")
    print("-" * 40)
    
    try:
        result = await client.chat(
            prompt=test_prompt,
            max_tokens=200,
            temperature=0.7,
            stream=False,
            thinking=True  # 启用思考模式
        )
        
        if result.get("error"):
            print(f"错误: {result['error']}")
        else:
            content = result.get("content", "")
            print(f"响应:\n{content}")
            print(f"\n响应长度: {len(content)} 字符")
            
            # 检查是否包含思考标签
            if '<begin_of_thought>' in content:
                print("✓ 检测到 <begin_of_thought> 标签")
            if '</end_of_thought>' in content:
                print("✓ 检测到 </end_of_thought> 标签")
            if '<think>' in content:
                print("✓ 检测到 <think> 标签")
            if '</think>' in content:
                print("✓ 检测到 </think> 标签")
            if '<think>' in content:
                print("✓ 检测到 <think> 标签")
                
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "=" * 60)
    print("【测试3】流式响应:")
    print("-" * 40)
    
    try:
        chunks_data = []
        async for chunk in client.chat_stream(
            prompt=test_prompt,
            max_tokens=200,
            temperature=0.7
        ):
            if chunk.error:
                print(f"错误: {chunk.error}")
                break
            print(f"[{chunk.is_think}] {chunk.content}", end="", flush=True)
            chunks_data.append({
                "content": chunk.content,
                "is_think": chunk.is_think,
                "is_first": chunk.is_first
            })
        
        print("\n\n流式块分析:")
        think_count = sum(1 for c in chunks_data if c['is_think'])
        print(f"总块数: {len(chunks_data)}")
        print(f"Think 块数: {think_count}")
        
    except Exception as e:
        print(f"错误: {e}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_yidongyun())