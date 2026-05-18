"""
FastAPI Web 应用
提供 SSE 流式事件和静态文件服务
支持简单的 API Key 认证
"""
import asyncio
import json
import os
import threading
import inspect
import ctypes
from pathlib import Path
from typing import Optional
from functools import wraps
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .emitter import TestEventEmitter, test_emitter


# 简单的认证依赖
def get_api_key(request: Request):
    """验证 API Key"""
    # 从请求头或查询参数获取 API Key
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    
    # 获取配置的 API Key
    config_api_key = os.environ.get("WEB_API_KEY", "")
    
    # 如果没有配置 API Key，则跳过验证（开发模式）
    if not config_api_key:
        return True
    
    # 验证 API Key
    if api_key != config_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    return True


# 受保护端点的认证依赖
def require_auth():
    """需要认证的端点依赖"""
    async def dependency(request: Request):
        return get_api_key(request)
    return dependency


# 创建 FastAPI 应用
app = FastAPI(
    title="AI模型速度测试",
    description="实时可视化测试进度和流式输出",
    version="1.0.0"
)

# 获取 web 模块目录
WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"

# 设置模板引擎
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Vue 前端目录
VUE_DAND_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页 - 使用 Vue 前端"""
    index_file = VUE_DAND_DIR / "index.html"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        # 回退到原生 HTML
        return templates.TemplateResponse(
            "index.html",
            {"request": request}
        )


@app.get("/events")
async def sse_events():
    """SSE 流式事件端点"""
    async def event_generator():
        # 创建新的订阅者
        queue = test_emitter.subscribe()
        
        try:
            while True:
                try:
                    # 等待事件，超时后发送心跳
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    
                    # 序列化为 SSE 格式
                    data = json.dumps({
                        "type": event.event_type,
                        "timestamp": event.timestamp,
                        "data": event.data
                    })
                    
                    yield f"data: {data}\n\n"
                    
                    # 如果是完成事件或汇总事件，发送完成后继续等待
                    if event.event_type in ("complete", "summary"):
                        pass
                        
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f": heartbeat\n\n"
                    
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            # 取消订阅
            test_emitter.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/status")
async def get_status():
    """获取当前状态和历史数据"""
    # 重新加载状态文件，确保获取最新数据
    test_emitter.reload_state()
    
    return {
        "history": [
            {
                "type": e.event_type,
                "timestamp": e.timestamp,
                "data": e.data
            }
            for e in test_emitter.get_history()
        ],
        "results": test_emitter.get_results(),
        "tasks": test_emitter._tasks if hasattr(test_emitter, '_tasks') else {}
    }


@app.post("/reset")
async def reset_test():
    """重置测试状态"""
    test_emitter.reset()
    return {"status": "reset"}


@app.get("/config")
async def get_config():
    """获取当前配置 - 从数据库读取"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    # 首先尝试从数据库读取
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取模型
            cursor.execute("""
                SELECT id, name, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled 
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
                })
            
            # 获取测试用例
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model 
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except:
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                else:
                    metadata = {}
                
                test_cases.append({
                    "id": row["case_id"],
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "max_tokens": row["max_tokens"] or 2000,
                    "temperature": row["temperature"] or 0.7,
                    "stream": bool(row["stream"]) if row["stream"] is not None else True,
                    "system_prompt": row["system_prompt"],
                    "messages": messages,
                    "metadata": metadata,
                    "enabled": bool(row["enabled"]),
                    "expected_output": row["expected_output"] or '',
                    "eval_model": row["eval_model"] or ''
                })
            
            conn.close()
            
            # 从数据库读取并发配置
            concurrency = {"test_rounds": 10, "interval": 1, "max_concurrent": 3, "num_requests": 1}
            output = {"results_dir": "results", "save_detailed_logs": True, "save_io_records": True, "export_csv": True, "export_jsonl": True}
            thresholds = {"ttft_max": 10, "min_tokens_per_sec": 10, "max_total_time": 60}
            
            try:
                cursor.execute("SELECT key, value FROM system_config")
                for row in cursor.fetchall():
                    if row["key"] == "concurrency":
                        concurrency = json.loads(row["value"])
                    elif row["key"] == "output":
                        output = json.loads(row["value"])
                    elif row["key"] == "thresholds":
                        thresholds = json.loads(row["value"])
            except Exception as e:
                print(f"从数据库读取系统配置失败: {e}")
            
            return {
                "version": "1.0.0",
                "models": models,
                "test_cases": test_cases,
                "concurrency": concurrency,
                "output": output,
                "thresholds": thresholds
            }
        else:
            raise Exception("config.db not found")
    except Exception as e:
        # 如果数据库读取失败，回退到从JSON文件读取
        print(f"从数据库读取配置失败: {e}")
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        return {"error": "配置文件不存在"}


@app.post("/config/models")
async def add_model(model_data: dict):
    """添加模型 - 操作数据库"""
    import json
    from pathlib import Path
    import sqlite3
    import uuid
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute("SELECT name FROM models WHERE name = ?", (model_data.get("name"),))
            if cursor.fetchone():
                conn.close()
                return {"error": "模型已存在"}
            
            # 插入新模型
            model_id = str(uuid.uuid4())
            name = model_data.get("name", "")
            provider = model_data.get("provider", "custom")
            endpoint = model_data.get("endpoint", "")
            api_key = model_data.get("api_key", "")
            model = model_data.get("model", name)
            enabled = 1 if model_data.get("enabled", True) else 0
            
            # 新参数
            temperature = model_data.get("temperature", 0.7)
            top_p = model_data.get("top_p", 1.0)
            max_tokens = model_data.get("max_tokens", 4096)
            presence_penalty = model_data.get("presence_penalty", 0.0)
            frequency_penalty = model_data.get("frequency_penalty", 0.0)
            thinking_enabled = 1 if model_data.get("thinking_enabled", True) else 0
            
            cursor.execute("""
                INSERT INTO models (model_id, name, provider, endpoint, api_key, model, group_name, tags, metadata, enabled, status, health_check_enabled, health_check_result, created_at, updated_at, temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (model_id, name, provider, endpoint, api_key, model, "production", "[]", "{}", enabled, "active", 1, "{}", datetime.now().isoformat(), datetime.now().isoformat(), temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled))
            
            conn.commit()
            
            # 返回更新后的所有模型列表（包含所有参数字段）
            cursor.execute("""
                SELECT id, name, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
                })
            
            conn.close()
            return {"status": "success", "models": models}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.put("/config/models/{model_name}")
async def update_model(model_name: str, model_data: dict):
    """更新模型 - 操作数据库"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取新的名称（如果名称被修改了）
            new_name = model_data.get("name", model_name)
            
            # 构建更新语句
            updates = []
            params = []
            
            if "endpoint" in model_data:
                updates.append("endpoint = ?")
                params.append(model_data["endpoint"])
            if "api_key" in model_data:
                updates.append("api_key = ?")
                params.append(model_data["api_key"])
            if "model" in model_data:
                updates.append("model = ?")
                params.append(model_data["model"])
            if "enabled" in model_data:
                updates.append("enabled = ?")
                params.append(1 if model_data["enabled"] else 0)
            if "name" in model_data:
                updates.append("name = ?")
                params.append(model_data["name"])
            
            # 新参数
            if "temperature" in model_data:
                updates.append("temperature = ?")
                params.append(model_data["temperature"])
            if "top_p" in model_data:
                updates.append("top_p = ?")
                params.append(model_data["top_p"])
            if "max_tokens" in model_data:
                updates.append("max_tokens = ?")
                params.append(model_data["max_tokens"])
            if "presence_penalty" in model_data:
                updates.append("presence_penalty = ?")
                params.append(model_data["presence_penalty"])
            if "frequency_penalty" in model_data:
                updates.append("frequency_penalty = ?")
                params.append(model_data["frequency_penalty"])
            if "thinking_enabled" in model_data:
                updates.append("thinking_enabled = ?")
                params.append(1 if model_data["thinking_enabled"] else 0)
            
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            
            # 如果名称改变了，需要先检查新名称是否已存在
            if new_name != model_name:
                cursor.execute("SELECT id FROM models WHERE name = ? AND name != ?", (new_name, model_name))
                if cursor.fetchone():
                    conn.close()
                    return {"error": "模型名称已存在"}
            
            params.append(model_name)
            
            cursor.execute(f"""
                UPDATE models 
                SET {', '.join(updates)}
                WHERE name = ?
            """, params)
            
            conn.commit()
            
            # 检查是否更新成功
            if cursor.rowcount == 0:
                conn.close()
                return {"error": "模型不存在"}
            
            # 返回更新后的所有模型列表（包含所有参数字段）
            cursor.execute("""
                SELECT id, name, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
                })
            
            conn.close()
            return {"status": "success", "models": models}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.delete("/config/models/{model_name}")
async def delete_model(model_name: str):
    """删除模型 - 操作数据库"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM models WHERE name = ?", (model_name,))
            
            conn.commit()
            
            if cursor.rowcount == 0:
                conn.close()
                return {"error": "模型不存在"}
            
            # 返回更新后的所有模型列表（包含所有参数字段）
            cursor.execute("""
                SELECT id, name, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
                })
            
            conn.close()
            return {"status": "success", "models": models}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.post("/config/models/ping")
async def ping_model_direct(model_data: dict):
    """通用模型连接测试 - 直接使用传入的配置"""
    import asyncio
    import time
    from pathlib import Path
    
    try:
        # 验证配置完整性
        endpoint = model_data.get("endpoint", "")
        api_key = model_data.get("api_key", "")
        model = model_data.get("model", "")
        
        if not endpoint:
            return {"success": False, "error": "endpoint 未配置"}
        if not api_key:
            return {"success": False, "error": "api_key 未配置"}
        if not model:
            return {"success": False, "error": "model 未配置"}
        
        # 尝试创建客户端并发送测试请求
        try:
            # 动态导入 client 模块
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.client import ModelClient
            
            # 创建客户端
            client = ModelClient(
                name="test_model",
                endpoint=endpoint,
                api_key=api_key,
                model=model
            )
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送简单的测试请求 - 使用流式响应，在首token返回时判定成功
            try:
                first_token_time = None
                content_preview = ""
                
                async for chunk in client.chat_stream(
                    prompt="你好！请回复一句问候语测试连接。",
                    max_tokens=100
                ):
                    # 记录首token时间
                    if first_token_time is None:
                        first_token_time = time.time()
                    
                    # 收集内容用于预览
                    if chunk.content:
                        content_preview += chunk.content
                    
                    # 首token返回后立即判定成功
                    if first_token_time is not None and content_preview:
                        break
                
                end_time = time.time()
                latency_ms = round((end_time - start_time) * 1000, 2)
                
                await client.close()
                
                # 检查返回结果
                if content_preview:
                    return {
                        "success": True,
                        "latency_ms": latency_ms,
                        "response_preview": content_preview[:100] if len(content_preview) > 100 else content_preview
                    }
                else:
                    return {
                        "success": False,
                        "error": "模型返回为空"
                    }
                    
            except asyncio.TimeoutError:
                await client.close()
                return {
                    "success": False,
                    "error": "请求超时（30秒）"
                }
            except Exception as e:
                try:
                    await client.close()
                except:
                    pass
                return {
                    "success": False,
                    "error": str(e)
                }
                
        except ImportError as e:
            return {
                "success": False,
                "error": f"无法导入客户端模块: {str(e)}"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/config/models/{model_name}/ping")
async def ping_model(model_name: str):
    """验证模型连接 - 发送简单测试请求"""
    import asyncio
    import time
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if not config_db_path.exists():
            return {"success": False, "error": "配置文件不存在"}
        
        conn = sqlite3.connect(str(config_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取模型配置
        cursor.execute("""
            SELECT name, endpoint, api_key, model, provider 
            FROM models WHERE name = ?
        """, (model_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"success": False, "error": "模型不存在"}
        
        model_config = {
            "name": row["name"],
            "endpoint": row["endpoint"],
            "api_key": row["api_key"],
            "model": row["model"],
            "provider": row["provider"]
        }
        
        # 验证配置完整性
        if not model_config.get("endpoint"):
            return {"success": False, "error": "模型 endpoint 未配置"}
        if not model_config.get("api_key"):
            return {"success": False, "error": "模型 api_key 未配置"}
        if not model_config.get("model"):
            return {"success": False, "error": "模型名称未配置"}
        
        # 尝试创建客户端并发送测试请求
        try:
            # 动态导入 client 模块
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from src.client import ModelClient
            
            # 创建客户端
            client = ModelClient(
                name=model_config["name"],
                endpoint=model_config["endpoint"],
                api_key=model_config["api_key"],
                model=model_config["model"]
            )
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送简单的测试请求
            try:
                result = await asyncio.wait_for(
                    client.chat(
                        prompt="你好！请回复一句问候语测试连接。",
                        max_tokens=100,
                        stream=False
                    ),
                    timeout=30.0  # 30秒超时
                )
                
                end_time = time.time()
                latency_ms = round((end_time - start_time) * 1000, 2)
                
                await client.close()
                
                # 检查返回结果
                content = result.get("content", "")
                if content:
                    return {
                        "success": True,
                        "latency_ms": latency_ms,
                        "response_preview": content[:100] if len(content) > 100 else content
                    }
                else:
                    return {
                        "success": False,
                        "error": "模型返回为空"
                    }
                    
            except asyncio.TimeoutError:
                await client.close()
                return {
                    "success": False,
                    "error": "请求超时（30秒）"
                }
            except Exception as e:
                try:
                    await client.close()
                except:
                    pass
                return {
                    "success": False,
                    "error": str(e)
                }
                
        except ImportError as e:
            return {
                "success": False,
                "error": f"无法导入客户端模块: {str(e)}"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/config/test-cases")
async def add_test_case(test_case_data: dict):
    """添加测试用例 - 保存到数据库"""
    import json
    from pathlib import Path
    import sqlite3
    import uuid
    import time
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 生成 case_id
            case_id = test_case_data.get("id", f"tc_{int(time.time() * 1000)}")
            
            # 检查是否已存在
            cursor.execute("SELECT case_id FROM test_cases WHERE case_id = ?", (case_id,))
            if cursor.fetchone():
                conn.close()
                # 如果 ID 存在，生成一个新的
                case_id = f"tc_{int(time.time() * 1000)}"
            
            name = test_case_data.get("name", "New Test Case")
            case_type = test_case_data.get("type", "custom")
            description = test_case_data.get("description", "")
            max_tokens = test_case_data.get("max_tokens", 2000)
            temperature = test_case_data.get("temperature", 0.7)
            stream = 1 if test_case_data.get("stream", True) else 0
            system_prompt = test_case_data.get("system_prompt", "")
            
            # 处理 messages
            messages = test_case_data.get("messages", [])
            if messages:
                messages_json = json.dumps(messages, ensure_ascii=False)
                # 从最后一条 user 消息提取内容作为 prompt
                prompt = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        prompt = msg.get("content", "")
                        break
            else:
                messages_json = "[]"
                prompt = test_case_data.get("prompt", "")
            
            metadata = test_case_data.get("metadata", {})
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            
            enabled = 1 if test_case_data.get("enabled", True) else 0
            
            # 处理新字段
            expected_output = test_case_data.get("expected_output", "")
            eval_model = test_case_data.get("eval_model", "")
            
            # 插入新测试用例
            cursor.execute("""
                INSERT INTO test_cases (case_id, name, type, description, max_tokens, temperature, stream, system_prompt, messages, metadata, enabled, expected_output, eval_model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (case_id, name, case_type, description, max_tokens, temperature, stream, system_prompt, messages_json, metadata_json, enabled, expected_output, eval_model, datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            
            # 返回更新后的所有测试用例列表
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model 
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except:
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                else:
                    metadata = {}
                
                test_cases.append({
                    "id": row["case_id"],
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "max_tokens": row["max_tokens"] or 2000,
                    "temperature": row["temperature"] or 0.7,
                    "stream": bool(row["stream"]) if row["stream"] is not None else True,
                    "system_prompt": row["system_prompt"],
                    "messages": messages,
                    "metadata": metadata,
                    "enabled": bool(row["enabled"]),
                    "expected_output": row["expected_output"] or '',
                    "eval_model": row["eval_model"] or ''
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.put("/config/test-cases/{test_case_id}")
async def update_test_case(test_case_id: str, test_case_data: dict):
    """更新测试用例 - 操作数据库"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 构建更新语句
            updates = []
            params = []
            
            if "name" in test_case_data:
                updates.append("name = ?")
                params.append(test_case_data["name"])
            if "type" in test_case_data:
                updates.append("type = ?")
                params.append(test_case_data["type"])
            if "description" in test_case_data:
                updates.append("description = ?")
                params.append(test_case_data["description"])
            if "max_tokens" in test_case_data:
                updates.append("max_tokens = ?")
                params.append(test_case_data["max_tokens"])
            if "temperature" in test_case_data:
                updates.append("temperature = ?")
                params.append(test_case_data["temperature"])
            if "stream" in test_case_data:
                updates.append("stream = ?")
                params.append(1 if test_case_data["stream"] else 0)
            if "system_prompt" in test_case_data:
                updates.append("system_prompt = ?")
                params.append(test_case_data["system_prompt"])
            if "messages" in test_case_data:
                updates.append("messages = ?")
                params.append(json.dumps(test_case_data["messages"], ensure_ascii=False))
            if "metadata" in test_case_data:
                updates.append("metadata = ?")
                params.append(json.dumps(test_case_data["metadata"], ensure_ascii=False))
            if "enabled" in test_case_data:
                updates.append("enabled = ?")
                params.append(1 if test_case_data["enabled"] else 0)
            if "expected_output" in test_case_data:
                updates.append("expected_output = ?")
                params.append(test_case_data["expected_output"])
            if "eval_model" in test_case_data:
                updates.append("eval_model = ?")
                params.append(test_case_data["eval_model"])
            
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            
            params.append(test_case_id)
            
            cursor.execute(f"""
                UPDATE test_cases 
                SET {', '.join(updates)}
                WHERE case_id = ?
            """, params)
            
            conn.commit()
            
            # 检查是否更新成功
            if cursor.rowcount == 0:
                conn.close()
                return {"error": "测试用例不存在"}
            
            # 返回更新后的所有测试用例列表
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model 
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except:
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                else:
                    metadata = {}
                
                test_cases.append({
                    "id": row["case_id"],
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "max_tokens": row["max_tokens"] or 2000,
                    "temperature": row["temperature"] or 0.7,
                    "stream": bool(row["stream"]) if row["stream"] is not None else True,
                    "system_prompt": row["system_prompt"],
                    "messages": messages,
                    "metadata": metadata,
                    "enabled": bool(row["enabled"]),
                    "expected_output": row["expected_output"] or '',
                    "eval_model": row["eval_model"] or ''
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.put("/config/system")
async def update_system_config(request: Request):
    """更新系统配置（concurrency/output/thresholds）- 保存到数据库"""
    import json
    from pathlib import Path
    import sqlite3
    
    data = await request.json()
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            cursor = conn.cursor()
            
            # 更新 concurrency
            if "concurrency" in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
                    VALUES (?, ?, ?, ?)
                """, ("concurrency", json.dumps(data["concurrency"], ensure_ascii=False), "并发配置", datetime.now().isoformat()))
            
            # 更新 output
            if "output" in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
                    VALUES (?, ?, ?, ?)
                """, ("output", json.dumps(data["output"], ensure_ascii=False), "输出配置", datetime.now().isoformat()))
            
            # 更新 thresholds
            if "thresholds" in data:
                cursor.execute("""
                    INSERT OR REPLACE INTO system_config (key, value, description, updated_at)
                    VALUES (?, ?, ?, ?)
                """, ("thresholds", json.dumps(data["thresholds"], ensure_ascii=False), "阈值配置", datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            return {"status": "success"}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


@app.delete("/config/test-cases/{test_case_id}")
async def delete_test_case(test_case_id: str):
    """删除测试用例 - 操作数据库"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM test_cases WHERE case_id = ?", (test_case_id,))
            
            conn.commit()
            
            if cursor.rowcount == 0:
                conn.close()
                return {"error": "测试用例不存在"}
            
            # 返回更新后的所有测试用例列表
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled 
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except:
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                else:
                    metadata = {}
                
                test_cases.append({
                    "id": row["case_id"],
                    "name": row["name"],
                    "type": row["type"],
                    "description": row["description"],
                    "max_tokens": row["max_tokens"] or 2000,
                    "temperature": row["temperature"] or 0.7,
                    "stream": bool(row["stream"]) if row["stream"] is not None else True,
                    "system_prompt": row["system_prompt"],
                    "messages": messages,
                    "metadata": metadata,
                    "enabled": bool(row["enabled"])
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        return {"error": str(e)}


# 测试控制
_test_running = False
_stop_event: Optional[asyncio.Event] = None
_test_task: Optional[asyncio.Task] = None
_test_thread: Optional[threading.Thread] = None


def _async_raise(tid, exctype):
    """强制停止线程"""
    try:
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = exctype.__class__
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")
    except Exception as e:
        print(f"强制停止线程失败: {e}")


def stop_test_thread():
    """强制停止测试线程"""
    global _test_thread
    
    if _test_thread and _test_thread.is_alive():
        print(f"正在强制停止测试线程: {_test_thread.ident}")
        try:
            _async_raise(_test_thread.ident, SystemExit)
        except Exception as e:
            print(f"停止线程时出错: {e}")
    
    _test_thread = None


def get_stop_event() -> asyncio.Event:
    """获取或创建停止事件"""
    global _stop_event
    if _stop_event is None:
        _stop_event = asyncio.Event()
    return _stop_event


def create_stop_event() -> asyncio.Event:
    """创建新的停止事件（用于每次测试开始）"""
    global _stop_event
    _stop_event = asyncio.Event()
    return _stop_event

@app.post("/test/start")
async def start_test(request: Request):
    """启动测试"""
    global _test_running, _test_task, _test_thread
    
    if _test_running:
        return {"error": "测试已在运行中"}
    
    try:
        body = await request.json()
    except:
        body = {}
    
    model_names = body.get("models", [])
    case_ids = body.get("cases", [])
    concurrent = body.get("concurrent", True)  # 默认启用并发
    
    # 获取前端传入的配置参数
    test_rounds = body.get("test_rounds", None)  # 测试轮数
    max_concurrent = body.get("max_concurrent", None)  # 最大并发数
    interval = body.get("interval", None)  # 请求间隔
    test_name = body.get("test_name", None)  # 测试名称
    
    # 创建新的停止事件
    stop_event = create_stop_event()
    
    # 标记测试开始
    _test_running = True
    
    # 在后台线程运行测试
    import threading
    import asyncio
    import sqlite3
    
    def run_test():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # 动态导入并运行
        from main import create_clients, get_enabled_test_cases, load_config
        from concurrent.futures import ThreadPoolExecutor
        
        # 首先从数据库加载配置
        config_db_path = Path(__file__).parent.parent / "results" / "config.db"
        
        config = {
            "models": [],
            "test_cases": [],
            "concurrency": {"test_rounds": 10, "interval": 1, "max_concurrent": 3},
            "output": {"results_dir": "results"}
        }
        
        # 从数据库读取测试用例
        if config_db_path.exists():
            try:
                conn = sqlite3.connect(str(config_db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 读取启用的测试用例
                cursor.execute("""
                    SELECT case_id, name, type, description, max_tokens, 
                           temperature, stream, system_prompt, messages, metadata, enabled,
                           expected_output, eval_model 
                    FROM test_cases WHERE enabled = 1
                """)
                
                for row in cursor.fetchall():
                    messages = row["messages"]
                    if messages:
                        try:
                            messages = json.loads(messages)
                        except:
                            messages = []
                    else:
                        messages = []
                    
                    metadata = row["metadata"]
                    if metadata:
                        try:
                            metadata = json.loads(metadata)
                        except:
                            metadata = {}
                    else:
                        metadata = {}
                    
                    test_case = {
                        "id": row["case_id"],
                        "name": row["name"],
                        "type": row["type"],
                        "description": row["description"],
                        "max_tokens": row["max_tokens"] or 2000,
                        "temperature": row["temperature"] or 0.7,
                        "stream": bool(row["stream"]) if row["stream"] is not None else True,
                        "system_prompt": row["system_prompt"],
                        "messages": messages,
                        "metadata": metadata,
                        "enabled": bool(row["enabled"]),
                        "expected_output": row["expected_output"] or '',
                        "eval_model": row["eval_model"] or ''
                    }
                    
                    # 如果指定了 case_ids，则过滤
                    if case_ids and row["case_id"] not in case_ids:
                        continue
                    
                    config["test_cases"].append(test_case)
                
                conn.close()
            except Exception as e:
                print(f"从数据库读取测试用例失败: {e}")
        
        # 如果没有从数据库读到测试用例，回退到 JSON 配置
        if not config.get("test_cases"):
            json_config = load_config()
            config["test_cases"] = json_config.get("test_cases", [])
            
            # 也读取模型配置
            config["models"] = json_config.get("models", [])
            
            # 如果指定了 case_ids，过滤测试用例
            if case_ids:
                config["test_cases"] = [tc for tc in config["test_cases"] if tc.get("id") in case_ids]
        else:
            # 从数据库读取模型配置
            config_db_path = Path(__file__).parent.parent / "results" / "config.db"
            if config_db_path.exists():
                try:
                    conn = sqlite3.connect(str(config_db_path))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT name, endpoint, api_key, model, enabled, provider,
                               temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
                        FROM models WHERE enabled = 1
                    """)
                    
                    for row in cursor.fetchall():
                        config["models"].append({
                            "name": row["name"],
                            "endpoint": row["endpoint"],
                            "api_key": row["api_key"],
                            "model": row["model"],
                            "enabled": bool(row["enabled"]),
                            "provider": row["provider"] if row["provider"] else "openai",
                            "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                            "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                            "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                            "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                            "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                            "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
                        })
                    
                    conn.close()
                except Exception as e:
                    print(f"从数据库读取模型失败: {e}")
        
        # 如果没有模型，回退到 JSON 配置
        if not config.get("models"):
            json_config = load_config()
            config["models"] = json_config.get("models", [])
        
        # 过滤指定模型
        if model_names:
            config["models"] = [m for m in config["models"] if m.get("name") in model_names]
        
        # 从数据库读取并发/输出配置（如果前端没有传入）
        if config_db_path.exists():
            try:
                conn = sqlite3.connect(str(config_db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM system_config")
                for row in cursor.fetchall():
                    if row["key"] == "concurrency" and test_rounds is None and max_concurrent is None and interval is None:
                        config["concurrency"] = json.loads(row["value"])
                    elif row["key"] == "output" and "output" not in config:
                        config["output"] = json.loads(row["value"])
                conn.close()
            except Exception as e:
                print(f"从数据库读取并发配置失败: {e}")
        
        # 如果前端传入了配置参数，覆盖配置文件中的值
        if test_rounds is not None:
            if "concurrency" not in config:
                config["concurrency"] = {}
            config["concurrency"]["test_rounds"] = test_rounds
        
        if max_concurrent is not None:
            if "concurrency" not in config:
                config["concurrency"] = {}
            config["concurrency"]["max_concurrent"] = max_concurrent
        
        if interval is not None:
            if "concurrency" not in config:
                config["concurrency"] = {}
            config["concurrency"]["interval"] = interval
        
        # 获取测试用例
        test_cases = [tc for tc in config.get("test_cases", []) if tc.get("enabled", True)]
        
        # 创建客户端
        clients = create_clients(config, model_names if model_names else None)
        
        # 并发模式：所有模型和测试用例组合都同时并发运行
        from main import run_tests_with_web
        
        async def run_all_concurrent():
            # 获取当前事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 为每个 (model, test_case) 组合创建独立任务
            tasks = []
            for client in clients:
                # 每个模型独立运行所有测试用例
                task = loop.create_task(
                    run_tests_with_web(
                        [client], 
                        config, 
                        test_cases, 
                        enable_web=True, 
                        stop_event=stop_event
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 在新的事件循环中运行
        asyncio.run(run_all_concurrent())
        
        global _test_running
        _test_running = False
    
    # 使用非守护线程以便可以强制停止
    thread = threading.Thread(target=run_test, daemon=False)
    thread.start()
    
    # 保存线程引用以便后续停止
    _test_thread = thread
    
    # 从数据库加载配置信息用于返回给前端
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    test_cases = []
    models_list = []
    
    if config_db_path.exists():
        try:
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取测试用例
            cursor.execute("""
                SELECT case_id, name, enabled FROM test_cases WHERE enabled = 1
            """)
            for row in cursor.fetchall():
                if case_ids and row["case_id"] not in case_ids:
                    continue
                test_cases.append({"id": row["case_id"], "name": row["name"]})
            
            # 获取模型
            cursor.execute("SELECT name, enabled FROM models WHERE enabled = 1")
            for row in cursor.fetchall():
                if model_names and row["name"] not in model_names:
                    continue
                models_list.append(row["name"])
            
            conn.close()
        except Exception as e:
            print(f"读取配置失败: {e}")
    
    # 如果没有从数据库获取到，回退到 JSON 配置
    if not test_cases:
        from main import load_config, get_enabled_test_cases
        json_config = load_config()
        if case_ids:
            for tc in json_config.get("test_cases", []):
                if tc.get("id") in case_ids:
                    test_cases.append({"id": tc.get("id"), "name": tc.get("name")})
        else:
            test_cases = [{"id": tc.get("id"), "name": tc.get("name")} for tc in get_enabled_test_cases(json_config)]
    
    if not models_list:
        json_config = load_config()
        enabled_models = [m["name"] for m in json_config.get("models", []) if m.get("enabled", True)]
        models_list = model_names if model_names else enabled_models
    
    # 从数据库读取并发配置
    conc_config = {"test_rounds": 10, "max_concurrent": 3, "interval": 1}
    if config_db_path.exists():
        try:
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_config WHERE key = 'concurrency'")
            row = cursor.fetchone()
            if row:
                conc_config = json.loads(row["value"])
            conn.close()
        except Exception as e:
            print(f"读取并发配置失败: {e}")
    
    # 优先使用前端传入的 test_rounds，否则使用数据库的值
    total_rounds = test_rounds if test_rounds is not None else conc_config.get("test_rounds", 10)
    
    # 返回测试配置信息，让前端可以立即创建任务卡片
    return {
        "status": "started",
        "config": {
            "models": models_list,
            "cases": [tc.get("name") for tc in test_cases],
            "total_rounds": total_rounds,
            "concurrency": concurrent,
            "client_count": len(models_list),
            "max_concurrent": max_concurrent,
            "interval": interval,
            "test_name": test_name
        }
    }


@app.post("/test/stop")
async def stop_test():
    """停止测试"""
    global _test_running
    
    # 触发停止事件
    stop_event = get_stop_event()
    if stop_event and not stop_event.is_set():
        stop_event.set()
        print("已发送停止信号...")
    
    # 强制停止测试线程
    stop_test_thread()
    
    # 获取当前的 group_id 并发送汇总事件
    try:
        # 从当前测试配置中获取 group_id
        if test_emitter._current_test:
            # 尝试从状态文件中获取 group_id
            import json
            from pathlib import Path
            state_file = test_emitter._get_state_file_path()
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    group_id = state.get('group_id')
                    if group_id:
                        # 手动更新数据库中的统计
                        from src.database import get_database
                        db = get_database()
                        # 获取实际完成的测试结果数量
                        results = test_emitter.get_results()
                        success_count = sum(1 for r in results if r.get("success", False))
                        failed_count = len(results) - success_count
                        completed_rounds = len(results)
                        
                        db.update_group(
                            group_id=group_id,
                            end_time=datetime.now().isoformat(),
                            status="stopped",
                            completed_rounds=completed_rounds,
                            success_count=success_count,
                            failed_count=failed_count
                        )
                        print(f"[Stop] 已更新测试组统计: {group_id}, 完成: {completed_rounds}, 成功: {success_count}")
    except Exception as e:
        print(f"[Stop] 更新统计失败: {e}")
    
    _test_running = False
    # 传入 False 保留状态文件，刷新页面后可以恢复任务进度
    test_emitter.reset(clear_state_file=False)
    return {"status": "stopped"}


@app.get("/test/status")
async def test_status():
    """获取测试状态"""
    global _test_running
    
    return {
        "running": _test_running,
        "pid": None
    }


# ===== 历史记录 API =====
@app.get("/api/history")
async def get_history(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    keyword: str = None,
    model_name: str = None
):
    """获取测试组历史列表"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        
        if keyword or model_name:
            groups = db.search_groups(
                keyword=keyword,
                model_name=model_name,
                limit=limit,
                offset=offset
            )
        else:
            groups = db.get_groups(
                limit=limit,
                offset=offset,
                status=status
            )
        
        # 获取总数
        total = db.get_group_count(status=status)
        
        # 解析 config_json
        for g in groups:
            if g.get("config_json"):
                try:
                    g["config"] = json.loads(g["config_json"])
                except:
                    pass
        
        return {
            "success": True,
            "data": groups,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/history/{group_id}")
async def get_history_detail(group_id: str):
    """获取测试组详情"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        summary = db.get_group_summary(group_id)
        
        if not summary:
            return {"success": False, "error": "测试组不存在"}
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/history/{group_id}/results")
async def get_history_results(group_id: str, model_name: str = None, test_case_name: str = None):
    """获取测试组的所有结果"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        
        if model_name:
            results = db.get_results_by_model(group_id, model_name, test_case_name)
        else:
            results = db.get_results(group_id)
        
        return {
            "success": True,
            "data": results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/history/{group_id}/summary")
async def get_history_summary(group_id: str):
    """获取测试组汇总统计"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        summary = db.get_group_summary(group_id)
        
        if not summary:
            return {"success": False, "error": "测试组不存在"}
        
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/history/{group_id}")
async def delete_history(group_id: str):
    """删除测试组"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        deleted = db.delete_group(group_id)
        
        return {
            "success": deleted,
            "message": "删除成功" if deleted else "删除失败"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.put("/api/history/{group_id}")
async def update_history(group_id: str, request: Request):
    """更新测试组信息（名称、状态等）"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        data = await request.json()
        name = data.get('name')
        status = data.get('status')
        
        db = get_database()
        
        # 更新名称
        if name:
            db.update_group_name(group_id, name)
        
        # 更新状态
        if status:
            db.update_group_status(group_id, status)
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/models")
async def get_models():
    """获取所有测试过的模型列表"""
    try:
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        
        db = get_database()
        
        # 从数据库中获取所有不同的模型名称
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT model_name FROM test_results ORDER BY model_name")
        models = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "data": models
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# 挂载前端静态文件
app.mount("/assets", StaticFiles(directory=str(Path(__file__).parent.parent / "frontend" / "dist" / "assets")), "assets")


def run_server(host: str = "0.0.0.0", port: int = 15010, log_level: str = "info"):
    """运行服务器"""
    import uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        reload=False
    )


def create_app() -> FastAPI:
    """创建并返回应用实例（用于编程式调用）"""
    return app


if __name__ == "__main__":
    run_server()

# ===== 报告生成 API =====

@app.get("/api/history/{group_id}/report/pdf")
async def generate_pdf_report(group_id: str, template: str = "default"):
    """生成 PDF 格式的测试报告，支持模板参数"""
    import io
    try:
        from .report_generator import ReportGenerator
        generator = ReportGenerator()
        pdf_bytes = generator.generate_pdf(group_id, template_name=template)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{group_id}.pdf"}
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/history/{group_id}/report/excel")
async def generate_excel_report(group_id: str):
    """生成 Excel 格式的测试报告"""
    import io
    try:
        from .excel_exporter import export_to_excel
        excel_buffer = export_to_excel(group_id)
        return StreamingResponse(
            io.BytesIO(excel_buffer),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=report_{group_id}.xlsx"}
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/report/templates")
async def list_report_templates():
    """列出所有可用的报告模板"""
    try:
        from .report_generator import ReportGenerator
        generator = ReportGenerator()
        templates = generator.list_templates()
        return {"success": True, "data": templates}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/history/{group_id}/report/markdown")
async def get_markdown_report(group_id: str, template: str = "default"):
    """获取 Markdown 格式的报告内容，支持模板参数"""
    import sys
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.database import get_database
        from .report_generator import ReportGenerator
        db = get_database()
        generator = ReportGenerator()
        summary_data = db.get_group_summary(group_id)
        if not summary_data:
            return {"success": False, "error": "测试组不存在"}
        group_info = summary_data.get('group', {})
        model_stats = summary_data.get('model_stats', [])
        results = db.get_results(group_id)
        total = len(results)
        success = sum(1 for r in results if r.get('success'))
        success_rate = (success / total * 100) if total > 0 else 0
        ttft_values = [r.get('ttft_seconds', 0) for r in results if r.get('ttft_seconds')]
        tps_values = [r.get('tokens_per_second', 0) for r in results if r.get('tokens_per_second')]
        token_values = [r.get('output_tokens', 0) for r in results if r.get('output_tokens')]
        avg_ttft = sum(ttft_values) / len(ttft_values) if ttft_values else 0
        avg_tps = sum(tps_values) / len(tps_values) if tps_values else 0
        avg_tokens = sum(token_values) / len(token_values) if token_values else 0
        summary = {'group_id': group_id, 'start_time': group_info.get('start_time', 'N/A'), 'total': total, 'success': success, 'avg_ttft': avg_ttft, 'avg_tps': avg_tps, 'avg_tokens': avg_tokens}
        formatted_stats = []
        for stat in model_stats:
            count = stat.get('total', 0)
            success_count = stat.get('success_count', 0)
            formatted_stats.append({'model_name': stat.get('model_name', 'Unknown'), 'count': count, 'success_count': success_count, 'avg_ttft': stat.get('avg_ttft', 0), 'avg_tps': stat.get('avg_tokens_per_second', 0), 'avg_tokens': stat.get('total_output_tokens', 0) / count if count > 0 else 0})
        content = generator.generate_markdown({"summary": summary, "results": results, "model_stats": formatted_stats}, template_name=template)
        return {"success": True, "content": content, "stats": {"total": total, "successRate": round(success_rate, 1), "avgTtft": round(avg_ttft * 1000, 2), "avgTps": round(avg_tps, 2)}}
    except Exception as e:
        return {"success": False, "error": str(e)}
