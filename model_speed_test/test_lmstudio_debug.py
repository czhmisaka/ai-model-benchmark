"""
LMStudio API 调试脚本
"""
import asyncio
import json
import sys
import time
sys.path.insert(0, '.')

from src.client import ModelClient


async def test_lmstudio():
    """测试 LMStudio API 并打印详细信息"""
    
    client = ModelClient(
        name="LMStudio-Qwen3.5-9B",
        endpoint="http://localhost:1234/v1/chat/completions",
        api_key="not-needed",
        model="qwen/qwen3.5-9b",
        timeout=300  # 增加超时到5分钟
    )
    
    print("=" * 50)
    print("开始测试 LMStudio API")
    print("=" * 50)
    
    try:
        # 测试流式 API
        print("\n[1] 测试流式 API...")
        chunk_count = 0
        total_reasoning = ""
        total_content = ""
        
        start_time = time.time()
        
        async for chunk in client.chat_stream(
            prompt="你好啊",
            max_tokens=4096,  # 增加 max_tokens
            temperature=0.7
        ):
            chunk_count += 1
            
            # 只打印关键信息，避免刷屏
            if chunk_count % 50 == 1 or not chunk.is_think:
                elapsed = time.time() - start_time
                print(f"Chunk {chunk_count}, is_think={chunk.is_think}, is_think_end={chunk.is_think_end}, elapsed={elapsed:.1f}s")
            
            if chunk.is_think:
                total_reasoning += chunk.content
            else:
                total_content += chunk.content
                
            # 如果已经输出了非 think 内容，说明思考过程结束了
            if not chunk.is_think and chunk.content:
                print(f">>> Answer 开始输出! preview: {chunk.content[:100]}...")
        
        elapsed = time.time() - start_time
        print(f"\n总耗时: {elapsed:.1f}秒")
        
        print("\n" + "=" * 50)
        print("流式测试完成")
        print(f"总 chunk 数: {chunk_count}")
        print(f"总 reasoning 长度: {len(total_reasoning)}")
        print(f"总 content 长度: {len(total_content)}")
        print("=" * 50)
        
        # 测试非流式 API
        print("\n[2] 测试非流式 API...")
        result = await client.chat(
            prompt="你好啊",
            max_tokens=4096,  # 增加 max_tokens
            temperature=0.7,
            stream=False
        )
        
        print("\n非流式结果:")
        print(f"content length: {len(result.get('content', ''))}")
        print(f"content preview: {result.get('content', '')[:500]}...")
        print(f"raw_response keys: {result.get('raw_response', {}).keys()}")
        
        # 打印完整的 raw_response
        raw = result.get('raw_response', {})
        if 'choices' in raw and raw['choices']:
            msg = raw['choices'][0].get('message', {})
            print(f"\nmessage 完整内容:")
            print(f"  content: {msg.get('content', '')[:200]}...")
            print(f"  reasoning_content: {msg.get('reasoning_content', '')[:200]}...")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_lmstudio())