"""
日志调试模块
提供结构化日志、请求追踪、错误诊断功能
"""
import json
import os
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps
import asyncio


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    logger: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    trace_id: str = ""
    error: str = ""
    stack_trace: str = ""


class RequestTracer:
    """请求追踪器"""
    
    def __init__(self):
        self._traces: Dict[str, Dict[str, Any]] = {}
        self._current_trace_id = 0
    
    def start_trace(self, operation: str, metadata: Dict[str, Any] = None) -> str:
        """开始追踪"""
        trace_id = f"trace_{self._current_trace_id}_{int(time.time() * 1000)}"
        self._current_trace_id += 1
        
        self._traces[trace_id] = {
            "id": trace_id,
            "operation": operation,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "status": "running",
            "metadata": metadata or {},
            "events": [],
            "errors": []
        }
        
        return trace_id
    
    def add_event(self, trace_id: str, event: str, data: Dict[str, Any] = None):
        """添加事件"""
        if trace_id not in self._traces:
            return
        
        self._traces[trace_id]["events"].append({
            "timestamp": time.time(),
            "event": event,
            "data": data or {}
        })
    
    def end_trace(self, trace_id: str, status: str = "success", error: str = None):
        """结束追踪"""
        if trace_id not in self._traces:
            return
        
        trace = self._traces[trace_id]
        trace["end_time"] = time.time()
        trace["duration"] = trace["end_time"] - trace["start_time"]
        trace["status"] = status
        
        if error:
            trace["errors"].append({
                "timestamp": time.time(),
                "error": error
            })
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """获取追踪"""
        return self._traces.get(trace_id)
    
    def get_traces(self, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取追踪列表"""
        traces = list(self._traces.values())
        
        if status:
            traces = [t for t in traces if t["status"] == status]
        
        # 按时间倒序
        traces.sort(key=lambda x: x["start_time"], reverse=True)
        
        return traces[:limit]
    
    def clear_traces(self, older_than: float = None):
        """清理追踪"""
        if older_than is None:
            self._traces.clear()
            return
        
        now = time.time()
        self._traces = {
            tid: trace for tid, trace in self._traces.items()
            if now - trace["start_time"] < older_than
        }


class StructuredLogger:
    """结构化日志器"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self._current_level = LogLevel.INFO
        self._tracer = RequestTracer()
        
        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)
    
    def set_level(self, level: LogLevel):
        """设置日志级别"""
        self._current_level = level
    
    def _write_log(self, level: LogLevel, message: str, context: Dict[str, Any] = None, error: Exception = None):
        """写入日志"""
        if level.value < self._current_level.value:
            return
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.name,
            logger=self.name,
            message=message,
            context=context or {},
            error=str(error) if error else "",
            stack_trace=traceback.format_exc() if error else ""
        )
        
        # 写入文件
        log_file = os.path.join(self.log_dir, f"{self.name}_{datetime.now().strftime('%Y%m%d')}.jsonl")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        
        # 同时输出到控制台
        print(f"[{entry.timestamp}] {level.name} - {self.name}: {message}")
        if context:
            print(f"  Context: {json.dumps(context, ensure_ascii=False)}")
        if error:
            print(f"  Error: {error}")
    
    def debug(self, message: str, context: Dict[str, Any] = None):
        """调试日志"""
        self._write_log(LogLevel.DEBUG, message, context)
    
    def info(self, message: str, context: Dict[str, Any] = None):
        """信息日志"""
        self._write_log(LogLevel.INFO, message, context)
    
    def warning(self, message: str, context: Dict[str, Any] = None):
        """警告日志"""
        self._write_log(LogLevel.WARNING, message, context)
    
    def error(self, message: str, context: Dict[str, Any] = None, error: Exception = None):
        """错误日志"""
        self._write_log(LogLevel.ERROR, message, context, error)
    
    def critical(self, message: str, context: Dict[str, Any] = None, error: Exception = None):
        """严重错误日志"""
        self._write_log(LogLevel.CRITICAL, message, context, error)
    
    def trace_request(self, operation: str):
        """追踪请求装饰器"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                trace_id = self._tracer.start_trace(operation, {
                    "function": func.__name__,
                    "args": str(args)[:100],
                    "kwargs": str(kwargs)[:100]
                })
                try:
                    self._tracer.add_event(trace_id, "start")
                    result = await func(*args, **kwargs)
                    self._tracer.add_event(trace_id, "success")
                    self._tracer.end_trace(trace_id, "success")
                    return result
                except Exception as e:
                    self._tracer.add_event(trace_id, "error", {"error": str(e)})
                    self._tracer.end_trace(trace_id, "error", str(e))
                    raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                trace_id = self._tracer.start_trace(operation, {
                    "function": func.__name__,
                    "args": str(args)[:100],
                    "kwargs": str(kwargs)[:100]
                })
                try:
                    self._tracer.add_event(trace_id, "start")
                    result = func(*args, **kwargs)
                    self._tracer.add_event(trace_id, "success")
                    self._tracer.end_trace(trace_id, "success")
                    return result
                except Exception as e:
                    self._tracer.add_event(trace_id, "error", {"error": str(e)})
                    self._tracer.end_trace(trace_id, "error", str(e))
                    raise
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        return decorator
    
    def get_tracer(self) -> RequestTracer:
        """获取追踪器"""
        return self._tracer
    
    def get_recent_logs(self, level: str = None, limit: int = 100) -> List[LogEntry]:
        """获取最近日志"""
        log_file = os.path.join(self.log_dir, f"{self.name}_{datetime.now().strftime('%Y%m%d')}.jsonl")
        
        if not os.path.exists(log_file):
            return []
        
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry_data = json.loads(line)
                    if level and entry_data.get("level") != level:
                        continue
                    logs.append(LogEntry(**entry_data))
                except Exception:
                    continue
        
        return logs[-limit:]


class APIDebugger:
    """API 调试器"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.request_history: List[Dict[str, Any]] = []
        self.max_history = 1000
    
    def log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        body: Any = None,
        response = None,
        duration: float = None,
        error: Exception = None
    ):
        """记录 API 请求"""
        request_info = {
            "timestamp": datetime.now().isoformat(),
            "method": method,
            "url": url,
            "headers": {k: v for k, v in (headers or {}).items() if k.lower() not in ["authorization", "api-key"]},
            "body": str(body)[:500] if body else None,
            "duration": duration,
            "status_code": getattr(response, "status_code", None) if response else None,
            "response": str(response)[:500] if response else None,
            "error": str(error) if error else None
        }
        
        self.request_history.append(request_info)
        
        # 限制历史长度
        if len(self.request_history) > self.max_history:
            self.request_history = self.request_history[-self.max_history:]
        
        # 记录到日志
        if error:
            self.logger.error(f"API Error: {method} {url}", {
                "duration": duration,
                "error": str(error)
            }, error)
        else:
            self.logger.info(f"API Request: {method} {url}", {
                "duration": duration,
                "status": request_info.get("status_code")
            })
    
    def get_history(
        self,
        method: str = None,
        url_pattern: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取请求历史"""
        history = self.request_history
        
        if method:
            history = [r for r in history if r.get("method") == method]
        
        if url_pattern:
            history = [r for r in history if url_pattern in r.get("url", "")]
        
        return history[-limit:]
    
    def analyze_errors(self) -> Dict[str, Any]:
        """分析错误"""
        errors = [r for r in self.request_history if r.get("error")]
        
        error_types = {}
        for error in errors:
            error_msg = error.get("error", "Unknown")
            error_types[error_msg] = error_types.get(error_msg, 0) + 1
        
        return {
            "total_requests": len(self.request_history),
            "error_count": len(errors),
            "error_rate": len(errors) / len(self.request_history) if self.request_history else 0,
            "error_types": error_types,
            "recent_errors": errors[-10:]
        }


# 全局日志器
_default_logger: Optional[StructuredLogger] = None


def get_logger(name: str = "model_test", log_dir: str = "logs") -> StructuredLogger:
    """获取全局日志器"""
    global _default_logger
    if _default_logger is None:
        _default_logger = StructuredLogger(name, log_dir)
    return _default_logger


def get_api_debugger(logger: StructuredLogger = None) -> APIDebugger:
    """获取 API 调试器"""
    if logger is None:
        logger = get_logger()
    return APIDebugger(logger)