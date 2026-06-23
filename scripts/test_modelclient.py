"""使用 ModelClient 测试移动云模型"""
import asyncio
import os
import sys
sys.path.insert(0, '/Volumes/mobileDisk/test/模型速度测试/model_speed_test')

from src.client import ModelClient


async def test_modelclient():
    """使用 ModelClient 测试"""
    api_key = os.environ.get("YIDONGYUN_API_KEY", "")
    client = ModelClient(
        name="移动云codingPlan",
        endpoint="https://zhenze-huhehaote.cmecloud.cn/api/coding/v1/chat/completions",
        api_key=api_key,
        model="minimax-m2.5",
        provider="openai"
    )
    
    print("=" * 60)
    print("使用 ModelClient 测试移动云模型")
    print("=" * 60)
    
    think_chunks = []
    answer_chunks = []
    
    try:
        async for chunk in client.chat_stream(
            prompt="你好啊",
            max_tokens=200,
            temperature=0.7
        ):
            if chunk.error:
                print(f"错误: {chunk.error}")
                break
            
            # 根据 is_think 标记分别收集
            if chunk.is_think:
                think_chunks.append(chunk.content)
                print(f"[THINK] {chunk.content}", end="", flush=True)
            else:
                answer_chunks.append(chunk.content)
                print(f"[ANSWER] {chunk.content}", end="", flush=True)
        
        print("\n" + "=" * 60)
        print("分析结果:")
        print("=" * 60)
        
        think_content = "".join(think_chunks)
        answer_content = "".join(answer_chunks)
        
        print(f"Think 块数: {len(think_chunks)}")
        print(f"Answer 块数: {len(answer_chunks)}")
        print(f"Think 内容长度: {len(think_content)} 字符")
        print(f"Answer 内容长度: {len(answer_content)} 字符")
        
        if think_content:
            print(f"\n【Think 部分预览】\n{think_content[:300]}...")
        if answer_content:
            print(f"\n【Answer 部分预览】\n{answer_content}")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_modelclient())
