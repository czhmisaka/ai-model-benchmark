#!/usr/bin/env python3
"""
测试数据库中所有注册的模型
按 Provider 分组调用，记录结果
"""
import asyncio
import sqlite3
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.client import ModelClient
from src.providers import get_provider_registry


def load_models_from_db(db_path: str) -> List[Dict[str, Any]]:
    """从数据库加载所有启用的模型"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, provider, endpoint, api_key, model,
               temperature, top_p, max_tokens, presence_penalty,
               frequency_penalty, thinking_enabled, enabled
        FROM models
        WHERE enabled = 1
    """)
    
    models = []
    for row in cursor.fetchall():
        models.append({
            "id": row["id"],
            "name": row["name"],
            "provider": row["provider"],
            "endpoint": row["endpoint"],
            "api_key": row["api_key"],
            "model": row["model"],
            "temperature": row["temperature"] if row["temperature"] else 0.7,
            "top_p": row["top_p"] if row["top_p"] else 1.0,
            "max_tokens": row["max_tokens"] if row["max_tokens"] else 4096,
            "presence_penalty": row["presence_penalty"] if row["presence_penalty"] else 0.0,
            "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] else 0.0,
            "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True,
        })
    
    conn.close()
    return models


async def test_model(model_config: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    """测试单个模型"""
    result = {
        "name": model_config["name"],
        "provider": model_config["provider"],
        "endpoint": model_config["endpoint"],
        "model": model_config["model"],
        "success": False,
        "error": None,
        "ttft": 0.0,
        "tpft": 0.0,
        "total_time": 0.0,
        "tokens_per_second": 0.0,
        "output_tokens": 0,
        "response_preview": "",
    }
    
    try:
        # 创建客户端
        client = ModelClient(
            name=model_config["name"],
            endpoint=model_config["endpoint"],
            api_key=model_config["api_key"],
            model=model_config["model"],
            provider=model_config["provider"],
            temperature=model_config["temperature"],
            top_p=model_config["top_p"],
            max_tokens=model_config["max_tokens"],
            presence_penalty=model_config["presence_penalty"],
            frequency_penalty=model_config["frequency_penalty"],
            thinking_enabled=model_config["thinking_enabled"],
        )
        
        # 测试消息
        test_messages = [
            {"role": "user", "content": "请简单介绍一下你自己。"}
        ]
        
        print(f"\n{'='*60}")
        print(f"测试模型: {model_config['name']}")
        print(f"Provider: {model_config['provider']}")
        print(f"Endpoint: {model_config['endpoint']}")
        print(f"{'='*60}")
        
        # 流式测试
        start_time = time.time()
        full_content = ""
        first_token_time = None
        chunk_count = 0
        
        try:
            # 创建流式请求
            stream = client.chat_stream(
                messages=test_messages,
                max_tokens=200,
                temperature=0.7
            )
            
            # 直接迭代，手动处理超时
            async for chunk in stream:
                # 检查超时
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    result["error"] = f"Timeout after {timeout}s"
                    print(f"⏱️ 超时 ({timeout}s)")
                    break
                
                chunk_count += 1
                
                if chunk.error:
                    result["error"] = chunk.error
                    break
                
                current_time = time.time()
                if first_token_time is None and chunk.is_first:
                    first_token_time = current_time - start_time
                
                # 获取内容
                content = getattr(chunk, 'content', '') or ''
                reasoning = getattr(chunk, 'reasoning_content', None) or ''
                full_content += content + reasoning
                
                # 打印进度
                if chunk_count % 20 == 0:
                    print(f"  已接收 {chunk_count} 个 chunks...")
            
            end_time = time.time()
            result["total_time"] = end_time - start_time
            result["ttft"] = first_token_time or 0
            result["tpft"] = result["total_time"] - result["ttft"]
            
            # 估算 token 数
            result["output_tokens"] = len(full_content) // 4  # 粗略估算
            
            if result["tpft"] > 0:
                result["tokens_per_second"] = result["output_tokens"] / result["tpft"]
            
            result["response_preview"] = full_content[:200] if full_content else ""
            result["success"] = bool(full_content) and result["ttft"] > 0
            
            print(f"✅ 成功!")
            print(f"  TTFT: {result['ttft']:.3f}s")
            print(f"  TPFT: {result['tpft']:.3f}s")
            print(f"  总耗时: {result['total_time']:.3f}s")
            print(f"  输出速度: {result['tokens_per_second']:.2f} tokens/s")
            print(f"  输出长度: {len(full_content)} 字符")
            
        except asyncio.TimeoutError:
            result["error"] = f"Timeout after {timeout}s"
            print(f"⏱️ 超时 ({timeout}s)")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ 错误: {e}")
        
        # 关闭客户端
        await client.close()
        
    except Exception as e:
        result["error"] = f"Client creation failed: {str(e)}"
        print(f"❌ 客户端创建失败: {e}")
    
    return result


async def test_models_by_provider(models: List[Dict[str, Any]]):
    """按 Provider 分组测试所有模型"""
    
    # 按 provider 分组
    providers = {}
    for model in models:
        provider = model["provider"]
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(model)
    
    print(f"\n{'='*60}")
    print(f"发现 {len(models)} 个启用的模型，分为 {len(providers)} 个 Provider")
    print(f"{'='*60}")
    
    for provider_name, provider_models in providers.items():
        print(f"\n\n{'#'*60}")
        print(f"# Provider: {provider_name} ({len(provider_models)} 个模型)")
        print(f"{'#'*60}")
        
        # 检查 provider 是否注册
        registry = get_provider_registry()
        provider_class = registry.get(provider_name)
        if provider_class:
            print(f"✅ Provider 已注册: {provider_class.__name__}")
        else:
            print(f"⚠️ Provider 未注册，将使用默认处理")
        
        # 测试该 provider 下的所有模型
        for model in provider_models:
            result = await test_model(model)
            
            # 保存结果
            yield result


async def main():
    """主函数"""
    print("="*60)
    print("AI模型速度测试 - 批量测试所有注册的模型")
    print("="*60)
    
    # 数据库路径
    db_path = Path(__file__).parent / "results" / "config.db"
    
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        return
    
    # 加载模型
    models = load_models_from_db(str(db_path))
    print(f"\n从数据库加载了 {len(models)} 个启用的模型")
    
    if not models:
        print("没有找到启用的模型")
        return
    
    # 显示模型列表
    print("\n模型列表:")
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model['name']} ({model['provider']}) - {model['model']}")
    
    # 询问是否继续（改为自动继续，因为测试需要时间）
    print(f"\n{'='*60}")
    print(f"将开始测试所有 {len(models)} 个模型...")
    print(f"每个模型有 {30}s 超时限制，请耐心等待...")
    print(f"{'='*60}")
    
    # 收集结果
    all_results = []
    
    # 测试所有模型
    async for result in test_models_by_provider(models):
        all_results.append(result)
    
    # 打印汇总
    print(f"\n\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    
    success_count = sum(1 for r in all_results if r["success"])
    failed_count = len(all_results) - success_count
    
    print(f"\n总计: {len(all_results)} 个模型")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 失败: {failed_count}")
    
    # 按 provider 汇总
    providers = {}
    for r in all_results:
        p = r["provider"]
        if p not in providers:
            providers[p] = {"success": 0, "failed": 0}
        if r["success"]:
            providers[p]["success"] += 1
        else:
            providers[p]["failed"] += 1
    
    print(f"\n按 Provider 汇总:")
    for p, stats in providers.items():
        print(f"  {p}: {stats['success']} 成功, {stats['failed']} 失败")
    
    # 保存详细结果
    output_file = Path(__file__).parent / "results" / "model_test_results.json"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细结果已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
