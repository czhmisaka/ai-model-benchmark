"""
事件发射器模块
用于在测试过程中实时推送事件到 Web 界面
支持文件持久化，页面刷新后可恢复状态
支持 SQLite 数据库持久化
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import deque
from pathlib import Path
import time


@dataclass
class TestEvent:
    """测试事件"""
    event_type: str  # 'start', 'progress', 'chunk', 'complete', 'error', 'summary'
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class TestEventEmitter:
    """测试事件发射器 - 使用内存队列实现 SSE，支持文件持久化和数据库存储"""

    # 状态文件路径
    STATE_FILE = "results/test_state.json"

    def __init__(self, max_history: int = 100, state_file: str = None, use_db: bool = True):
        self.max_history = max_history
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._subscribers: List[asyncio.Queue] = []
        self._history: deque = deque(maxlen=max_history)
        self._current_test: Optional[Dict[str, Any]] = None
        self._test_results: List[Dict[str, Any]] = []
        
        # 新增：完整任务状态存储
        # 结构: { "model__case": { "model_name": "", "test_case_name": "", "rounds": { "1": {...}, "2": {...} } } }
        self._tasks: Dict[str, Dict[str, Any]] = {}
        
        # 允许自定义状态文件路径
        if state_file:
            self.STATE_FILE = state_file
        
        # 数据库集成
        self._use_db = use_db
        self._db = None
        if use_db:
            self._init_database()
        
        # 启动时尝试恢复状态
        self._load_state()
    
    def _get_task_id(self, model_name: str, test_case_name: str) -> str:
        """生成任务ID"""
        return f"{model_name}__{test_case_name}"
    
    def _get_or_create_task(self, model_name: str, test_case_name: str, total_rounds: int = 10) -> Dict[str, Any]:
        """获取或创建任务状态"""
        task_id = self._get_task_id(model_name, test_case_name)
        
        if task_id not in self._tasks:
            # 创建新任务
            task = {
                "model_name": model_name,
                "test_case_name": test_case_name,
                "total_rounds": total_rounds,
                "rounds": {}
            }
            # 初始化所有轮次为 pending
            for r in range(1, total_rounds + 1):
                task["rounds"][str(r)] = {
                    "status": "pending",
                    "output": "",
                    "metrics": None
                }
            self._tasks[task_id] = task
        else:
            # 确保所有轮次都存在
            task = self._tasks[task_id]
            for r in range(1, total_rounds + 1):
                if str(r) not in task["rounds"]:
                    task["rounds"][str(r)] = {
                        "status": "pending",
                        "output": "",
                        "metrics": None
                    }
        
        return task
    
    def _init_database(self):
        """初始化数据库连接"""
        try:
            # 延迟导入避免循环依赖
            import sys
            from pathlib import Path
            
            # 获取项目根目录
            web_dir = Path(__file__).parent
            project_dir = web_dir.parent
            sys.path.insert(0, str(project_dir))
            
            from src.database import get_database
            self._db = get_database()
            print(f"[Emitter] 数据库已初始化: {self._db.DB_PATH}")
        except Exception as e:
            print(f"[Emitter] 数据库初始化失败: {e}")
            self._use_db = False
    
    def _get_state_file_path(self) -> Path:
        """获取状态文件路径（相对于当前文件）"""
        # 获取 web 目录的父目录（即项目根目录）
        web_dir = Path(__file__).parent
        project_dir = web_dir.parent
        return project_dir / self.STATE_FILE
    
    def _load_state(self):
        """从文件加载状态"""
        state_file = self._get_state_file_path()
        if not state_file.exists():
            return
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # 恢复历史事件
            history_data = state.get('history', [])
            for item in history_data:
                event = TestEvent(
                    event_type=item.get('event_type', ''),
                    timestamp=item.get('timestamp', time.time()),
                    data=item.get('data', {})
                )
                self._history.append(event)
            
            # 恢复测试结果
            self._test_results = state.get('test_results', [])
            
            # 恢复当前测试状态
            self._current_test = state.get('current_test')
            
            # 恢复任务状态（用于页面刷新后显示进度）
            self._tasks = state.get('tasks', {})
            
            print(f"[Emitter] 已从 {state_file} 恢复状态: {len(self._history)} 个事件, {len(self._test_results)} 个结果, {len(self._tasks)} 个任务")
        except Exception as e:
            print(f"[Emitter] 加载状态失败: {e}")
    
    def reload_state(self):
        """从文件重新加载状态（用于 API 请求时获取最新状态）"""
        # 先清空当前内存中的数据
        self._history.clear()
        self._test_results.clear()
        self._current_test = None
        self._tasks = {}
        
        # 然后从文件加载
        self._load_state()
        print(f"[Emitter] 已重新加载状态: {len(self._tasks)} 个任务")
    
    def _save_state(self):
        """保存状态到文件"""
        state_file = self._get_state_file_path()
        
        # 确保目录存在
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 序列化历史事件
            history_data = []
            for event in self._history:
                history_data.append({
                    'event_type': event.event_type,
                    'timestamp': event.timestamp,
                    'data': event.data
                })
            
            state = {
                'history': history_data,
                'test_results': self._test_results,
                'current_test': self._current_test,
                'tasks': self._tasks,  # 保存完整任务状态
                'group_id': self._current_test.get('group_id') if self._current_test else None,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            
            print(f"[Emitter] 状态已保存到 {state_file}")
        except Exception as e:
            print(f"[Emitter] 保存状态失败: {e}")

    def subscribe(self) -> asyncio.Queue:
        """创建新的订阅者队列"""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """取消订阅"""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    # 状态保存计数器
    _save_counter = 0
    _save_interval = 10  # 每10个事件保存一次状态
    
    async def emit(self, event: TestEvent):
        """发射事件到所有订阅者"""
        # 保存到历史记录
        self._history.append(event)

        # 推送到所有订阅者
        for queue in self._subscribers:
            try:
                await queue.put(event)
            except Exception:
                pass
        
        # 减少保存频率：只保存重要事件（start, complete, summary, error）
        # 不保存频繁的 progress 和 chunk 事件
        if event.event_type in ('start', 'complete', 'summary', 'error'):
            TestEventEmitter._save_counter += 1
            if TestEventEmitter._save_counter >= TestEventEmitter._save_interval:
                self._save_state()
                TestEventEmitter._save_counter = 0

    # 便捷方法
    async def emit_start(self, config: Dict[str, Any]) -> str:
        """发射测试开始事件，返回 group_id"""
        total_rounds = config.get("total_rounds", 10)  # 默认10轮
        models = config.get("models", [])
        test_cases = config.get("test_cases", [])
        
        # 生成 group_id
        group_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 初始化所有任务状态
        self._tasks = {}
        for model_name in models:
            for test_case_name in test_cases:
                self._get_or_create_task(model_name, test_case_name, total_rounds)
        
        # 保存到数据库
        if self._use_db and self._db:
            try:
                self._db.create_group(
                    group_id=group_id,
                    name=f"测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    models=models,
                    test_cases=test_cases,
                    total_rounds=total_rounds
                )
                print(f"[Emitter] 已创建测试组: {group_id}")
            except Exception as e:
                print(f"[Emitter] 创建测试组失败: {e}")
        
        await self.emit(TestEvent(
            event_type="start",
            data={
                "group_id": group_id,
                "models": models,
                "test_cases": test_cases,
                "total_rounds": total_rounds,
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        return group_id

    async def emit_progress(
        self,
        model_name: str,
        test_case_name: str,
        current_round: int,
        total_rounds: int,
        status: str = "running",
        prompt: str = ""
    ):
        """发射进度事件"""
        # 计算总任务数和当前进度
        models = self._current_test.get("models", []) if self._current_test else []
        test_cases = self._current_test.get("test_cases", []) if self._current_test else []
        
        total = len(models) * len(test_cases) * total_rounds
        current = self._current_test.get("completed_count", 0) if self._current_test else 0
        
        # 当前任务的进度
        task_progress = int((current_round / total_rounds) * 100)

        await self.emit(TestEvent(
            event_type="progress",
            data={
                "model_name": model_name,
                "test_case_name": test_case_name,
                "current_round": current_round,
                "total_rounds": total_rounds,
                "status": status,
                "prompt": prompt,
                "percent": task_progress
            }
        ))

    async def emit_chunk(self, content: str, is_first: bool, model_name: str, test_case_name: str = "", current_round: int = 1, total_rounds: int = 1):
        """发射流式输出块"""
        # 更新任务状态 - 累加输出
        task = self._get_or_create_task(model_name, test_case_name, total_rounds)
        round_key = str(current_round)
        
        if round_key in task["rounds"]:
            # 累加输出内容
            if is_first:
                # 新一轮开始，重置输出
                task["rounds"][round_key]["output"] = content
            else:
                # 累加输出
                task["rounds"][round_key]["output"] += content
            # 设置为 running 状态
            task["rounds"][round_key]["status"] = "running"
        
        await self.emit(TestEvent(
            event_type="chunk",
            data={
                "content": content,
                "is_first": is_first,
                "model_name": model_name,
                "test_case_name": test_case_name,
                "current_round": current_round,
                "total_rounds": total_rounds,
                "timestamp": datetime.now().isoformat()
            }
        ))

    async def emit_complete(
        self,
        model_name: str,
        test_case_name: str,
        metrics: Dict[str, Any],
        success: bool = True,
        current_round: int = 1,
        total_rounds: int = 10,
        group_id: str = None,
        prompt: str = None,
        response: str = None
    ):
        """发射单次测试完成事件"""
        # 更新任务状态 - 保存完整输出
        task = self._get_or_create_task(model_name, test_case_name, total_rounds)
        round_key = str(current_round)
        
        # 获取当前轮次的输出
        output_text = ""
        if round_key in task["rounds"]:
            output_text = task["rounds"][round_key].get("output", "")
        
        # 更新任务状态
        if round_key in task["rounds"]:
            task["rounds"][round_key]["status"] = "done" if success else "error"
            task["rounds"][round_key]["metrics"] = metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
        
        # 保存结果
        self._test_results.append({
            "model_name": model_name,
            "test_case_name": test_case_name,
            "metrics": metrics,
            "success": success,
            "current_round": current_round,
            "total_rounds": total_rounds,
            "output": output_text,  # 保存完整输出
            "timestamp": datetime.now().isoformat()
        })

        # 更新完成计数
        if self._current_test:
            self._current_test["completed_count"] = self._current_test.get("completed_count", 0) + 1

        # 保存到数据库（包含完整输出）
        if self._use_db and self._db and group_id:
            try:
                # 将 metrics 对象转换为字典
                metrics_dict = metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics
                
                self._db.add_result(
                    group_id=group_id,
                    model_name=model_name,
                    test_case_name=test_case_name,
                    round_number=current_round,
                    metrics=metrics_dict,
                    success=success,
                    prompt=prompt,
                    response=output_text  # 使用完整输出
                )
                print(f"[Emitter] 已保存测试结果: {group_id} - {model_name} - R{current_round}")
            except Exception as e:
                print(f"[Emitter] 保存测试结果失败: {e}")

        await self.emit(TestEvent(
            event_type="complete",
            data={
                "group_id": group_id,
                "model_name": model_name,
                "test_case_name": test_case_name,
                "metrics": metrics,
                "success": success,
                "current_round": current_round,
                "total_rounds": total_rounds,
                "prompt": prompt or "",
                "response": response or ""
            }
        ))
        
        # 立即保存状态（确保轮次状态更新到文件）
        self._save_state()

    async def emit_error(self, error: str, model_name: str = ""):
        """发射错误事件"""
        await self.emit(TestEvent(
            event_type="error",
            data={
                "error": error,
                "model_name": model_name,
                "timestamp": datetime.now().isoformat()
            }
        ))
        
        # 注意：emit_error 不更新具体轮次状态，因为不知道是哪一轮出错
        # 轮次状态应该由 emit_complete 来更新
        # 完成后也标记状态
        if self._current_test:
            self._current_test["completed_count"] = self._current_test.get("completed_count", 0) + 1
        
        # 保存状态（包含 error 事件）
        self._save_state()

    async def emit_summary(self, group_id: str = None):
        """发射汇总事件"""
        # 更新测试组状态
        if self._use_db and self._db and group_id:
            try:
                # 直接从数据库查询实际统计结果，而不是依赖内存中的 _test_results
                # 因为并发模式下内存列表可能不完整
                results = self._db.get_results(group_id)
                success_count = sum(1 for r in results if r.get("success", 0) == 1)
                failed_count = len(results) - success_count
                completed_rounds = len(results)
                
                self._db.update_group(
                    group_id=group_id,
                    end_time=datetime.now().isoformat(),
                    status="completed",
                    completed_rounds=completed_rounds,
                    success_count=success_count,
                    failed_count=failed_count
                )
                print(f"[Emitter] 已更新测试组状态: {group_id}, 完成: {completed_rounds}, 成功: {success_count}, 失败: {failed_count}")
            except Exception as e:
                print(f"[Emitter] 更新测试组状态失败: {e}")
        
        await self.emit(TestEvent(
            event_type="summary",
            data={
                "group_id": group_id,
                "results": self._test_results,
                "timestamp": datetime.now().isoformat()
            }
        ))

    def set_current_test(self, config: Dict[str, Any]):
        """设置当前测试配置"""
        self._current_test = {
            "config": config,
            "models": config.get("models", []),
            "test_cases": config.get("test_cases", []),
            "completed_count": 0
        }

    def get_history(self) -> List[TestEvent]:
        """获取历史事件"""
        return list(self._history)

    def get_results(self) -> List[Dict[str, Any]]:
        """获取测试结果"""
        return self._test_results

    def reset(self, clear_state_file: bool = True):
        """重置发射器
        
        Args:
            clear_state_file: 是否删除状态文件，默认为 True
        """
        self._history.clear()
        self._test_results.clear()
        
        # 注意：不重置 _current_test，保留 group_id 等信息
        
        # 可选：是否清空任务状态和删除状态文件
        # 保留 _tasks 以便页面刷新后能恢复进度
        # 只有明确要求时才清空任务状态
        if clear_state_file:
            self._tasks.clear()  # 清空任务状态
            self._current_test = None  # 清空当前测试
            
            # 删除持久化的状态文件
            state_file = self._get_state_file_path()
            if state_file.exists():
                try:
                    state_file.unlink()
                    print(f"[Emitter] 已删除状态文件: {state_file}")
                except Exception as e:
                    print(f"[Emitter] 删除状态文件失败: {e}")
        else:
            # 不删除状态文件，只保存当前状态
            # 更新状态文件，保留 _tasks 和其他信息
            self._save_state()
            print(f"[Emitter] 已保留状态文件，进度将保留")


# 全局实例
test_emitter = TestEventEmitter()