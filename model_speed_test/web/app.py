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
from typing import Optional, Dict
from functools import wraps
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .emitter import TestEventEmitter, test_emitter

# MiniMax M2.7 API 配置
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"

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


# ===== 统一错误处理 =====
import logging

logger = logging.getLogger("web.app")


class AppError(Exception):
    """业务错误：带 HTTP 状态码的可预期错误

    使用方式：raise AppError(404, "测试组不存在")
    服务端记录完整堆栈，客户端只收到通用文案。
    """
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


# 创建 FastAPI 应用
app = FastAPI(
    title="AI模型速度测试",
    description="实时可视化测试进度和流式输出",
    version="1.0.0"
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """业务错误：返回规范的 HTTP 状态码 + 通用文案"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
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


# ===== 文件夹管理辅助函数 =====
def _load_folders_tree(cursor):
    """从数据库加载文件夹树形结构"""
    cursor.execute("""
        SELECT folder_id, name, parent_id, sort_order
        FROM test_case_folders
        ORDER BY sort_order, name
    """)
    folders = []
    for row in cursor.fetchall():
        folders.append({
            "folder_id": row["folder_id"],
            "name": row["name"],
            "parent_id": row["parent_id"] or '',
            "sort_order": row["sort_order"]
        })
    return _build_folder_tree(folders)


def _build_folder_tree(flat_folders):
    """将扁平的文件夹列表构建为树形结构"""
    folder_map = {}
    roots = []
    for f in flat_folders:
        f["children"] = []
        folder_map[f["folder_id"]] = f
    for f in flat_folders:
        parent_id = f.get("parent_id", '')
        if parent_id and parent_id in folder_map:
            folder_map[parent_id]["children"].append(f)
        else:
            roots.append(f)
    return roots


def _collect_descendant_folder_ids(cursor, folder_id):
    """递归收集文件夹及其所有子文件夹的 ID"""
    ids = [folder_id]
    cursor.execute("""
        SELECT folder_id FROM test_case_folders WHERE parent_id = ?
    """, (folder_id,))
    for row in cursor.fetchall():
        ids.extend(_collect_descendant_folder_ids(cursor, row["folder_id"]))
    return ids


# ===== 配置管理 API =====

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
                SELECT id, name, provider, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled, extra_params
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                try:
                    extra_params = json.loads(row["extra_params"]) if row["extra_params"] else {}
                except (json.JSONDecodeError, TypeError):
                    extra_params = {}
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "provider": row["provider"] or "custom",
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True,
                    "extra_params": extra_params,
                })
            
            # 获取测试用例（含 folder_id）
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model, folder_id
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except (json.JSONDecodeError, TypeError):
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
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
                    "eval_model": row["eval_model"] or '',
                    "folder_id": row["folder_id"]
                })
            
            # 获取文件夹树形结构
            folders = _load_folders_tree(cursor)
            
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
                "folders": folders,
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
                INSERT INTO models (model_id, name, provider, endpoint, api_key, model, group_name, tags, metadata, enabled, status, health_check_enabled, health_check_result, created_at, updated_at, temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled, extra_params)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (model_id, name, provider, endpoint, api_key, model, "production", "[]", "{}", enabled, "active", 1, "{}", datetime.now().isoformat(), datetime.now().isoformat(), temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled, json.dumps(model_data.get("extra_params") or {})))

            conn.commit()

            # 返回更新后的所有模型列表（包含所有参数字段）
            cursor.execute("""
                SELECT id, name, provider, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled, extra_params
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                try:
                    extra_params = json.loads(row["extra_params"]) if row["extra_params"] else {}
                except (json.JSONDecodeError, TypeError):
                    extra_params = {}
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "provider": row["provider"] or "custom",
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True,
                    "extra_params": extra_params,
                })
            
            conn.close()
            return {"status": "success", "models": models}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
            if "extra_params" in model_data:
                updates.append("extra_params = ?")
                params.append(json.dumps(model_data["extra_params"] or {}))
            
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
                SELECT id, name, provider, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled, extra_params
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                try:
                    extra_params = json.loads(row["extra_params"]) if row["extra_params"] else {}
                except (json.JSONDecodeError, TypeError):
                    extra_params = {}
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "provider": row["provider"] or "custom",
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                    "enabled": bool(row["enabled"]),
                    "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
                    "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
                    "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
                    "presence_penalty": row["presence_penalty"] if row["presence_penalty"] is not None else 0.0,
                    "frequency_penalty": row["frequency_penalty"] if row["frequency_penalty"] is not None else 0.0,
                    "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True,
                    "extra_params": extra_params,
                })
            
            conn.close()
            return {"status": "success", "models": models}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
                SELECT id, name, provider, endpoint, api_key, model, enabled,
                       temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
                FROM models
            """)
            models = []
            for row in cursor.fetchall():
                models.append({
                    "id": row["id"],
                    "name": row["name"],
                    "provider": row["provider"] or "custom",
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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
                except Exception:
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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
            SELECT name, endpoint, api_key, model, provider, temperature, top_p, max_tokens, thinking_enabled
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
            "provider": row["provider"],
            "temperature": row["temperature"] if row["temperature"] is not None else 0.7,
            "top_p": row["top_p"] if row["top_p"] is not None else 1.0,
            "max_tokens": row["max_tokens"] if row["max_tokens"] is not None else 4096,
            "thinking_enabled": bool(row["thinking_enabled"]) if row["thinking_enabled"] is not None else True
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
                model=model_config["model"],
                temperature=model_config.get("temperature", 0.7),
                top_p=model_config.get("top_p", 1.0),
                max_tokens=model_config.get("max_tokens", 4096),
                thinking_enabled=model_config.get("thinking_enabled", True)
            )
            
            # 记录开始时间
            start_time = time.time()
            
            # 发送简单的测试请求
            try:
                result = await asyncio.wait_for(
                    client.chat(
                        prompt="你好！请回复一句问候语测试连接。",
                        max_tokens=100,
                        temperature=model_config.get("temperature", 0.7),
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
                except Exception:
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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
                # 从最后一条 user 消息提取文本内容作为 prompt（兼容多模态 list 形态）
                from src.providers.base import extract_text_for_log
                prompt = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        prompt = extract_text_for_log(msg.get("content", ""))
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
            
            # 处理 folder_id
            folder_id = test_case_data.get("folder_id", None)
            
            # 插入新测试用例
            cursor.execute("""
                INSERT INTO test_cases (case_id, name, type, description, max_tokens, temperature, stream, system_prompt, messages, metadata, enabled, expected_output, eval_model, folder_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (case_id, name, case_type, description, max_tokens, temperature, stream, system_prompt, messages_json, metadata_json, enabled, expected_output, eval_model, folder_id, datetime.now().isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            
            # 返回更新后的所有测试用例列表
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model, folder_id
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except (json.JSONDecodeError, TypeError):
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
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
                    "eval_model": row["eval_model"] or '',
                    "folder_id": row["folder_id"]
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.put("/config/test-cases/{test_case_id}/move")
async def move_test_case(test_case_id: str, move_data: dict):
    """移动测试用例到指定文件夹"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            folder_id = move_data.get("folder_id", None)  # None 表示移动到根目录
            
            # 如果指定了 folder_id，验证文件夹存在
            if folder_id:
                cursor.execute("SELECT folder_id FROM test_case_folders WHERE folder_id = ?", (folder_id,))
                if not cursor.fetchone():
                    conn.close()
                    return {"error": "目标文件夹不存在"}
            
            cursor.execute("""
                UPDATE test_cases 
                SET folder_id = ?, updated_at = datetime('now', 'localtime')
                WHERE case_id = ?
            """, (folder_id, test_case_id))
            
            conn.commit()
            
            if cursor.rowcount == 0:
                conn.close()
                return {"error": "测试用例不存在"}
            
            # 返回更新后的测试用例列表
            cursor.execute("""
                SELECT case_id, name, type, description, max_tokens, 
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model, folder_id
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except (json.JSONDecodeError, TypeError):
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
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
                    "eval_model": row["eval_model"] or '',
                    "folder_id": row["folder_id"]
                })
            
            # 获取文件夹树
            folders = _load_folders_tree(cursor)
            conn.close()
            
            return {"status": "success", "test_cases": test_cases, "folders": folders}
        else:
            return {"error": "config.db not found"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
            if "folder_id" in test_case_data:
                updates.append("folder_id = ?")
                params.append(test_case_data["folder_id"])
            
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
                       expected_output, eval_model, folder_id
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except (json.JSONDecodeError, TypeError):
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
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
                    "eval_model": row["eval_model"] or '',
                    "folder_id": row["folder_id"]
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


# ===== 测试用例文件夹管理 API =====

@app.get("/config/test-case-folders")
async def get_test_case_folders():
    """获取所有文件夹（树形结构）"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            folders = _load_folders_tree(cursor)
            conn.close()
            
            return {"status": "success", "folders": folders}
        else:
            return {"error": "config.db not found"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.post("/config/test-case-folders")
async def create_test_case_folder(folder_data: dict):
    """创建新文件夹"""
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
            
            folder_id = folder_data.get("folder_id", str(uuid.uuid4()))
            name = folder_data.get("name", "新文件夹")
            parent_id = folder_data.get("parent_id", None)
            sort_order = folder_data.get("sort_order", 0)
            
            # 如果指定了 parent_id，验证父文件夹存在
            if parent_id:
                cursor.execute("SELECT folder_id FROM test_case_folders WHERE folder_id = ?", (parent_id,))
                if not cursor.fetchone():
                    conn.close()
                    return {"error": "父文件夹不存在"}
            
            # 同级同名防重
            cursor.execute(
                "SELECT folder_id FROM test_case_folders WHERE name = ? AND COALESCE(parent_id, '') = COALESCE(?, '')",
                (name, parent_id)
            )
            if cursor.fetchone():
                conn.close()
                return {"error": "同级已存在同名文件夹"}
            
            cursor.execute("""
                INSERT INTO test_case_folders (folder_id, name, parent_id, sort_order)
                VALUES (?, ?, ?, ?)
            """, (folder_id, name, parent_id, sort_order))
            
            conn.commit()
            
            # 返回更新后的文件夹树
            folders = _load_folders_tree(cursor)
            conn.close()
            
            return {"status": "success", "folders": folders}
        else:
            return {"error": "config.db not found"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.put("/config/test-case-folders/{folder_id}")
async def update_test_case_folder(folder_id: str, folder_data: dict):
    """更新文件夹（重命名、移动）"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 检查文件夹是否存在
            cursor.execute("SELECT folder_id, parent_id FROM test_case_folders WHERE folder_id = ?", (folder_id,))
            existing = cursor.fetchone()
            if not existing:
                conn.close()
                return {"error": "文件夹不存在"}
            
            updates = []
            params = []
            
            if "name" in folder_data:
                updates.append("name = ?")
                params.append(folder_data["name"])
            
            if "parent_id" in folder_data:
                new_parent_id = folder_data["parent_id"]
                # 循环检测：向上递归查找
                if new_parent_id:
                    # 不允许设置为自身
                    if new_parent_id == folder_id:
                        conn.close()
                        return {"error": "不能将文件夹移动到自身"}
                    # 循环检测
                    check_id = new_parent_id
                    visited = set()
                    while check_id:
                        if check_id == folder_id or check_id in visited:
                            conn.close()
                            return {"error": "循环引用：不能将文件夹移动到其子文件夹中"}
                        visited.add(check_id)
                        cursor.execute("SELECT parent_id FROM test_case_folders WHERE folder_id = ?", (check_id,))
                        row = cursor.fetchone()
                        check_id = row["parent_id"] if row and row["parent_id"] else None
                
                updates.append("parent_id = ?")
                params.append(new_parent_id)
            
            if "sort_order" in folder_data:
                updates.append("sort_order = ?")
                params.append(folder_data["sort_order"])
            
            if updates:
                updates.append("updated_at = datetime('now', 'localtime')")
                params.append(folder_id)
                
                cursor.execute(f"""
                    UPDATE test_case_folders 
                    SET {', '.join(updates)}
                    WHERE folder_id = ?
                """, params)
                
                conn.commit()
            
            # 返回更新后的文件夹树
            folders = _load_folders_tree(cursor)
            conn.close()
            
            return {"status": "success", "folders": folders}
        else:
            return {"error": "config.db not found"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.delete("/config/test-case-folders/{folder_id}")
async def delete_test_case_folder(folder_id: str):
    """删除文件夹（级联删除子文件夹，用例回退 NULL）"""
    import json
    from pathlib import Path
    import sqlite3
    
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    
    try:
        if config_db_path.exists():
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 检查文件夹是否存在
            cursor.execute("SELECT folder_id FROM test_case_folders WHERE folder_id = ?", (folder_id,))
            if not cursor.fetchone():
                conn.close()
                return {"error": "文件夹不存在"}
            
            # 递归收集所有子文件夹 ID
            all_ids = _collect_descendant_folder_ids(cursor, folder_id)
            
            # 将所有受影响文件夹下的 test_cases 的 folder_id 置为 NULL
            placeholders = ','.join(['?' for _ in all_ids])
            cursor.execute(f"""
                UPDATE test_cases 
                SET folder_id = NULL, updated_at = datetime('now', 'localtime')
                WHERE folder_id IN ({placeholders})
            """, all_ids)
            
            # 删除所有子文件夹记录（父文件夹由 CASCADE 处理）
            for fid in all_ids:
                cursor.execute("DELETE FROM test_case_folders WHERE folder_id = ?", (fid,))
            
            conn.commit()
            
            # 返回更新后的文件夹树
            folders = _load_folders_tree(cursor)
            conn.close()
            
            return {"status": "success", "folders": folders}
        else:
            return {"error": "config.db not found"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
                       temperature, stream, system_prompt, messages, metadata, enabled,
                       expected_output, eval_model, folder_id
                FROM test_cases
            """)
            test_cases = []
            for row in cursor.fetchall():
                messages = row["messages"]
                if messages:
                    try:
                        messages = json.loads(messages)
                    except (json.JSONDecodeError, TypeError):
                        messages = []
                else:
                    messages = []
                
                metadata = row["metadata"]
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
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
                    "eval_model": row["eval_model"] or '',
                    "folder_id": row["folder_id"]
                })
            
            conn.close()
            return {"status": "success", "test_cases": test_cases}
        else:
            raise Exception("config.db not found")
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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


def stop_test_thread(timeout: float = 15.0):
    """协作式停止测试线程：先发停止信号，再等待线程自行退出

    不再使用 ctypes 强杀（SystemExit 会在任意字节码边界注入，
    跳过清理逻辑导致 _test_running 永久卡 True）。测试线程内部
    通过 stop_event + should_stop() 检查实现协作取消。
    """
    global _test_thread
    
    if _test_thread and _test_thread.is_alive():
        print(f"[Stop] 等待测试线程 {_test_thread.ident} 退出 (超时 {timeout}s)...")
        _test_thread.join(timeout=timeout)
        if _test_thread.is_alive():
            print(f"[Stop] 警告: 测试线程 {_test_thread.ident} 在 {timeout}s 内未退出（可能阻塞在网络请求），等待其自行完成")
        else:
            print("[Stop] 测试线程已退出")
    
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

def _find_analysis_model_config(model_name: str) -> dict:
    """查找 AI 分析模型的配置（独立函数，供 ai_analysis 调用）

    Returns:
        模型配置 dict；找不到时返回 None（调用方决定兜底策略）
    """
    import sqlite3
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"

    if model_name:
        try:
            conn = sqlite3.connect(str(config_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, provider, endpoint, api_key, model FROM models WHERE name = ?",
                (model_name,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "name": row["name"],
                    "provider": row["provider"] or "openai",
                    "endpoint": row["endpoint"],
                    "api_key": row["api_key"],
                    "model": row["model"],
                }
        except Exception:
            pass  # 查找失败则回退到默认
    return None


@app.get("/api/analysis")
async def ai_analysis(request: Request):
    """
    AI 分析端点 — 使用指定模型流式分析当前页面所有测评任务数据
    SSE 流式返回 Markdown 分析报告
    支持参数:
      - group_id: 可选,指定分析哪个测试组的历史数据,不传则使用 emitter 内存中的最新数据
      - use_db: 可选,是否从数据库获取历史数据 (true/false), 默认 false
      - model_name: 可选,指定用哪个模型来执行分析,不传则使用 MiniMax-M2.7 兜底
    """
    group_id = request.query_params.get("group_id")
    use_db = request.query_params.get("use_db", "false").lower() == "true"
    model_name = request.query_params.get("model_name", "").strip()
    
    # 先重新加载状态
    test_emitter.reload_state()
    
    # --- 查找分析模型的配置（已提取为独立函数）---
    ai_model_config = _find_analysis_model_config(model_name)
    if not ai_model_config:
        minimax_key = os.environ.get("MINIMAX_API_KEY", "")
        if minimax_key:
            model_name = "MiniMax-M2.7"
            ai_model_config = {
                "name": "MiniMax-M2.7",
                "provider": "minimax",
                "endpoint": "https://api.minimaxi.com/v1/text/chatcompletion_v2",
                "api_key": minimax_key,
                "model": "MiniMax-M2.7",
            }
        else:
            raise AppError(400, "未找到可用的分析模型（请指定 model_name 或配置 MINIMAX_API_KEY）")

    async def event_generator():
        try:
            # Step 1: 收集所有测评任务数据
            yield f"data: {json.dumps({'type': 'status', 'status': 'collecting', 'message': '正在收集测评任务数据...'})}\n\n"
            await asyncio.sleep(0.1)
            
            tasks_data = []
            
            if use_db and group_id:
                # 从数据库获取指定组的数据
                yield f"data: {json.dumps({'type': 'status', 'status': 'collecting', 'message': '正在从数据库读取测试结果...'})}\n\n"
                try:
                    results = test_emitter._db.get_results(group_id)
                    # 按模型和测试用例分组
                    grouped = {}
                    for r in results:
                        key = f"{r.get('model_name','')}__{r.get('test_case_name','')}"
                        if key not in grouped:
                            grouped[key] = {
                                "model_name": r.get("model_name", "unknown"),
                                "test_case_name": r.get("test_case_name", "unknown"),
                                "rounds": {}
                            }
                        round_num = str(r.get("round_number", 0))
                        grouped[key]["rounds"][round_num] = {
                            "status": "done" if r.get("success") else "error",
                            "metrics": r.get("metrics", {}),
                            "evaluation": r.get("evaluation", None),
                            "output": r.get("response", "")[:500]  # 只取前500字符摘要
                        }
                    tasks_data = list(grouped.values())
                    
                    # 也获取 group 信息
                    group_info = test_emitter._db.get_group(group_id)
                    if group_info:
                        yield f"data: {json.dumps({'type': 'meta', 'group_id': group_id, 'models': group_info.get('models',[]), 'test_cases': group_info.get('test_cases',[]), 'total_rounds': group_info.get('total_rounds',0), 'completed_rounds': group_info.get('completed_rounds', 0)})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'数据库查询失败: {str(e)}'})}\n\n"
                    return
            
            # 同时从 emitter 内存中获取最新数据
            if not tasks_data:
                # 使用 emitter 内存中的 tasks
                for task_id, task in test_emitter._tasks.items():
                    tasks_data.append(task)
            
            if not tasks_data:
                yield f"data: {json.dumps({'type': 'error', 'message': '没有可分析的测评任务数据,请先运行测试'})}\n\n"
                return
            
            task_count = len(tasks_data)
            round_count = sum(len(t.get("rounds", {})) for t in tasks_data)
            yield f"data: {json.dumps({'type': 'status', 'status': 'collected', 'message': f'已收集 {task_count} 个任务的数据,共 {round_count} 轮测试'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Step 2: 构建分析提示词
            yield f"data: {json.dumps({'type': 'status', 'status': 'analyzing', 'message': '正在构建分析提示词...'})}\n\n"
            
            # 构建结构化的系统提示词
            prompt_data = []
            for task in tasks_data:
                task_info = {
                    "模型名称": task.get("model_name", "unknown"),
                    "测试用例": task.get("test_case_name", "unknown"),
                    "总轮数": task.get("total_rounds", 0),
                    "各轮详情": []
                }
                
                rounds = task.get("rounds", {})
                success_count = 0
                total_valid = 0
                all_metrics = []
                
                for round_num in sorted(rounds.keys(), key=int):
                    round_data = rounds[round_num]
                    status = round_data.get("status", "unknown")
                    if status in ("done", "error"):
                        total_valid += 1
                        if status == "done":
                            success_count += 1
                    
                    metrics = round_data.get("metrics", {}) or {}
                    round_detail = {
                        "轮次": int(round_num),
                        "状态": "成功" if status == "done" else ("失败" if status == "error" else "未运行"),
                        "TTFT(首Token时间s)": metrics.get('ttft_seconds', metrics.get('ttft', '-')),
                        "TPFT(生成时间s)": metrics.get('tpft_seconds', metrics.get('tpft', '-')),
                        "总耗时s": metrics.get('total_time_seconds', metrics.get('total_time_ms', metrics.get('total_duration', '-'))),
                        "输出Token数": metrics.get('output_tokens', '-'),
                        "输入Token数": metrics.get('input_tokens', '-'),
                        "输出速度(tokens/s)": metrics.get('tokens_per_second', metrics.get('avg_tps', '-')),
                        "总时间效率(tokens/s)": metrics.get('total_tokens_per_second', '-'),
                    }
                    
                    # 添加评估结果(如果有)
                    evaluation = round_data.get("evaluation")
                    if evaluation:
                        round_detail["评估结果"] = str(evaluation)[:200]
                    
                    task_info["各轮详情"].append(round_detail)
                    
                    if metrics:
                        all_metrics.append(metrics)
                
                task_info["成功率"] = f"{success_count}/{total_valid}" if total_valid > 0 else "N/A"
                
                # 汇总统计
                if all_metrics:
                    def _num(val, default=0):
                        return val if isinstance(val, (int, float)) else default

                    ttfts = [_num(m.get('ttft_seconds') or m.get('ttft')) for m in all_metrics if _num(m.get('ttft_seconds') or m.get('ttft'))]
                    tps_list = [_num(m.get('tokens_per_second') or m.get('avg_tps')) for m in all_metrics if _num(m.get('tokens_per_second') or m.get('avg_tps'))]
                    total_time_vals = [_num(m.get('total_time_seconds') or m.get('total_time_ms') or m.get('total_duration')) for m in all_metrics if _num(m.get('total_time_seconds') or m.get('total_time_ms') or m.get('total_duration'))]
                    output_tokens_list = [_num(m.get('output_tokens')) for m in all_metrics if _num(m.get('output_tokens'))]
                    total_tps_list = [_num(m.get('total_tokens_per_second')) for m in all_metrics if _num(m.get('total_tokens_per_second'))]
                    
                    if ttfts:
                        task_info["TTFT统计"] = f"平均: {sum(ttfts)/len(ttfts):.3f}s, 最快: {min(ttfts):.3f}s, 最慢: {max(ttfts):.3f}s"
                    if tps_list:
                        task_info["TPS统计"] = f"平均: {sum(tps_list)/len(tps_list):.1f} t/s, 最快: {max(tps_list):.1f} t/s, 最慢: {min(tps_list):.1f} t/s"
                    if total_time_vals:
                        task_info["总耗时统计"] = f"平均: {sum(total_time_vals)/len(total_time_vals):.3f}s, 最短: {min(total_time_vals):.3f}s, 最长: {max(total_time_vals):.3f}s"
                    if output_tokens_list:
                        task_info["输出Token统计"] = f"平均: {sum(output_tokens_list)/len(output_tokens_list):.0f} tokens/轮, 最少: {min(output_tokens_list)}, 最多: {max(output_tokens_list)}"
                    if total_tps_list:
                        task_info["总时间效率统计"] = f"平均: {sum(total_tps_list)/len(total_tps_list):.1f} t/s (基于总耗时,含首Token等待)"
                    
                    # 关键效率指标：纯生成速度(排除首Token等待)
                    tpft_token_pairs = [(m.get('tpft_seconds', m.get('tpft', 0)), m.get('output_tokens', 0)) for m in all_metrics if m.get('output_tokens', 0)]
                    if tpft_token_pairs:
                        gen_eff = [tokens / tpft for tpft, tokens in tpft_token_pairs if tpft and tpft > 0]
                        if gen_eff:
                            task_info["纯生成效率(排除首Token)"] = f"平均: {sum(gen_eff)/len(gen_eff):.1f} t/s"
                    
                    # 任务完成效率：总耗时 vs 输出量
                    # 正确理念：在成功完成同一任务的前提下，总耗时越短越好，输出 Token 越少越好
                    # 因此传递原始数据（总耗时 + 输出Token），由 AI 综合判断，而非简单做除法
                    time_token_pairs = [(m.get('total_time_seconds', m.get('total_time_ms', m.get('total_duration', 0))), m.get('output_tokens', 0)) for m in all_metrics if m.get('output_tokens', 0)]
                    if time_token_pairs:
                        total_times = [total_t for total_t, _ in time_token_pairs if total_t and total_t > 0]
                        output_tokens_list = [tokens for _, tokens in time_token_pairs if tokens > 0]
                        if total_times:
                            task_info["平均总耗时"] = f"平均: {sum(total_times)/len(total_times):.3f}s, 最短: {min(total_times):.3f}s, 最长: {max(total_times):.3f}s"
                        if output_tokens_list:
                            task_info["平均输出Token"] = f"平均: {sum(output_tokens_list)/len(output_tokens_list):.0f} tokens/轮, 最少: {min(output_tokens_list)}, 最多: {max(output_tokens_list)}"
                        # 综合效率评分：总耗时越短 + Token越少 → 综合效率越高
                        # 使用归一化后的反比指标：1/(归一化总耗时 * 归一化Token数)
                        if total_times and output_tokens_list:
                            avg_time = sum(total_times) / len(total_times)
                            avg_tokens = sum(output_tokens_list) / len(output_tokens_list)
                            task_info["综合效率指标说明"] = "在成功完成同一任务的前提下，总耗时越短且输出Token越少 = 任务完成效率越高。请综合这两个维度判断，不要仅凭 tokens/s 做判断。"
                
                prompt_data.append(task_info)
            
            # 序列化为JSON供分析
            data_json = json.dumps(prompt_data, ensure_ascii=False, indent=2)
            
            # 构建分析 system prompt
            system_prompt = """你是一位专业的 AI 模型性能分析师。请基于提供的测评任务数据,生成一份详细的中文Markdown分析报告。

## 核心分析理念：任务完成效率 = 总耗时越短 + Token越少 = 越好
- **任务完成效率的正确定义**：在确保任务成功完成的前提下，总耗时（total_time_seconds）越短、输出 Token 数越少，任务完成效率越高。
- **重要：token/s 速度高 ≠ 效率高！** 一个模型可能每秒输出很多 token（tokens/s 高），但如果它废话连篇、输出大量无用 token，同样任务的总耗时反而更长——这不是好模型。
- **评价一个模型是否高效，必须同时看两个维度**：
  * 总耗时（total_time_seconds）：从发起请求到收到完整回复的总时间，这是用户体感最直接的指标，越短越好
  * 输出 Token 数：完成同一任务所消耗的 Token，越少说明模型越精炼、回答越简洁高效（前提是成功完成任务）
  * 综合判断规则：总耗时越短 且 输出Token越少 → 任务完成效率越高（两者缺一不可）
  * 如果一个模型总耗时短但 Token 很少 → 非常高效（又快又精炼）
  * 如果一个模型总耗时短但 Token 很多 → 虽然快但可能废话多（效率一般）
  * 如果一个模型总耗时长但 Token 很少 → 生成速度慢但回答精炼（效率较低）
  * 如果一个模型总耗时长且 Token 也很多 → 效率最低
- **其他辅助指标**：
  * 纯生成效率(排除首Token) = 输出Token数 / TPFT——衡量模型"想清楚后"的纯生成速度
  * 首Token时间(TTFT)：用户感知的"首次响应"速度，越低越好
  * 成功率：任务是否成功完成（未完成的模型不应参与效率排名）

## 报告结构要求:

### 1. 执行摘要
- 概括本次测试的整体情况
- **用 ⭐ 标记任务完成效率最高的模型（综合考虑总耗时最短 + 输出Token最精炼）**
- 一句话总结各模型的综合表现排名

### 2. 各模型详细分析
针对每个模型:
- **综合得分与排名**: 综合成功率、总耗时、输出精炼度（Token越少越好）进行评分
- **任务完成效率分析**(重点!):
  - 列出平均总耗时和平均输出Token数
  - 综合判断：总耗时越短 + Token越少 → 效率越高
  - 如果总耗时最短且输出Token也最少 → ✅ 最佳效率模型
  - 如果总耗时短但输出Token偏多 → ⚠️ 速度快但不够精炼（有"废话多"嫌疑）
  - 如果总耗时长但输出Token少 → ⚠️ 回答精炼但生成速度慢
  - 如果总耗时长且输出Token多 → ❌ 效率低下
- **速度快照**: TTFT(首Token)、TPFT(生成阶段)、纯生成效率
- **稳定性分析**: 成功率、速度波动情况（最大值/最小值差异）
- **评估结果**: 如果有评估数据,分析回复质量
- **优势与不足**: 特别指出"废话多但快"或"比较慢但言简意赅"等特征

### 3. 对比分析
- 所有模型的任务完成效率对比表（**总耗时、输出Token数两列并列展示**，不要合并为单一 t/s 数值）
- 不同测试用例下的表现差异
- 给出「最佳效率模型」（总耗时短 + Token少）和「最快输出模型」（tokens/s最高）的明确区分

### 4. 选型建议
- 如果追求"用户体感最好的响应速度"→ 推荐总耗时最短的模型
- 如果追求"性价比(按Token计费)"→ 推荐输出精炼度高（输出Token最少）的模型
- 如果追求"又快又省的综合效率"→ 推荐总耗时短且输出Token少的模型
- 如果追求"首Token响应快"→ 推荐TTFT最低的模型
- 不同场景下的最佳选择

### 5. 结论
- 用一句话总结:哪个模型在「又快又好地完成任务」上表现最佳
- 最终推荐和理由

## 格式要求:
- 使用标准 Markdown 格式
- 关键数据用 **加粗** 标记
- 使用表格进行数据对比（对比表必须同时展示总耗时和输出Token两列）
- 使用 ✅ ⚠️ ❌ 标记表现好坏
- 使用 ⭐ 标记最佳表现
- 语言:中文
- 报告末尾加上: *--- AI 分析报告由 MiniMax M2.7 生成 ---*"""

            user_message = f"请分析以下模型速度测评数据:\n\n```json\n{data_json}\n```\n\n请按照要求生成完整的Markdown格式分析报告。"
            
            if not ai_model_config:
                yield f"data: {json.dumps({'type': 'error', 'message': '未找到可用的分析模型配置，请确保 MINIMAX_API_KEY 环境变量已设置或选择了一个已配置的模型'})}\n\n"
                return
            
            model_display_name = ai_model_config.get("name", "Unknown")
            yield f"data: {json.dumps({'type': 'status', 'status': 'calling', 'message': f'正在调用 {model_display_name} 进行分析...'})}\n\n"
            
            # Step 3: 使用选定的模型进行流式生成（OpenAI 兼容 API）
            import aiohttp
            
            analysis_endpoint = ai_model_config.get("endpoint", "")
            analysis_api_key = ai_model_config.get("api_key", "")
            analysis_model = ai_model_config.get("model", "")
            
            if not analysis_api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': f'模型 {model_display_name} 未配置 API Key'})}\n\n"
                return
            if not analysis_endpoint:
                yield f"data: {json.dumps({'type': 'error', 'message': f'模型 {model_display_name} 未配置 Endpoint'})}\n\n"
                return
            
            payload = {
                "model": analysis_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 16384
            }
            
            headers = {
                "Authorization": f"Bearer {analysis_api_key}",
                "Content-Type": "application/json"
            }
            
            full_text = ""
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        analysis_endpoint,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=300)
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            yield f"data: {json.dumps({'type': 'error', 'message': f'API 返回错误 (HTTP {resp.status}): {error_text[:500]}'})}\n\n"
                            return
                        
                        buffer = ""
                        async for chunk in resp.content:
                            if chunk:
                                buffer += chunk.decode('utf-8', errors='replace')
                                while '\n' in buffer:
                                    line, buffer = buffer.split('\n', 1)
                                    line = line.strip()
                                    if line.startswith('data: '):
                                        data_str = line[6:]
                                        if data_str == '[DONE]':
                                            break
                                        try:
                                            data = json.loads(data_str)
                                            choices = data.get('choices', [])
                                            if choices:
                                                delta = choices[0].get('delta', {})
                                                content = delta.get('content', '')
                                                if content:
                                                    full_text += content
                                                    yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
                                        except json.JSONDecodeError:
                                            pass
                
                # 发送完成信号
                yield f"data: {json.dumps({'type': 'done', 'full_text': full_text})}\n\n"
                
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'API 请求超时 (300秒)'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'调用 {model_display_name} API 失败: {str(e)}'})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'分析过程异常: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/test/start")
async def start_test(request: Request):
    """启动测试"""
    global _test_running, _test_task, _test_thread

    if _test_running:
        return {"error": "测试已在运行中"}
    
    try:
        body = await request.json()
    except Exception:
        body = {}  # invalid json body tolerated
    
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
                
                # 读取启用的测试用例（包含 folder_id）
                cursor.execute("""
                    SELECT case_id, name, type, description, max_tokens, 
                           temperature, stream, system_prompt, messages, metadata, enabled,
                           expected_output, eval_model, folder_id 
                    FROM test_cases WHERE enabled = 1
                """)
                
                for row in cursor.fetchall():
                    messages = row["messages"]
                    if messages:
                        try:
                            messages = json.loads(messages)
                        except (json.JSONDecodeError, TypeError):
                            messages = []
                    else:
                        messages = []
                    
                    metadata = row["metadata"]
                    if metadata:
                        try:
                            metadata = json.loads(metadata)
                        except (json.JSONDecodeError, TypeError):
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
                        "eval_model": row["eval_model"] or '',
                        "folder_id": row["folder_id"]
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
        
        # 构建 case_name → folder 映射，传递给 emitter 用于持久化
        case_folder_map: Dict[str, Dict[str, str]] = {}
        folder_name_cache: Dict[str, str] = {}  # folder_id → folder_name
        if config_db_path.exists():
            try:
                conn = sqlite3.connect(str(config_db_path))
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # 一次性读取所有文件夹
                cursor.execute("SELECT folder_id, name FROM test_case_folders")
                for row in cursor.fetchall():
                    folder_name_cache[row["folder_id"]] = row["name"]
                conn.close()
            except Exception as e:
                pass
        
        for tc in test_cases:
            tc_name = tc.get("name", "")
            tc_folder_id = tc.get("folder_id", "")
            if tc_name and tc_folder_id and tc_folder_id in folder_name_cache:
                case_folder_map[tc_name] = {
                    "folder_id": tc_folder_id,
                    "folder_name": folder_name_cache[tc_folder_id]
                }
        
        test_emitter.set_case_folder_map(case_folder_map)
        
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

            # 跨模型共享并发信号量：所有模型的在途请求总数受 max_concurrent 约束
            max_conc = int((config.get("concurrency", {}) or {}).get("max_concurrent", 3) or 3)
            shared_semaphore = asyncio.Semaphore(max(1, max_conc))

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
                        stop_event=stop_event,
                        case_semaphore=shared_semaphore
                    )
                )
                tasks.append(task)
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # 在新的事件循环中运行
        asyncio.run(run_all_concurrent())
    
    # 包装函数：确保无论 run_test 正常结束还是抛异常，_test_running 都复位，
    # 避免服务永久卡在"测试已在运行中"（协作式停止的配套保障）
    def run_test_safe():
        global _test_running
        try:
            run_test()
        except Exception as e:
            print(f"[Test] 测试线程异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _test_running = False
    
    # 使用 daemon 线程（不阻塞进程退出）；停止依赖协作式 stop_event，不强杀
    thread = threading.Thread(target=run_test_safe, daemon=True)
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
    """停止测试（协作式取消）"""
    global _test_running
    
    # 触发停止事件（测试线程内 should_stop() 会响应并退出）
    stop_event = get_stop_event()
    if stop_event and not stop_event.is_set():
        stop_event.set()
        print("已发送停止信号...")
    
    # 等待测试线程退出（协作式，不再强杀；_test_running 由 run_test 的 finally 复位）
    stop_test_thread(timeout=15.0)
    
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
    
    # 兜底：正常情况下 _test_running 由 run_test 的 finally 复位。
    # 若线程已退出但标志未复位（极少数异常路径），这里强制复位，
    # 避免服务永久卡在"测试已在运行中"。
    global _test_thread
    if _test_running and (_test_thread is None or not _test_thread.is_alive()):
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
                except Exception:
                    pass
        
        return {
            "success": True,
            "data": groups,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {str(e)}"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {str(e)}"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.get("/api/report/templates")
async def list_report_templates():
    """列出所有可用的报告模板"""
    try:
        from .report_generator import ReportGenerator
        generator = ReportGenerator()
        templates = generator.list_templates()
        return {"success": True, "data": templates}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


@app.get("/api/history/{group_id}/report/all")
async def export_all_reports(group_id: str, template: str = "default"):
    """一键导出全部报告：PDF + Markdown + Excel，打包为 ZIP"""
    import io
    import sys
    import zipfile
    try:
        from .report_generator import ReportGenerator
        from .excel_exporter import export_to_excel
        
        generator = ReportGenerator()
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. PDF 报告
            try:
                pdf_bytes = generator.generate_pdf(group_id, template_name=template)
                zf.writestr(f"report_{group_id}.pdf", pdf_bytes)
            except Exception as pdf_err:
                zf.writestr(f"report_{group_id}_pdf_error.txt", f"PDF 生成失败: {pdf_err}")
            
            # 2. Markdown 报告
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from src.database import get_database
                db = get_database()
                summary_data = db.get_group_summary(group_id)
                if summary_data:
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
                    md_content = generator.generate_markdown({"summary": summary, "results": results, "model_stats": formatted_stats}, template_name=template)
                    zf.writestr(f"report_{group_id}.md", md_content.encode('utf-8'))
                else:
                    zf.writestr(f"report_{group_id}_md_error.txt", "测试组不存在")
            except Exception as md_err:
                zf.writestr(f"report_{group_id}_md_error.txt", f"Markdown 生成失败: {md_err}")
            
            # 3. Excel 报告
            try:
                excel_bytes = export_to_excel(group_id)
                zf.writestr(f"report_{group_id}.xlsx", excel_bytes)
            except Exception as xl_err:
                zf.writestr(f"report_{group_id}_xlsx_error.txt", f"Excel 生成失败: {xl_err}")
        
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=report_{group_id}_all.zip"}
        )
    except ImportError as e:
        return {"success": False, "error": f"依赖未安装: {str(e)}"}
    except Exception as e:
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


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
        logger.exception("[App] request failed")
        raise AppError(500, "internal error, see server log")


# ===== Webhook 配置端点（SDK 兼容） =====
WEBHOOK_CONFIG_KEY = "webhook_config"


def _load_webhook_config() -> dict:
    """从 system_config 表读取 webhook 配置"""
    import sqlite3
    from pathlib import Path
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    if not config_db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(config_db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (WEBHOOK_CONFIG_KEY,))
        row = cursor.fetchone()
        conn.close()
        if row and row["value"]:
            return json.loads(row["value"])
    except Exception as e:
        print(f"[Webhook] 读取配置失败: {e}")
    return {}


def _save_webhook_config(config: dict) -> bool:
    """保存 webhook 配置到 system_config 表"""
    import sqlite3
    from pathlib import Path
    config_db_path = Path(__file__).parent.parent / "results" / "config.db"
    if not config_db_path.exists():
        return False
    try:
        conn = sqlite3.connect(str(config_db_path))
        cursor = conn.cursor()
        value = json.dumps(config, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO system_config (key, value, updated_at)
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (WEBHOOK_CONFIG_KEY, value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Webhook] 保存配置失败: {e}")
        return False


@app.get("/api/webhook/config")
async def get_webhook_config():
    """获取 Webhook 配置"""
    config = _load_webhook_config()
    return {"success": True, "config": config}


@app.post("/api/webhook/config")
async def configure_webhook(data: dict):
    """配置 Webhook（SDK: configure_webhook）"""
    url = data.get("url", "")
    if not url:
        return {"success": False, "error": "webhook URL 不能为空"}
    if not url.startswith(("http://", "https://")):
        return {"success": False, "error": "webhook URL 必须以 http:// 或 https:// 开头"}
    
    config = _load_webhook_config()
    config["url"] = url
    config["events"] = data.get("events") or ["test_complete"]
    config["enabled"] = bool(data.get("enabled", True))
    if data.get("secret"):
        config["secret"] = data["secret"]
    
    if _save_webhook_config(config):
        return {"success": True, "config": config}
    return {"success": False, "error": "保存失败（config.db 不可写）"}


@app.delete("/api/webhook/config")
async def delete_webhook_config():
    """删除 Webhook 配置"""
    if _save_webhook_config({}):
        return {"success": True}
    return {"success": False, "error": "删除失败（config.db 不可写）"}
