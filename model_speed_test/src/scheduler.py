"""
测试计划调度模块
支持定时任务、报告自动生成、Webhook通知
"""
import asyncio
import calendar
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Set
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
    
    def get_next_run_time(self, from_time: datetime = None) -> Optional[datetime]:
        """
        计算下次执行时间
        
        Returns:
            下次执行时间；ONCE 类型返回 None（表示执行一次后不再调度）
        """
        if from_time is None:
            from_time = datetime.now()
        
        if self.schedule_type == "once":
            # ONCE：一次性任务，返回 None 表示调度结束。
            # 调用方应将 next_run 置空，避免无限重复执行。
            return None
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
            return _monthly_next_run(
                from_time,
                day=self.day_of_month,
                hour=self.hour,
                minute=self.minute
            )
        elif self.schedule_type == "cron":
            if not self.cron_expression:
                return None
            try:
                return cron_next_run(self.cron_expression, from_time)
            except Exception as e:
                print(f"[Scheduler] Cron 表达式解析失败 '{self.cron_expression}': {e}")
                return None
        
        return None


def _monthly_next_run(from_time: datetime, day: int, hour: int, minute: int) -> datetime:
    """计算每月指定日期的下一次执行时间（自动 clamp 到月末）"""
    # 目标日超出当月最大天数时 clamp 到月末（如 31 日在 2 月 → 2/28 或 2/29）
    max_day = calendar.monthrange(from_time.year, from_time.month)[1]
    target_day = min(day, max_day)
    
    next_time = from_time.replace(day=target_day, hour=hour, minute=minute, second=0, microsecond=0)
    if next_time <= from_time:
        # 推进到下一个月的目标日
        if from_time.month == 12:
            next_year, next_month = from_time.year + 1, 1
        else:
            next_year, next_month = from_time.year, from_time.month + 1
        max_day_next = calendar.monthrange(next_year, next_month)[1]
        next_time = next_time.replace(
            year=next_year,
            month=next_month,
            day=min(day, max_day_next),
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )
    return next_time


def _parse_cron_field(field: str, min_val: int, max_val: int) -> Set[int]:
    """解析单个 cron 字段：支持 *、*/n、a-b、a-b/n、a,b,c、具体数字"""
    values: Set[int] = set()
    field = field.strip()
    if field == "" or field == "*":
        return set(range(min_val, max_val + 1))
    
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        
        # 步长解析：base/step，base 可为 * 或 a-b
        step = 1
        if "/" in part:
            base_str, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                continue
            if step <= 0:
                continue
        else:
            base_str = part
        
        if base_str == "*":
            start, end = min_val, max_val
        elif "-" in base_str:
            parts = base_str.split("-", 1)
            try:
                start, end = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if start < min_val:
                start = min_val
            if end > max_val:
                end = max_val
        else:
            try:
                single = int(base_str)
                if min_val <= single <= max_val:
                    values.add(single)
                continue
            except ValueError:
                continue
        
        values.update(range(start, end + 1, step))
    
    return values


def _parse_cron_expression(expression: str) -> Dict[str, Set[int]]:
    """
    解析 5 字段 cron 表达式：分 时 日 月 周
    (秒级不支持，周支持 0-6，0/7=周日)
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError(f"cron 表达式必须为 5 字段（分 时 日 月 周），收到: {expression!r}")
    
    minute_set = _parse_cron_field(fields[0], 0, 59)
    hour_set = _parse_cron_field(fields[1], 0, 23)
    day_set = _parse_cron_field(fields[2], 1, 31)
    month_set = _parse_cron_field(fields[3], 1, 12)
    
    # 周：cron 语义 0/7=周日, 1=周一 ... 6=周六
    # 转换为 Python datetime.weekday()（0=周一 ... 6=周日）
    weekday_set: Set[int] = set()
    for w in _parse_cron_field(fields[4], 0, 7):
        weekday_set.add((w - 1) % 7)
    
    return {
        "minute": minute_set,
        "hour": hour_set,
        "day": day_set,
        "month": month_set,
        "weekday": weekday_set,
    }


def cron_next_run(expression: str, from_time: datetime = None) -> datetime:
    """
    计算 cron 表达式的下一次执行时间（向后逐级推进，最多搜索 4 年）
    
    算法：从下一分钟开始，依次校验 月→日/周→时→分，
    每层不匹配时直接推进到该层下一个候选值，避免低效逐分钟扫描。
    """
    if from_time is None:
        from_time = datetime.now()
    
    parsed = _parse_cron_expression(expression)
    
    day_is_star = (len(parsed["day"]) == 31)
    weekday_is_star = (len(parsed["weekday"]) == 7)
    
    # 从下一分钟开始搜索
    candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    for _ in range(366 * 4):  # 最多搜索 4 年
        # 1. 月匹配？
        if candidate.month not in parsed["month"]:
            # 推进到下个月 1 号 00:00
            if candidate.month == 12:
                candidate = candidate.replace(year=candidate.year + 1, month=1, day=1, hour=0, minute=0)
            else:
                candidate = candidate.replace(month=candidate.month + 1, day=1, hour=0, minute=0)
            continue
        
        # 2. 日/周匹配（标准 cron 语义）：
        #    - day=* 且 weekday=* → 每天
        #    - day=* → 只按 weekday 匹配
        #    - weekday=* → 只按 day 匹配
        #    - 两者都限定 → 任一匹配（OR）
        day_ok = candidate.day in parsed["day"]
        weekday_ok = candidate.weekday() in parsed["weekday"]
        if day_is_star and weekday_is_star:
            day_weekday_ok = True
        elif day_is_star:
            day_weekday_ok = weekday_ok
        elif weekday_is_star:
            day_weekday_ok = day_ok
        else:
            day_weekday_ok = day_ok or weekday_ok
        
        if not day_weekday_ok:
            candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        
        # 3. 小时匹配？
        if candidate.hour not in parsed["hour"]:
            next_hours = sorted(h for h in parsed["hour"] if h > candidate.hour)
            if next_hours:
                candidate = candidate.replace(hour=next_hours[0], minute=0)
            else:
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        
        # 4. 分钟匹配？
        if candidate.minute not in parsed["minute"]:
            next_mins = sorted(m for m in parsed["minute"] if m > candidate.minute)
            if next_mins:
                candidate = candidate.replace(minute=next_mins[0])
            else:
                candidate = candidate.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        
        # 全部匹配
        return candidate
    
    raise ValueError(f"无法在 4 年内找到 cron 表达式的下次执行时间: {expression!r}")


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
        # 计算下次执行时间（ONCE 返回 None → next_run 置空）
        next_run = task.schedule.get_next_run_time()
        task.next_run = next_run.isoformat() if next_run else ""
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
            next_run = task.schedule.get_next_run_time()
            task.next_run = next_run.isoformat() if next_run else ""
        
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
        next_run = task.schedule.get_next_run_time(from_time=end_time)
        # ONCE 任务执行后 next_run 置空，不再重复调度
        task.next_run = next_run.isoformat() if next_run else ""
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
        """调度器循环（带重叠检测，避免长任务重复触发）"""
        while self._running:
            now = datetime.now()
            # 复制任务列表，避免遍历中修改
            tasks_snapshot = list(self._tasks.values())

            for task in tasks_snapshot:
                if not task.enabled:
                    continue
                if not task.next_run:
                    continue

                next_run = datetime.fromisoformat(task.next_run)

                # 重叠检测：只在非运行状态时触发
                if now >= next_run and task.status != "running":
                    print(f"[Scheduler] 执行任务: {task.name}")
                    task.status = "running"
                    asyncio.create_task(self._execute_with_cleanup(task.id))

            await asyncio.sleep(check_interval)

    async def _execute_with_cleanup(self, task_id: str):
        """执行任务并处理异常路径

        说明：execute_task 内部已把状态置为 completed/failed，
        这里不再覆盖（旧逻辑强制置 idle 会导致 ONCE/CRON 任务
        状态丢失、无限重复触发）。仅在 execute_task 抛异常时
        做兜底复位，避免卡在 running。
        """
        try:
            await self.execute_task(task_id)
        except Exception as e:
            print(f"[Scheduler] 任务 {task_id} 执行异常: {e}")
            if task_id in self._tasks:
                self._tasks[task_id].status = "failed"
                self._tasks[task_id].last_result = {"error": str(e)}
                self._save_all()
    
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