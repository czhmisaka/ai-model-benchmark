"""
测试计划调度模块
支持定时任务、报告自动生成、Webhook通知
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import hashlib
import hmac


class ScheduleType(Enum):
    """调度类型"""
    ONCE = "once"           # 单次
    DAILY = "daily"         # 每日
    WEEKLY = "weekly"       # 每周
    MONTHLY = "monthly"     # 每月
    CRON = "cron"           # Cron表达式


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduleConfig:
    """调度配置"""
    schedule_type: str = "daily"
    hour: int = 2           # 每日执行小时
    minute: int = 0         # 每日执行分钟
    weekday: int = 0       # 周几 (0=周一)
    day_of_month: int = 1   # 每月几号
    cron_expression: str = ""  # Cron表达式
    
    def get_next_run_time(self, from_time: datetime = None) -> datetime:
        """计算下次执行时间"""
        if from_time is None:
            from_time = datetime.now()
        
        if self.schedule_type == "once":
            return from_time
        elif self.schedule_type == "daily":
            next_time = from_time.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
            if next_time <= from_time:
                next_time += timedelta(days=1)
            return next_time
        elif self.schedule_type == "weekly":
            days_ahead = self.weekday - from_time.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_time = from_time + timedelta(days=days_ahead)
            next_time = next_time.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
            return next_time
        elif self.schedule_type == "monthly":
            if from_time.day < self.day_of_month:
                next_time = from_time.replace(day=self.day_of_month, hour=self.hour, minute=self.minute, second=0, microsecond=0)
            else:
                # 下个月
                if from_time.month == 12:
                    next_time = from_time.replace(year=from_time.year+1, month=1, day=self.day_of_month, hour=self.hour, minute=self.minute, second=0, microsecond=0)
                else:
                    next_time = from_time.replace(month=from_time.month+1, day=self.day_of_month, hour=self.hour, minute=self.minute, second=0, microsecond=0)
            return next_time
        
        return from_time


@dataclass
class TestTask:
    """测试任务"""
    id: str
    name: str
    description: str = ""
    test_case_ids: List[str] = field(default_factory=list)
    model_ids: List[str] = field(default_factory=list)
    rounds: int = 3
    concurrency: int = 1
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    enabled: bool = True
    webhook_url: str = ""
    webhook_secret: str = ""
    notification_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 执行状态
    status: str = "pending"
    last_run: str = ""
    next_run: str = ""
    last_result: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class WebhookNotifier:
    """Webhook通知器"""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
    
    def _sign_payload(self, payload: str, secret: str) -> str:
        """生成签名"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def send(self, url: str, secret: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送Webhook通知"""
        if not url:
            return {"success": False, "error": "No webhook URL"}
        
        payload = json.dumps(data, ensure_ascii=False)
        headers = {"Content-Type": "application/json"}
        
        # 如果有密钥，添加签名
        if secret:
            signature = self._sign_payload(payload, secret)
            headers["X-Signature"] = signature
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    data=payload.encode('utf-8'),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    return {
                        "success": response.status == 200,
                        "status_code": response.status,
                        "response": await response.text()
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def send_dingtalk(self, url: str, message: str, secret: str = "") -> Dict[str, Any]:
        """发送钉钉通知"""
        # 钉钉特殊格式
        data = {
            "msgtype": "text",
            "text": {"content": f"[模型测试] {message}"}
        }
        return await self.send(url, secret, data)
    
    async def send_feishu(self, url: str, message: str, secret: str = "") -> Dict[str, Any]:
        """发送飞书通知"""
        data = {
            "msg_type": "text",
            "content": {"text": f"[模型测试] {message}"}
        }
        return await self.send(url, secret, data)


class TestScheduler:
    """测试调度器"""
    
    def __init__(
        self,
        storage_path: str = "config/schedules",
        task_executor: Callable = None
    ):
        self.storage_path = storage_path
        self.task_executor = task_executor  # 任务执行函数
        self.webhook_notifier = WebhookNotifier()
        self._tasks: Dict[str, TestTask] = {}
        self._running = False
        self._scheduler_task = None
        self._load_all()
    
    def _load_all(self):
        """加载所有任务"""
        os.makedirs(self.storage_path, exist_ok=True)
        filepath = os.path.join(self.storage_path, "tasks.json")
        
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        task = TestTask(
                            id=item["id"],
                            name=item["name"],
                            description=item.get("description", ""),
                            test_case_ids=item.get("test_case_ids", []),
                            model_ids=item.get("model_ids", []),
                            rounds=item.get("rounds", 3),
                            concurrency=item.get("concurrency", 1),
                            schedule=ScheduleConfig(**item.get("schedule", {})),
                            enabled=item.get("enabled", True),
                            webhook_url=item.get("webhook_url", ""),
                            webhook_secret=item.get("webhook_secret", ""),
                            notification_enabled=item.get("notification_enabled", True),
                            metadata=item.get("metadata", {}),
                            status=item.get("status", "pending"),
                            last_run=item.get("last_run", ""),
                            next_run=item.get("next_run", ""),
                            last_result=item.get("last_result", {}),
                            created_at=item.get("created_at", datetime.now().isoformat())
                        )
                        self._tasks[task.id] = task
            except Exception as e:
                print(f"加载调度任务失败: {e}")
    
    def _save_all(self):
        """保存所有任务"""
        os.makedirs(self.storage_path, exist_ok=True)
        filepath = os.path.join(self.storage_path, "tasks.json")
        
        data = []
        for task in self._tasks.values():
            data.append({
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "test_case_ids": task.test_case_ids,
                "model_ids": task.model_ids,
                "rounds": task.rounds,
                "concurrency": task.concurrency,
                "schedule": {
                    "schedule_type": task.schedule.schedule_type,
                    "hour": task.schedule.hour,
                    "minute": task.schedule.minute,
                    "weekday": task.schedule.weekday,
                    "day_of_month": task.schedule.day_of_month,
                    "cron_expression": task.schedule.cron_expression
                },
                "enabled": task.enabled,
                "webhook_url": task.webhook_url,
                "webhook_secret": task.webhook_secret,
                "notification_enabled": task.notification_enabled,
                "metadata": task.metadata,
                "status": task.status,
                "last_run": task.last_run,
                "next_run": task.next_run,
                "last_result": task.last_result,
                "created_at": task.created_at
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_task(self, task: TestTask) -> str:
        """添加任务"""
        # 计算下次执行时间
        task.next_run = task.schedule.get_next_run_time().isoformat()
        self._tasks[task.id] = task
        self._save_all()
        return task.id
    
    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """更新任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        
        if "schedule" in updates:
            task.schedule = ScheduleConfig(**updates["schedule"])
            task.next_run = task.schedule.get_next_run_time().isoformat()
        
        for key, value in updates.items():
            if key != "schedule" and hasattr(task, key):
                setattr(task, key, value)
        
        self._save_all()
        return True
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        self._save_all()
        return True
    
    def get_task(self, task_id: str) -> Optional[TestTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, enabled_only: bool = False) -> List[TestTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if enabled_only:
            tasks = [t for t in tasks if t.enabled]
        return tasks
    
    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """执行任务"""
        if task_id not in self._tasks:
            return {"success": False, "error": "Task not found"}
        
        task = self._tasks[task_id]
        task.status = "running"
        self._save_all()
        
        start_time = datetime.now()
        
        result = {
            "task_id": task_id,
            "task_name": task.name,
            "start_time": start_time.isoformat(),
            "success": False,
            "details": {}
        }
        
        try:
            # 执行任务
            if self.task_executor:
                exec_result = await self.task_executor(task)
                result["details"] = exec_result
                result["success"] = True
            else:
                result["error"] = "No executor configured"
            
        except Exception as e:
            result["error"] = str(e)
        
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        # 更新任务状态
        task.status = "completed" if result["success"] else "failed"
        task.last_run = start_time.isoformat()
        task.next_run = task.schedule.get_next_run_time(from_time=end_time).isoformat()
        task.last_result = result
        self._save_all()
        
        # 发送通知
        if task.notification_enabled and task.webhook_url:
            message = f"任务【{task.name}】{'成功' if result['success'] else '失败'}"
            message += f"，耗时 {result['duration_seconds']:.1f}秒"
            
            if result["success"]:
                # 添加关键指标
                if "details" in result and "metrics" in result["details"]:
                    metrics = result["details"]["metrics"]
                    message += f"\n平均TPS: {metrics.get('avg_tps', 'N/A')}"
            
            await self.webhook_notifier.send(task.webhook_url, task.webhook_secret, {
                "task_id": task_id,
                "task_name": task.name,
                "status": task.status,
                "message": message,
                "result": result
            })
        
        return result
    
    async def _run_scheduler(self, check_interval: int = 60):
        """调度器循环"""
        while self._running:
            now = datetime.now()
            
            for task in self._tasks.values():
                if not task.enabled:
                    continue
                
                if not task.next_run:
                    continue
                
                next_run = datetime.fromisoformat(task.next_run)
                
                if now >= next_run:
                    print(f"[Scheduler] 执行任务: {task.name}")
                    await self.execute_task(task.id)
            
            await asyncio.sleep(check_interval)
    
    async def start(self, check_interval: int = 60):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler(check_interval))
        print("[Scheduler] 调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] 调度器已停止")
    
    def get_pending_tasks(self) -> List[TestTask]:
        """获取待执行任务"""
        now = datetime.now()
        pending = []
        
        for task in self._tasks.values():
            if not task.enabled:
                continue
            
            if not task.next_run:
                continue
            
            next_run = datetime.fromisoformat(task.next_run)
            if next_run <= now:
                pending.append(task)
        
        return pending
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._tasks)
        enabled = sum(1 for t in self._tasks.values() if t.enabled)
        
        status_counts = {}
        for task in self._tasks.values():
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
        
        return {
            "total": total,
            "enabled": enabled,
            "status": status_counts
        }


def create_scheduler(
    storage_path: str = "config/schedules",
    task_executor: Callable = None
) -> TestScheduler:
    """创建调度器"""
    return TestScheduler(storage_path, task_executor)