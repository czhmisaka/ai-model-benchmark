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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
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
    """获取当前配置"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    return {"error": "配置文件不存在"}


@app.post("/config/models")
async def add_model(model_data: dict):
    """添加模型"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 添加新模型
        if "models" not in config:
            config["models"] = []
        
        # 检查是否已存在
        for m in config["models"]:
            if m.get("name") == model_data.get("name"):
                return {"error": "模型已存在"}
        
        config["models"].append(model_data)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "models": config["models"]}
    
    return {"error": "配置文件不存在"}


@app.put("/config/models/{model_name}")
async def update_model(model_name: str, model_data: dict):
    """更新模型"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 查找并更新模型
        found = False
        for m in config.get("models", []):
            if m.get("name") == model_name:
                # 更新模型信息（保留原名称）
                m["endpoint"] = model_data.get("endpoint", m.get("endpoint", ""))
                m["api_key"] = model_data.get("api_key", m.get("api_key", ""))
                m["model"] = model_data.get("model", m.get("model", ""))
                m["enabled"] = model_data.get("enabled", m.get("enabled", True))
                found = True
                break
        
        if not found:
            return {"error": "模型不存在"}
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "models": config["models"]}
    
    return {"error": "配置文件不存在"}


@app.delete("/config/models/{model_name}")
async def delete_model(model_name: str):
    """删除模型"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 删除模型
        config["models"] = [m for m in config.get("models", []) if m.get("name") != model_name]
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "models": config["models"]}
    
    return {"error": "配置文件不存在"}


@app.post("/config/test-cases")
async def add_test_case(test_case_data: dict):
    """添加测试用例"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 添加新测试用例
        if "test_cases" not in config:
            config["test_cases"] = []
        
        # 生成 ID
        import time
        test_case_data["id"] = test_case_data.get("id", f"tc_{int(time.time())}")
        test_case_data["enabled"] = True
        
        # 支持 messages 数组格式
        # 如果有 messages，将其转换为 prompt 兼容旧系统
        if "messages" in test_case_data and isinstance(test_case_data["messages"], list):
            # 从最后一条 user 消息提取内容作为 prompt
            for msg in reversed(test_case_data["messages"]):
                if msg.get("role") == "user":
                    test_case_data["prompt"] = msg.get("content", "")
                    break
        
        config["test_cases"].append(test_case_data)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "test_cases": config["test_cases"]}
    
    return {"error": "配置文件不存在"}


@app.put("/config/test-cases/{test_case_id}")
async def update_test_case(test_case_id: str, test_case_data: dict):
    """更新测试用例"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 查找并更新测试用例
        found = False
        for tc in config.get("test_cases", []):
            if tc.get("id") == test_case_id:
                # 更新测试用例信息（保留原ID）
                tc["name"] = test_case_data.get("name", tc.get("name", ""))
                # 支持 messages 数组格式
                if "messages" in test_case_data:
                    tc["messages"] = test_case_data["messages"]
                    # 同时更新 prompt 字段以兼容旧系统
                    # 从最后一条 user 消息提取内容作为 prompt
                    for msg in reversed(test_case_data["messages"]):
                        if msg.get("role") == "user":
                            tc["prompt"] = msg.get("content", "")
                            break
                else:
                    tc["prompt"] = test_case_data.get("prompt", tc.get("prompt", ""))
                tc["max_tokens"] = test_case_data.get("max_tokens", tc.get("max_tokens", 500))
                tc["temperature"] = test_case_data.get("temperature", tc.get("temperature", 0.7))
                tc["stream"] = test_case_data.get("stream", tc.get("stream", True))
                found = True
                break
        
        if not found:
            return {"error": "测试用例不存在"}
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "test_cases": config["test_cases"]}
    
    return {"error": "配置文件不存在"}


@app.delete("/config/test-cases/{test_case_id}")
async def delete_test_case(test_case_id: str):
    """删除测试用例"""
    import json
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 删除测试用例
        config["test_cases"] = [tc for tc in config.get("test_cases", []) if tc.get("id") != test_case_id]
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "test_cases": config["test_cases"]}
    
    return {"error": "配置文件不存在"}


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
    
    def run_test():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # 动态导入并运行
        from main import create_clients, get_enabled_test_cases, load_config
        from concurrent.futures import ThreadPoolExecutor
        
        config = load_config()
        
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
        test_cases = []
        if case_ids:
            for tc in config.get("test_cases", []):
                if tc.get("id") in case_ids:
                    test_cases.append(tc)
        else:
            test_cases = get_enabled_test_cases(config)
        
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
    
    # 从线程外部加载配置（因为 run_test 内部的 import 可能还没执行完）
    from main import load_config, get_enabled_test_cases
    config = load_config()
    test_cases = []
    if case_ids:
        for tc in config.get("test_cases", []):
            if tc.get("id") in case_ids:
                test_cases.append(tc)
    else:
        test_cases = get_enabled_test_cases(config)
    
    conc_config = config.get("concurrency", {})
    # 优先使用前端传入的 test_rounds，否则使用配置文件的值
    total_rounds = test_rounds if test_rounds is not None else conc_config.get("test_rounds", 10)
    
    # 获取实际要测试的模型列表
    enabled_models = [m["name"] for m in config.get("models", []) if m.get("enabled", True)]
    actual_models = model_names if model_names else enabled_models
    
    # 返回测试配置信息，让前端可以立即创建任务卡片
    return {
        "status": "started",
        "config": {
            "models": actual_models,
            "cases": [tc.get("name") for tc in test_cases],
            "total_rounds": total_rounds,
            "concurrency": concurrent,
            "client_count": len(actual_models),
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


# 挂载静态文件（如果需要）
# app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), "static")


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