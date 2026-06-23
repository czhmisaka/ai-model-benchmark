#!/usr/bin/env python3
"""
DSv4 流式响应原始块记录脚本
用于逐块记录服务端返回的每个 SSE chunk，不做任何解析处理。

用法：
    1. 确认配置信息正确（ENDPOINT, MODEL）
    2. 运行: python test_dsv4_stream_raw.py
    3. 将生成的 test_dsv4_stream_output.txt 内容贴给 Cline 分析
"""
import asyncio
import aiohttp
import json
import time
import sys

# ============================================================
# API 配置
# ============================================================
ENDPOINT = "http://20.6.2.59:8000/v1/chat/completions"
MODEL = "dsv4"
API_KEY = ""  # 内部服务无需 API Key
TEST_PROMPT = "你好"
# ============================================================

# 输出文件
OUTPUT_FILE = "test_dsv4_stream_output.txt"

# 请求体
PAYLOAD = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": TEST_PROMPT}
    ],
    "stream": True,          # 流式模式
    "max_tokens": 200,       # 限制长度便于分析
    "temperature": 0.6
}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream"
}
if API_KEY:
    HEADERS["Authorization"] = f"Bearer {API_KEY}"


async def main():
    results = {
        "config": {
            "endpoint": ENDPOINT,
            "model": MODEL,
            "prompt": TEST_PROMPT,
            "payload": PAYLOAD
        },
        "chunks": [],
        "http_status": None,
        "http_headers": {},
        "error": None,
        "total_chunks": 0,
        "content_chunks": 0,
        "reasoning_chunks": 0,
        "finish_reason": None,
        "final_usage": None
    }

    print("=" * 70)
    print("DSv4 流式响应原始块记录测试")
    print("=" * 70)
    print(f"Endpoint: {ENDPOINT}")
    print(f"Model: {MODEL}")
    print(f"Prompt: {TEST_PROMPT}")
    print("-" * 70)

    try:
        timeout = aiohttp.ClientTimeout(total=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                ENDPOINT,
                json=PAYLOAD,
                headers=HEADERS
            ) as response:
                results["http_status"] = response.status
                results["http_headers"] = dict(response.headers)

                print(f"HTTP Status: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                print("-" * 70)
                print("开始接收流式数据...\n")

                if response.status != 200:
                    error_text = await response.text()
                    results["error"] = f"HTTP {response.status}: {error_text}"
                    print(f"❌ 错误: {error_text[:500]}")
                    return results

                chunk_index = 0
                async for raw_line in response.content:
                    try:
                        line = raw_line.decode("utf-8").rstrip("\n").rstrip("\r")
                    except UnicodeDecodeError:
                        line = f"[解码失败] raw_bytes={raw_line[:100]}"

                    # 记录原始行
                    chunk_record = {
                        "index": chunk_index,
                        "raw_line": line,
                        "parsed": None,
                        "parsed_keys": None,
                        "has_data": False,
                        "has_choices": False,
                        "has_content": False,
                        "has_reasoning": False,
                        "has_usage": False,
                        "content": None,
                        "reasoning_content": None,
                        "is_done": False
                    }

                    # 空行跳过
                    if not line:
                        chunk_record["note"] = "空行"
                        results["chunks"].append(chunk_record)
                        chunk_index += 1
                        continue

                    # 检查是否是 data: 行
                    if line.startswith("data: "):
                        data_str = line[6:]
                        chunk_record["has_data"] = True

                        if data_str == "[DONE]":
                            chunk_record["is_done"] = True
                            chunk_record["note"] = "流结束标记 [DONE]"
                            results["chunks"].append(chunk_record)
                            print(f"[{chunk_index}] 🏁 [DONE] - 流结束")
                            chunk_index += 1
                            break

                        # 尝试解析 JSON
                        try:
                            data = json.loads(data_str)
                            chunk_record["parsed"] = data
                            chunk_record["parsed_keys"] = list(data.keys()) if isinstance(data, dict) else "not_dict"

                            # 检查 choices
                            if "choices" in data:
                                chunk_record["has_choices"] = True
                                choices = data["choices"]
                                if choices:
                                    delta = choices[0].get("delta", {})

                                    # 提取 content
                                    content = delta.get("content")
                                    if content:
                                        chunk_record["has_content"] = True
                                        chunk_record["content"] = content
                                        results["content_chunks"] += 1

                                    # 提取 reasoning_content
                                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                                    if reasoning:
                                        chunk_record["has_reasoning"] = True
                                        chunk_record["reasoning_content"] = reasoning
                                        results["reasoning_chunks"] += 1

                                    # finish_reason
                                    finish = choices[0].get("finish_reason", "")
                                    if finish:
                                        results["finish_reason"] = finish

                                    # 提取 usage
                                    usage = data.get("usage")
                                    if usage:
                                        chunk_record["has_usage"] = True
                                        chunk_record["usage"] = usage
                                        results["final_usage"] = usage

                                    # 打印 chunk 信息
                                    ch_type = []
                                    if reasoning:
                                        ch_type.append("💭REASONING")
                                    if content:
                                        ch_type.append("💬CONTENT")
                                    if not ch_type:
                                        ch_type.append("⚪EMPTY")

                                    print(
                                        f"[{chunk_index}] {'+'.join(ch_type)} "
                                        f"| content={repr(content[:60]) if content else 'None'} "
                                        f"| reasoning={repr(reasoning[:60]) if reasoning else 'None'} "
                                        f"| finish={repr(finish) if finish else '-'} "
                                        f"| usage={usage if usage else '-'}"
                                    )
                                else:
                                    chunk_record["note"] = "choices 为空列表"
                            else:
                                chunk_record["note"] = f"无 choices 字段, keys={chunk_record['parsed_keys']}"

                        except json.JSONDecodeError as e:
                            chunk_record["note"] = "JSON 解析失败"
                            chunk_record["parse_error"] = str(e)

                    else:
                        # 非 data: 开头的行
                        chunk_record["note"] = f"非data行: {line[:80]}"
                        print(f"[{chunk_index}] 其他行: {line[:100]}")

                    results["chunks"].append(chunk_record)
                    chunk_index += 1

                results["total_chunks"] = chunk_index

    except aiohttp.ClientError as e:
        results["error"] = f"连接错误: {str(e)}"
        print(f"❌ 连接错误: {e}")
    except Exception as e:
        results["error"] = f"未知错误: {str(e)}"
        print(f"❌ 未知错误: {e}")

    # ============================================================
    # 输出统计摘要
    # ============================================================
    print("\n" + "=" * 70)
    print("统计摘要")
    print("=" * 70)
    print(f"总块数: {results['total_chunks']}")
    print(f"有 content 的块: {results['content_chunks']}")
    print(f"有 reasoning 的块: {results['reasoning_chunks']}")
    print(f"HTTP 状态码: {results['http_status']}")
    print(f"finish_reason: {results['finish_reason']}")
    if results["final_usage"]:
        print(f"最终 usage: {results['final_usage']}")
    if results["error"]:
        print(f"错误: {results['error']}")

    # ============================================================
    # 写入详细输出文件
    # ============================================================
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("DSv4 流式响应原始块记录 - 详细报告\n")
        f.write("=" * 70 + "\n\n")

        f.write("## 配置信息\n\n")
        f.write(f"- Endpoint: {ENDPOINT}\n")
        f.write(f"- Model: {MODEL}\n")
        f.write(f"- Prompt: {TEST_PROMPT}\n")
        f.write(f"- Payload:\n```json\n{json.dumps(PAYLOAD, indent=2, ensure_ascii=False)}\n```\n\n")

        f.write("## HTTP 响应\n\n")
        f.write(f"- Status: {results['http_status']}\n")
        f.write(f"- Headers:\n```\n")
        for k, v in results.get("http_headers", {}).items():
            f.write(f"  {k}: {v}\n")
        f.write("```\n\n")

        if results["error"]:
            f.write(f"## 错误\n\n```\n{results['error']}\n```\n\n")

        f.write("## 统计摘要\n\n")
        f.write(f"- 总块数: {results['total_chunks']}\n")
        f.write(f"- 有 content 的块: {results['content_chunks']}\n")
        f.write(f"- 有 reasoning 的块: {results['reasoning_chunks']}\n")
        f.write(f"- finish_reason: {results['finish_reason']}\n")
        if results["final_usage"]:
            f.write(f"- 最终 usage: {json.dumps(results['final_usage'])}\n")

        f.write("\n## 逐块详细记录\n\n")
        f.write("| # | 类型 | content | reasoning | finish | usage | raw_line 前80字符 |\n")
        f.write("|---|------|---------|-----------|--------|-------|-------------------|\n")

        for ch in results["chunks"]:
            idx = ch["index"]

            # 类型
            if ch.get("is_done"):
                chtype = "🏁DONE"
            elif ch.get("has_reasoning") and ch.get("has_content"):
                chtype = "💭💬BOTH"
            elif ch.get("has_reasoning"):
                chtype = "💭REASON"
            elif ch.get("has_content"):
                chtype = "💬CONTENT"
            elif ch.get("has_choices"):
                chtype = "⚪EMPTY"
            elif ch.get("has_data"):
                chtype = "📦OTHER"
            else:
                chtype = "⬜NOISE"

            content_str = repr(ch.get("content", "")[:40]) if ch.get("content") else "-"
            reasoning_str = repr(ch.get("reasoning_content", "")[:40]) if ch.get("reasoning_content") else "-"

            # finish_reason
            finish = "-"
            if ch.get("parsed") and "choices" in ch.get("parsed", {}):
                choices = ch["parsed"]["choices"]
                if choices:
                    finish = choices[0].get("finish_reason", "-") or "-"

            # usage
            usage_str = str(ch.get("usage", "-")) if ch.get("usage") else "-"

            # raw_line 截断
            raw = ch.get("raw_line", "")[:80].replace("|", "\\|")

            f.write(f"| {idx} | {chtype} | {content_str} | {reasoning_str} | {finish} | {usage_str} | {raw} |\n")

        f.write("\n## 原始数据（JSON）\n\n```json\n")
        simplified = []
        for ch in results["chunks"]:
            simplified.append({
                "index": ch["index"],
                "raw_line": ch["raw_line"][:200],
                "has_content": ch["has_content"],
                "has_reasoning": ch["has_reasoning"],
                "content": ch.get("content"),
                "reasoning_content": ch.get("reasoning_content"),
                "is_done": ch["is_done"],
                "parsed_keys": ch.get("parsed_keys"),
                "usage": ch.get("usage"),
                "note": ch.get("note")
            })
        f.write(json.dumps(simplified, indent=2, ensure_ascii=False))
        f.write("\n```\n")

    print(f"\n✅ 详细报告已写入: {OUTPUT_FILE}")
    return results


if __name__ == "__main__":
    asyncio.run(main())