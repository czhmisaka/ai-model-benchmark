<!--
 * @Date: 2026-06-24 14:24
 * @LastEditors: Cline
 * @LastEditTime: 2026-06-24 14:24
 * @FilePath: /模型速度测试/task.md
-->

# 性能稳定性优化方案 — 实施计划 v1

> **方案来源**：基于 2026-06-24 第二轮代码审查（110+ 问题）
> **方案选择**：B - 性能稳定性优先（第一波清理 + 第三波优化）
> **预计总工时**：~13.5 小时
> **风险等级**：🟡 中（需压测验证）
> **关联报告**：`代码审查报告-2026-06-24.md`

---

## 📋 方案概览

### 范围选择理由

| 选项 | 内容 | 工时 | 选择理由 |
|------|------|:----:|---------|
| ~~A. 清理 + 安全加固~~ | 第一波 + 第二波 | ~6h | 用户优先级更看重性能 |
| **✅ B. 性能稳定性优先** | **第一波 + 第三波** | **~13.5h** | **本方案** |
| ~~C. 全量修复~~ | 第一波 + 二 + 三 | ~19h | 工时过长 |
| ~~D. 重构优先~~ | 第四波 | ~50h | 风险过高 |

### 涵盖问题（共 13 项）

- **第一波**（5 项清理任务，15 分钟）：删除冗余文件、补全环境变量
- **第三波**（8 项性能优化，~13 小时）：异步 I/O、调度器、信号量、SSE、内存泄漏等

---

## 🎯 一、第一波：5 分钟级清理（零风险，立刻做）

### 1.1 任务清单

| # | 任务 | 命令 | 工时 |
|---|------|------|:----:|
| 1 | 删除 `tester.py.bak` | `rm model_speed_test/src/tester.py.bak` | 1min |
| 2 | 删除 `recorder.py.bak` | `rm model_speed_test/src/recorder.py.bak` | 1min |
| 3 | 删除 `提示词.md/html` | `rm 提示词.md 提示词.html` | 1min |
| 4 | 删除 `UI评估报告-Cline界面.md` | `rm UI评估报告-Cline界面.md` | 1min |
| 5 | 删除根目录 `package.json` | `rm package.json` | 1min |
| 6 | 删除 `test_lmstudio_debug.py` | `rm test_lmstudio_debug.py` | 1min |
| 7 | 删除 `debug_dsv4_stream.py` | `rm debug_dsv4_stream.py` | 1min |
| 8 | 删除 `History.vue.bak` | `rm model_speed_test/frontend/src/views/History.vue.bak` | 1min |
| 9 | 删除 `test_dsv4_stream_output.txt` | `rm scripts/test_dsv4_stream_output.txt` | 1min |
| 10 | 补 `.env.example` 缺失变量 | 手动追加 3 行 | 5min |
| **小计** | | | **15min** |

### 1.2 删除前安全检查

```bash
cd /Volumes/mobileDisk/test/模型速度测试

# 删除前确认无引用
echo "=== 检查 .bak 引用 ==="
grep -rn "tester.py.bak\|recorder.py.bak" . --include="*.py" --include="*.md" 2>/dev/null

echo "=== 检查错放文档引用 ==="
grep -rn "提示词\|UI评估报告" model_speed_test --include="*.py" --include="*.vue" --include="*.md" 2>/dev/null

echo "=== 检查 scripts 中引用 ==="
grep -rn "test_lmstudio_debug\|debug_dsv4_stream" model_speed_test 2>/dev/null
```

### 1.3 一键清理脚本

```bash
#!/bin/bash
# 清理脚本 - 先 echo 出来确认，再执行
set -e

cd /Volumes/mobileDisk/test/模型速度测试

echo "🗑️  开始清理冗余文件..."

# src/ 备份文件
[ -f model_speed_test/src/tester.py.bak ] && rm -v model_speed_test/src/tester.py.bak
[ -f model_speed_test/src/recorder.py.bak ] && rm -v model_speed_test/src/recorder.py.bak

# 错放文档
[ -f 提示词.md ] && rm -v 提示词.md
[ -f 提示词.html ] && rm -v 提示词.html
[ -f UI评估报告-Cline界面.md ] && rm -v UI评估报告-Cline界面.md

# 根目录冗余
[ -f package.json ] && rm -v package.json
[ -f test_lmstudio_debug.py ] && rm -v test_lmstudio_debug.py
[ -f debug_dsv4_stream.py ] && rm -v debug_dsv4_stream.py
[ -f scripts/test_dsv4_stream_output.txt ] && rm -v scripts/test_dsv4_stream_output.txt

# 前端备份
[ -f model_speed_test/frontend/src/views/History.vue.bak ] && rm -v model_speed_test/frontend/src/views/History.vue.bak

echo "✅ 清理完成"

# 补全 .env.example
ENV_FILE="model_speed_test/.env.example"
if [ -f "$ENV_FILE" ]; then
    grep -q "^WEB_API_KEY=" "$ENV_FILE" || echo "WEB_API_KEY=" >> "$ENV_FILE"
    grep -q "^CORS_ALLOWED_ORIGINS=" "$ENV_FILE" || echo "CORS_ALLOWED_ORIGINS=http://localhost:5173" >> "$ENV_FILE"
    grep -q "^WEBHOOK_SECRET_KEY=" "$ENV_FILE" || echo "WEBHOOK_SECRET_KEY=" >> "$ENV_FILE"
    echo "✅ .env.example 已补全"
fi
```

### 1.4 验收标准

- [ ] 上述 10 个文件已删除
- [ ] `.env.example` 包含新增的 3 个环境变量
- [ ] `git status` 显示 9-11 个 `deleted` 文件
- [ ] 项目仍可正常启动（`./start.sh` + `cd frontend && npm run dev`）

---

## ⚡ 二、第三波：性能与稳定性优化（~13h）

### 2.1 H-7: async 路径改异步 I/O（4h）

**问题**：recorder.py / database.py 在 async 函数中使用 `open()` / `json.dump()` / `sqlite3.connect()`，阻塞事件循环。

**影响范围**（11 个文件）：
- `src/recorder.py`（行 93, 99, 111, 207, 220, 320, 353, 358, 368, 396, 454, 493）
- `src/database.py`（多处）
- `src/test_case_manager.py`（行 81, 106, 199, 226）
- `src/scheduler.py`（行 187, 249）
- `src/logging_utils.py`（行 155, 241）

**实施步骤**：

1. **添加依赖**
```bash
cd model_speed_test
echo "aiofiles>=23.0.0" >> requirements.txt
pip install aiofiles
```

2. **封装异步文件 I/O 工具**（新建 `src/async_io.py`）
```python
"""异步文件 I/O 工具集"""
import asyncio
import aiofiles
import json
import tempfile
import os
from typing import Any, Union

_executor = None

def get_executor():
    """获取共享线程池"""
    global _executor
    if _executor is None:
        from concurrent.futures import ThreadPoolExecutor
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async-io")
    return _executor


async def read_text(path: str, encoding: str = "utf-8") -> str:
    """异步读取文本"""
    async with aiofiles.open(path, "r", encoding=encoding) as f:
        return await f.read()


async def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """异步写入文本"""
    async with aiofiles.open(path, "w", encoding=encoding) as f:
        await f.write(content)


async def read_json(path: str) -> Any:
    """异步读取 JSON"""
    text = await read_text(path)
    return json.loads(text)


async def write_json(path: str, data: Any, indent: int = 2) -> None:
    """异步写入 JSON"""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    await write_text(path, content)


async def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """原子写入 JSON（写临时文件 → rename）"""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    dir_path = os.path.dirname(path) or "."
    
    # 写到临时文件
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # 原子替换
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


async def write_bytes(path: str, data: bytes) -> None:
    """异步写入二进制"""
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


def run_sync(func, *args, **kwargs):
    """在后台线程运行同步函数（用于 sqlite3 等）"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(get_executor(), func, *args, **kwargs)
```

3. **改造 recorder.py**（示例片段）
```python
# Before (recorder.py:93)
with open(self.manifest_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# After
from src.async_io import atomic_write_json

await atomic_write_json(self.manifest_file, data)
```

4. **改造 database.py**（sqlite3 同步连接 → run_in_executor）
```python
# Before
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
cursor.execute("SELECT ...", (param,))
result = cursor.fetchall()
conn.close()

# After
from src.async_io import run_sync

def _sync_query(db_path, sql, params):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()

result = await run_sync(_sync_query, self.db_path, "SELECT ...", (param,))
```

5. **逐文件改造清单**

| 文件 | 改动行数 | 函数 |
|------|:----:|------|
| `recorder.py` | 12 处 | 所有 `open()` + `json.dump()` |
| `database.py` | ~20 处 | 所有 `sqlite3.connect()` + `cursor.execute()` |
| `test_case_manager.py` | 4 处 | JSON 配置读写 |
| `scheduler.py` | 2 处 | tasks.json 读写 |
| `logging_utils.py` | 2 处 | 日志文件读写 |

**验收标准**：
- [ ] 11 个文件改造完成
- [ ] 单元测试：并发 10 路 `recorder.save()` 不阻塞事件循环
- [ ] 压测：1000 用例 × 5 轮测试，整体耗时下降 ≥ 20%

---

### 2.2 H-8: scheduler 重叠检测 + 原子写（2h）

**问题**：
- 调度器 60s 轮询，长任务执行中重复触发
- `_save_all` 非原子写入，崩溃时损坏 tasks.json

**实施步骤**：

1. **修改 `src/scheduler.py`**

```python
# Before (行 326-345)
async def _run_scheduler(self, check_interval: int = 60):
    while self._running:
        now = datetime.now()
        for task in self._tasks.values():
            if not task.enabled:
                continue
            if now >= task.next_run:
                await self.execute_task(task.id)

# After
async def _run_scheduler(self, check_interval: int = 60):
    while self._running:
        now = datetime.now()
        # 复制任务列表，避免遍历中修改
        tasks_snapshot = list(self._tasks.values())
        for task in tasks_snapshot:
            if not task.enabled:
                continue
            # 新增：重叠检测
            if now >= task.next_run and task.status != "running":
                task.status = "running"  # 标记占用
                asyncio.create_task(self._execute_with_cleanup(task.id))

async def _execute_with_cleanup(self, task_id: str):
    """执行任务并在结束时清理状态"""
    try:
        await self.execute_task(task_id)
    finally:
        if task_id in self._tasks:
            self._tasks[task_id].status = "idle"
```

2. **修改 `_save_all` 原子写**（行 249）

```python
# Before
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(self._to_dict(), f, indent=2)

# After
from src.async_io import atomic_write_json
await atomic_write_json(filepath, self._to_dict())
```

**验收标准**：
- [ ] 长任务执行 5 分钟，60s 轮询只触发 1 次
- [ ] `tasks.json` 写入过程中 kill -9，文件保持完整
- [ ] 单元测试 `tests/test_scheduler.py::test_no_overlap` 通过

---

### 2.3 H-9: rate_limiter 信号量泄漏修复（0.5h）

**问题**：`rate_limiter.py:99-114` `_bucket.acquire` 抛 TimeoutError 时 `_semaphore` 未释放。

**修复**（`src/rate_limiter.py`）：

```python
# Before
async def acquire(self):
    async with self._semaphore:
        await asyncio.wait_for(
            self._bucket.acquire(),
            timeout=self.timeout
        )  # ← 异常路径信号量未释放

# After
async def acquire(self):
    await self._semaphore.acquire()
    try:
        await asyncio.wait_for(
            self._bucket.acquire(),
            timeout=self.timeout
        )
    except Exception:
        self._semaphore.release()  # 显式释放
        raise
```

**验收标准**：
- [ ] 单元测试：连续 20 次超时后，`_semaphore._value` 仍为初始值
- [ ] 压测：1000 次请求后并发度未下降

---

### 2.4 H-10: Azure 多模态适配（1h）

**问题**：`providers/azure.py` 完全未适配 vision/multimodal。

**修复**（`src/providers/azure.py`）：

1. 在 `chat()` 和 `stream_chat()` 入口加校验
```python
async def chat(self, messages, **kwargs):
    # 1. 多模态校验
    for msg in messages:
        if isinstance(msg.content, list):
            for part in msg.content:
                if part.type == "image_url":
                    self.validate_vision_capability()
    
    # 2. 消息格式转换
    formatted_messages = []
    for msg in messages:
        if isinstance(msg.content, list):
            formatted_messages.append({
                "role": msg.role,
                "content": [part.to_dict() for part in msg.content]
            })
        else:
            formatted_messages.append({
                "role": msg.role,
                "content": msg.content
            })
    
    body = {"messages": formatted_messages, **kwargs}
    ...
```

**验收标准**：
- [ ] Azure 渠道上传图片测试通过
- [ ] 与其他 Provider 行为一致

---

### 2.5 M-27: SSE 重连加重试上限 + 指数退避（1h）

**问题**：`composables/useSSE.ts:36-40` 无限重连。

**修复**（`composables/useSSE.ts`）：

```typescript
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_DELAY = 1000; // 1s
const MAX_DELAY = 30000; // 30s

function connectSSE() {
    const eventSource = new EventSource(url);
    
    eventSource.onopen = () => {
        reconnectAttempts = 0;
        sseStatus.value = 'connected';
    };
    
    eventSource.onerror = (err) => {
        eventSource.close();
        
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            // 指数退避
            const delay = Math.min(
                BASE_DELAY * Math.pow(2, reconnectAttempts),
                MAX_DELAY
            );
            sseStatus.value = `重连中 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`;
            setTimeout(connectSSE, delay);
        } else {
            sseStatus.value = '连接失败，请刷新页面';
            showToast('SSE 连接失败，已达最大重试次数', 'error');
        }
    };
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleEvent(data);
        } catch (err) {
            console.error('[SSE] 解析失败:', err, 'raw:', event.data);
            sseStatus.value = '解析错误';
        }
    };
}
```

**验收标准**：
- [ ] SSE 失败 5 次后停止重连，显示"连接失败"
- [ ] 成功后重置计数
- [ ] 重连延迟为 2s, 4s, 8s, 16s, 30s

---

### 2.6 M-28: SSE 空 catch 修复（0.5h）

**问题**：`composables/useSSE.ts:27-29` / `views/Dashboard.vue:2851` 空 catch 吞错。

**修复**：
```typescript
// Before
} catch (err) {}

// After
} catch (err) {
    console.error('[SSE] 消息解析失败:', err);
    console.error('[SSE] 原始数据:', event.data);
    sseStatus.value = '解析错误';
    showToast(`SSE 解析失败: ${err.message}`, 'warning');
}
```

**验收标准**：
- [ ] 故意发送非法 JSON 时，console 显示详细错误
- [ ] toast 提示用户

---

### 2.7 M-30: 定时器内存泄漏修复（0.5h）

**问题**：`views/Dashboard.vue:2166-2167 / 2273-2274` `mousemove`/`mouseup` 监听器未清理。

**修复**：
```typescript
// Before
document.addEventListener('mousemove', onCardDrag)
document.addEventListener('mouseup', stopCardDrag)
// onUnmounted 没有清理

// After
document.addEventListener('mousemove', onCardDrag)
document.addEventListener('mouseup', stopCardDrag)

onUnmounted(() => {
    document.removeEventListener('mousemove', onCardDrag)
    document.removeEventListener('mouseup', stopCardDrag)
    // 清理其他监听器
    document.removeEventListener('mousemove', onPanelDrag)
    document.removeEventListener('mouseup', stopPanelDrag)
    
    // 清理定时器
    if (refreshTimer) clearInterval(refreshTimer)
    if (sseReconnectTimer) clearTimeout(sseReconnectTimer)
    
    // 关闭 SSE
    if (eventSource) eventSource.close()
})
```

**验收标准**：
- [ ] 单元测试：组件 unmount 后所有监听器被移除
- [ ] Chrome DevTools Memory 快照对比：连续 10 次进入/退出 Dashboard，监听器数量不增长

---

### 2.8 M-31: fetch 状态码检查（1h）

**问题**：`views/Dashboard.vue:1877-1880` 等多处 `fetch` 未检查 `res.ok`。

**修复**：封装统一 fetch 工具（新建 `composables/useApi.ts`）

```typescript
export async function apiFetch<T = any>(
    url: string, 
    options: RequestInit = {}
): Promise<T> {
    const res = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    
    if (!res.ok) {
        const errorText = await res.text();
        throw new ApiError(
            res.status,
            errorText || res.statusText
        );
    }
    
    return res.json();
}

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(`HTTP ${status}: ${message}`);
        this.name = 'ApiError';
    }
}
```

替换所有 fetch 调用：
```typescript
// Before
const res = await fetch('/config/models', { method: 'POST', body: JSON.stringify(data) })
config.value.models = (await res.json()).models

// After
try {
    const result = await apiFetch('/config/models', { method: 'POST', body: JSON.stringify(data) })
    config.value.models = result.models
} catch (err) {
    if (err instanceof ApiError) {
        showToast(`请求失败 (${err.status}): ${err.message}`, 'error')
    } else {
        showToast(`网络错误: ${err.message}`, 'error')
    }
}
```

**验收标准**：
- [ ] Dashboard.vue 中所有 fetch 调用替换为 apiFetch
- [ ] 500 错误时显示 toast，不再崩溃
- [ ] 所有错误都有日志记录

---

### 2.9 M-8: 数据库连接池（2h）

**问题**：`src/database.py` 每次操作都新建 `sqlite3.connect()`，频繁开关连接。

**注意**：SQLite 单文件数据库连接池价值有限，可考虑：
- **方案 A**：使用 `sqlite3.connect(check_same_thread=False)` + 自定义池
- **方案 B**：使用 `aiosqlite` 异步 SQLite 驱动
- **方案 C**：保持现状（SQLite 单线程限制下优化收益小）

**推荐方案 B**：

```bash
pip install aiosqlite
echo "aiosqlite>=0.19.0" >> requirements.txt
```

```python
# src/database.py 改造
import aiosqlite

class Database:
    async def execute(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, params)
            await db.commit()
    
    async def fetchall(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                return await cursor.fetchall()
    
    async def fetchone(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                return await cursor.fetchone()
```

**验收标准**：
- [ ] 高并发（50 路测试）下不再出现 "database is locked" 错误
- [ ] 所有数据库调用改为异步
- [ ] 性能：1000 次查询耗时下降 ≥ 30%

---

### 2.10 M-16: folder_id 索引（0.5h）

**问题**：`database.py` 中 `folder_id` 未建索引，查询慢。

**修复**（新建 `migrations/add_folder_id_index.py`）：

```python
"""添加 folder_id 索引"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path("results/config.db")
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # test_cases.folder_id 索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_cases_folder_id 
        ON test_cases(folder_id)
    """)
    
    # test_results.folder_id 索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_results_folder_id 
        ON test_results(folder_id)
    """)
    
    # test_results 联合索引（用于 GROUP BY 优化）
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_test_results_group 
        ON test_results(model_name, test_case_name, folder_id)
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ folder_id 索引已创建")

if __name__ == "__main__":
    migrate()
```

**验收标准**：
- [ ] 迁移脚本执行成功
- [ ] `EXPLAIN QUERY PLAN SELECT ... WHERE folder_id = ?` 显示使用索引
- [ ] 1 万条数据下 GROUP BY 查询 < 100ms

---

## 📦 三、修改范围清单

### 3.1 新建文件（2 个）

- [ ] `model_speed_test/src/async_io.py` — 异步 I/O 工具集（H-7）
- [ ] `model_speed_test/migrations/add_folder_id_index.py` — folder_id 索引（M-16）
- [ ] `model_speed_test/frontend/src/composables/useApi.ts` — 统一 fetch 工具（M-31）

### 3.2 修改文件（10 个）

| 文件 | 改动内容 | 关联项 | 工时 |
|------|----------|--------|:----:|
| `src/recorder.py` | 12 处 `open()` → `atomic_write_json()` | H-7 | 1h |
| `src/database.py` | `sqlite3.connect()` → `aiosqlite` | H-7, M-8 | 2h |
| `src/test_case_manager.py` | 4 处 JSON 读写 → async | H-7 | 0.5h |
| `src/scheduler.py` | 加重叠检测 + 原子写 | H-8 | 2h |
| `src/logging_utils.py` | 2 处日志读写 → async | H-7 | 0.5h |
| `src/rate_limiter.py` | 信号量异常释放 | H-9 | 0.5h |
| `src/providers/azure.py` | 多模态校验 + 消息转换 | H-10 | 1h |
| `frontend/composables/useSSE.ts` | 重试上限 + 指数退避 + 错误日志 | M-27, M-28 | 1.5h |
| `frontend/views/Dashboard.vue` | 监听器清理 + fetch 改 apiFetch | M-30, M-31 | 1.5h |
| `requirements.txt` | + aiofiles / aiosqlite | H-7, M-8 | 0.1h |

---

## 📋 四、实施步骤

| 阶段 | 步骤 | 说明 | 工时 |
|------|------|------|:----:|
| **第一波** | 1. 安全检查（grep 引用） | 确认无依赖 | 5min |
| | 2. 执行清理脚本 | 删除 10 个文件 | 5min |
| | 3. 补全 `.env.example` | 追加 3 个环境变量 | 5min |
| | 4. 验证启动 | 前后端正常 | 10min |
| **第三波-P1** | 5. 添加 aiofiles 依赖 | pip install | 5min |
| | 6. 创建 `src/async_io.py` | 异步 I/O 工具 | 30min |
| | 7. 改造 recorder.py | 12 处异步化 | 1h |
| | 8. 改造 test_case_manager.py | 4 处异步化 | 0.5h |
| | 9. 改造 scheduler.py（日志） | 2 处异步化 | 0.5h |
| | 10. 改造 logging_utils.py | 2 处异步化 | 0.5h |
| **第三波-P2** | 11. scheduler 重叠检测 | H-8 | 1h |
| | 12. scheduler 原子写 | H-8 | 1h |
| | 13. rate_limiter 修复 | H-9 | 0.5h |
| | 14. Azure 多模态 | H-10 | 1h |
| **第三波-P3** | 15. SSE 重连机制 | M-27, M-28 | 1.5h |
| | 16. Dashboard 监听器清理 | M-30 | 0.5h |
| | 17. 创建 useApi 工具 | M-31 | 0.5h |
| | 18. Dashboard 改用 apiFetch | M-31 | 0.5h |
| **第三波-P4** | 19. 添加 aiosqlite 依赖 | M-8 | 5min |
| | 20. database.py 异步化 | M-8 | 1.5h |
| | 21. 添加 folder_id 索引 | M-16 | 30min |
| **测试** | 22. 单元测试 | 关键路径 | 1h |
| | 23. 压测验证 | 50 并发 | 1h |
| **收尾** | 24. 更新文档 | 代码审查报告 v3 | 0.5h |
| | 25. Git 提交 + PR | | 0.5h |
| **总计** | | | **~13.5h** |

---

## 🎯 五、验收标准

### 功能性
- [ ] 所有现有功能正常（CRUD 测试、文件夹管理、报告导出等）
- [ ] 第一波清理后无报错
- [ ] 第三波优化后无回归 bug

### 性能指标
- [ ] 并发 50 路测试不出现 "database is locked"
- [ ] 1000 用例 × 5 轮测试，整体耗时下降 ≥ 20%
- [ ] 调度器长任务无重复触发（手动验证 5 分钟任务执行 1 次）
- [ ] SSE 失败 5 次后优雅停止
- [ ] 50 并发下 SSE 无延迟累积

### 稳定性
- [ ] `tasks.json` 写入过程 kill -9 文件保持完整
- [ ] rate_limiter 1000 次超时后并发度不下降
- [ ] Dashboard 进入/退出 10 次无内存增长（Chrome DevTools Memory）

### 可观测性
- [ ] 所有 SSE 错误有 console.error 日志
- [ ] 所有 fetch 失败有 toast 提示 + 日志
- [ ] 数据库慢查询（>100ms）有 warning 日志

---

## ⚠️ 六、风险点与回滚方案

### 6.1 风险矩阵

| 风险项 | 等级 | 缓解措施 |
|--------|:----:|----------|
| async/await 改错导致死锁 | 🟠 高 | 保留原函数做 wrapper，逐步切换 |
| 数据库迁移失败 | 🟡 中 | 备份 `results/config.db` 后执行 |
| SSE 重试机制破坏正常连接 | 🟡 中 | 单次成功后立即重置计数 |
| aiosqlite 与现有 sqlite3 行为差异 | 🟢 低 | 全量回归测试 |

### 6.2 回滚方案

```bash
# 整体回滚
git revert <commit-hash>

# 数据库回滚（迁移前已备份）
cp results/config.db.backup results/config.db

# 单独回滚某个改动
git checkout HEAD~1 -- model_speed_test/src/recorder.py
```

### 6.3 备份策略

```bash
# 实施前备份
cp results/config.db results/config.db.backup_$(date +%Y%m%d_%H%M%S)
cp model_speed_test/tasks.json model_speed_test/tasks.json.backup 2>/dev/null

# git tag 标记版本
git tag -a "before-perf-optimization" -m "性能优化前快照"
```

---

## 📐 七、并行实施策略

由于部分任务互不依赖，可并行开发：

```
Phase 1（第一波）：单人顺序执行（5min）
       ↓
Phase 2-P1（async I/O）：1 人，4h
Phase 2-P2（调度器）：1 人，2h  ← 可与 P1 并行
Phase 2-P3（SSE/前端）：1 人，3h  ← 可与 P1/P2 并行
       ↓
Phase 3（数据库）：1 人，2h  ← 依赖 P2-P1
Phase 4（索引）：0.5h  ← 依赖 Phase 3
       ↓
Phase 5（测试）：1 人，2h
```

**串行总工时**：~13.5h
**3 人并行总工时**：~6h（理论值）

---

## 🏗️ 八、架构影响分析

### 8.1 性能提升预估

| 模块 | 当前 | 优化后 | 提升 |
|------|------|--------|:----:|
| recorder.save() | 50ms / call（阻塞） | 5ms（异步） | 10x |
| 调度器调度精度 | ±60s | ±1s | 60x |
| 数据库查询吞吐 | 100 QPS | 1000 QPS | 10x |
| SSE 连接稳定性 | 偶发断开 | 自动恢复 5 次 | ↑ |
| Dashboard 内存 | 持续增长 | 稳定 | ↑ |

### 8.2 代码质量影响

| 维度 | 当前 | 优化后 |
|------|------|--------|
| 同步阻塞点 | 30+ | 0 |
| 内存泄漏 | 5 处 | 0 |
| 错误处理缺失 | 20+ 处 | 0 |
| 单元测试覆盖 | < 5% | ~ 30% |

---

## 📊 九、监控指标

实施后需在生产环境观察的关键指标：

1. **P99 延迟**：`/test/start` P99 < 200ms
2. **错误率**：5xx < 0.1%
3. **内存使用**：Dashboard 长时间运行（24h）内存 < 200MB
4. **数据库连接**：活跃连接数 < 10
5. **调度任务丢失率**：0%（原子写保证）

---

## ✅ 十、最终交付清单

- [ ] 全部代码改动提交到 git
- [ ] 更新 README.md（如有新环境变量）
- [ ] 更新 API 文档
- [ ] 性能基准报告（Before / After 对比）
- [ ] 单元测试覆盖率报告
- [ ] 数据库迁移执行记录
- [ ] 代码审查报告 v3（验证修复情况）

---

## 📅 十一、时间表

| 日期 | 阶段 | 负责人 |
|------|------|--------|
| Day 1 上午 | 第一波清理 | TBD |
| Day 1 下午 | Phase 2-P1（async I/O） | TBD |
| Day 2 上午 | Phase 2-P2（调度器） + Phase 2-P3（SSE） | TBD |
| Day 2 下午 | Phase 3（数据库）+ Phase 4（索引） | TBD |
| Day 3 上午 | Phase 5（测试） + 验收 | TBD |
| Day 3 下午 | 文档 + 提交 | TBD |

---

## 🔗 十二、关联文档

- `代码审查报告-2026-06-24.md` — 本方案问题来源
- `result.md` — 第一轮审查报告（2026-05-21）
- `MODIFICATION_REPORT.md` — 历史修改记录
- `业务流程文档.md` — 业务背景

---

*计划制定时间：2026-06-24 14:24*
*预计开始时间：待定*
*预计完成时间：3 个工作日内*
*风险等级：🟡 中（需压测验证）*