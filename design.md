<!--
 * @Date: 2026-06-30 08:45
 * @LastEditors: Cline
 * @LastEditTime: 2026-06-30 08:45
 * @FilePath: /模型速度测试/design.md
-->

# AI 模型速度测试平台 — 优化修复开发方案

> **方案来源**：2026-06-29 独立代码审查（209 条问题：🔴68 / 🟠81 / 🟢60）
> **制定时间**：2026-06-30
> **预计总工时**：~80h（可分阶段执行）
> **风险等级**：🟡 中（需分阶段验证）

---

## 📋 一、方案总览

### 1.1 四阶段路线图

```
Phase 0: 紧急止血（4h）        → 修复崩溃 Bug + 安全漏洞
     ↓
Phase 1: 安全加固（12h）       → 认证、脱敏、加密、CORS
     ↓
Phase 2: 性能与稳定性（20h）   → 异步 I/O、竞态修复、内存泄漏
     ↓
Phase 3: 架构重构（44h）       → Dashboard 拆分、双套系统统一、测试覆盖
```

### 1.2 问题覆盖矩阵

| 阶段 | 覆盖问题数 | 🔴 | 🟠 | 🟢 | 工时 |
|------|:------:|:--:|:--:|:--:|:----:|
| Phase 0 紧急止血 | 15 | 15 | 0 | 0 | 4h |
| Phase 1 安全加固 | 22 | 16 | 6 | 0 | 12h |
| Phase 2 性能与稳定性 | 48 | 18 | 30 | 0 | 20h |
| Phase 3 架构重构 | 64 | 19 | 25 | 20 | 44h |
| 后续低优 | 60 | 0 | 20 | 40 | — |
| **合计** | **209** | **68** | **81** | **60** | **~80h** |

---

## 🔥 二、Phase 0：紧急止血（4h）

> **目标**：修复所有会导致程序崩溃的 Bug 和最高危安全漏洞
> **原则**：最小改动、最快见效、零回归风险

### 2.1 崩溃级 Bug 修复（5 项，2h）

#### P0-1. `main.py:1412` — `NameError: all_results 未定义`

**位置**：`model_speed_test/main.py` 的 `run_tests_with_web()` 函数

**问题**：
```python
# L1412 — all_results 未在该函数中定义
all_results[client.name] = client_results  # ← NameError
```

**修复**：
```python
# 在 run_tests_with_web() 函数开头添加
all_results = {}
```

**工时**：0.2h

---

#### P0-2. `main.py:761` — `AttributeError: eval_manager 不存在`

**位置**：`model_speed_test/main.py` 的测试类 `__init__` 方法

**问题**：`self.eval_manager` 属性从未在 `__init__` 中初始化，但 `run()` 方法中引用了它。

**修复**：
```python
# 在 __init__ 中添加
self.eval_manager = None  # 或按设计意图初始化
```

**工时**：0.3h

---

#### P0-3. `main.py:58-68` — `EOFError: input() 在非交互环境崩溃`

**位置**：`model_speed_test/main.py` 的 `setup_logging()` 函数

**问题**：
```python
# L58-68 — 交互式 input() 在 CI/管道/Docker 中抛 EOFError
should_log = input("是否创建日志文件? (y/N): ").lower() == 'y'
```

**修复**：
```python
# 改为通过环境变量或命令行参数控制
import os
should_log = os.getenv("ENABLE_FILE_LOGGING", "").lower() in ("1", "true", "yes")
# 或通过命令行参数 --log-file 控制
```

**工时**：0.3h

---

#### P0-4. `database.py:528-537` — 空列表生成非法 SQL

**位置**：`model_speed_test/src/database.py` 的 `search_groups()` 方法

**问题**：
```python
# rows 为空时生成 WHERE id IN () — 非法 SQL
rows = cursor.execute(
    f"SELECT * FROM test_groups WHERE id IN ({','.join(['?'] * len(rows))})",
    tuple(id_list)
).fetchall()
```

**修复**：
```python
if not id_list:
    return []
placeholders = ','.join(['?'] * len(id_list))
rows = cursor.execute(
    f"SELECT * FROM test_groups WHERE id IN ({placeholders})",
    tuple(id_list)
).fetchall()
```

**工时**：0.2h

---

#### P0-5. `App.vue` — 缺少 `<router-view />` 导致路由不可达

**位置**：`model_speed_test/frontend/src/App.vue`

**问题**：`<template>` 中缺少 `<router-view />`，导致 `/test`、`/history`、`/settings` 路由永远不可达。

**修复**：
```vue
<template>
  <div id="app">
    <router-view />
  </div>
</template>
```

**工时**：0.5h

---

### 2.2 高危安全漏洞修复（3 项，2h）

#### P0-6. SSL 证书验证恢复

**位置**：`model_speed_test/src/providers/openai.py` 及旧版 `gemini.py`

**问题**：
```python
ssl_context = ssl.create_default_context()
ssl_context.verify_mode = ssl.CERT_NONE      # ← 完全禁用 SSL 验证
ssl_context.check_hostname = False           # ← 接受中间人攻击
```

**修复**：
```python
import ssl
ssl_context = ssl.create_default_context()  # 使用系统默认证书验证
# 仅对本地自签名服务允许可选跳过（通过环境变量控制）
if os.getenv("ALLOW_INSECURE_SSL", "").lower() == "true":
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
```

**工时**：0.5h

---

#### P0-7. 数据库迁移异常处理

**位置**：`model_speed_test/src/database.py` 的 `_migrate()` 方法

**问题**：
```python
try:
    cursor.execute("ALTER TABLE test_groups ADD COLUMN folder_id TEXT")
except sqlite3.OperationalError:
    pass  # ← 磁盘满、权限错误全部静默吞掉
```

**修复**：
```python
cursor.execute("PRAGMA table_info(test_groups)")
existing_cols = {row[1] for row in cursor.fetchall()}
if "folder_id" not in existing_cols:
    cursor.execute("ALTER TABLE test_groups ADD COLUMN folder_id TEXT")
```

**工时**：0.5h

---

#### P0-8. Provider 注册系统死代码清理

**位置**：
- `model_speed_test/src/providers/__init__.py`（两个版本的注册函数）
- `model_speed_test/src/providers/registry.py`（两个互不一致的 ProviderManager）

**修复**：删除旧版死代码，统一使用新版实现。

**工时**：1h

---

## 🛡️ 三、Phase 1：安全加固（12h）

> **目标**：消除安全漏洞，建立完整的认证和脱敏体系

### 3.1 API 认证启用（4h）

#### P1-1. 为所有写操作端点添加认证

**位置**：`model_speed_test/web/app.py`

**当前状态**：`require_auth()` 函数已定义但从未被任何端点引用（39 个路由全部裸奔）。

**修复方案**：

```python
# Step 1: 改造 require_auth 为标准的 FastAPI Depends
from fastapi import Depends, HTTPException, Request
import os

async def require_auth(request: Request) -> bool:
    """API 认证中间件"""
    api_key = os.getenv("WEB_API_KEY", "")
    if not api_key:
        return True  # 未配置时兼容开发环境
    provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

# Step 2: 对所有写操作端点添加依赖
@app.post("/config/models", dependencies=[Depends(require_auth)])
@app.put("/config/models/{model_name}", dependencies=[Depends(require_auth)])
@app.delete("/config/models/{model_name}", dependencies=[Depends(require_auth)])
@app.post("/config/test-cases", dependencies=[Depends(require_auth)])
@app.put("/config/test-cases/{case_id}", dependencies=[Depends(require_auth)])
@app.delete("/config/test-cases/{case_id}", dependencies=[Depends(require_auth)])
@app.post("/test/start", dependencies=[Depends(require_auth)])
@app.post("/test/stop", dependencies=[Depends(require_auth)])
@app.delete("/api/history/{group_id}", dependencies=[Depends(require_auth)])
# ... 所有其他写操作端点
```

**工时**：2h

---

#### P1-2. 前端适配认证头

**位置**：`model_speed_test/frontend/src/composables/useApi.ts`（新建）

```typescript
// 新建统一 API 请求工具
const API_KEY = import.meta.env.VITE_WEB_API_KEY || ''

export async function apiFetch<T = any>(
    url: string,
    options: RequestInit = {}
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(API_KEY && { 'X-API-Key': API_KEY }),
        ...(options.headers as Record<string, string> || {}),
    }

    const res = await fetch(url, { ...options, headers })

    if (!res.ok) {
        const errorText = await res.text().slice(0, 500)
        throw new ApiError(res.status, errorText || res.statusText)
    }

    return res.json()
}

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(`HTTP ${status}: ${message}`)
        this.name = 'ApiError'
    }
}
```

**工时**：1h

---

#### P1-3. 配置 CORS 限制来源

**位置**：`model_speed_test/web/app.py`

```python
from fastapi.middleware.cors import CORSMiddleware
import os

ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

**工时**：0.5h

---

#### P1-4. 环境变量补全

**位置**：`model_speed_test/.env.example`

```bash
# 追加
WEB_API_KEY=
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
ALLOW_INSECURE_SSL=false
```

**工时**：0.1h

---

### 3.2 API Key 全链路脱敏（4h）

#### P1-5. Provider 基类添加脱敏方法

**位置**：`model_speed_test/src/providers/base.py`

```python
import re

class BaseProvider:
    @staticmethod
    def _sanitize_error_text(text: str, max_length: int = 500) -> str:
        """脱敏 API Key、Token、敏感 Header"""
        if not text:
            return text

        # Bearer token
        text = re.sub(r'(Bearer\s+)[A-Za-z0-9\-_\.]{8,}', r'\1***MASKED***', text)
        # x-api-key header
        text = re.sub(
            r'(x-api-key["\']?\s*[:=]\s*)[A-Za-z0-9\-_\.]{8,}',
            r'\1***MASKED***',
            text,
            flags=re.IGNORECASE
        )
        # query string key=
        text = re.sub(r'([?&]key=)[A-Za-z0-9\-_\.]{8,}', r'\1***MASKED***', text)
        # sk- prefix keys
        text = re.sub(r'\bsk-[A-Za-z0-9]{8,}\b', 'sk-***MASKED***', text)

        if len(text) > max_length:
            text = text[:max_length] + "...[truncated]"
        return text
```

**工时**：0.5h

---

#### P1-6. 5 个 Provider 统一使用脱敏方法

**影响文件**：`openai.py`、`anthropic.py`、`gemini.py`、`azure.py`、`local.py`

**修复模式**：
```python
# Before（5 个 Provider 全都这样写）
error_text = await response.text()
logger.error(f"[Provider] API error: {response.status} - {error_text}")
return LLMResponse(
    error=f"API error {response.status}: {error_text}",  # ← 原样泄露
    raw_response={"status": response.status, "body": error_text}
)

# After
error_text = await response.text()
sanitized = self._sanitize_error_text(error_text)
logger.error(f"[{self.__class__.__name__}] API error {response.status}: {sanitized}")
return LLMResponse(
    error=f"API error {response.status}: {sanitized}",
    raw_response={"status": response.status}  # 不含 body
)
```

**工时**：1.5h

---

#### P1-7. Gemini API Key 改用 Header 传递

**位置**：`model_speed_test/src/providers/gemini.py`

**问题**：
```python
# L167-168 — Key 在 URL query string 泄露
params = {"key": self.config.api_key}
```

**修复**：
```python
# 改用 HTTP Header
headers = {"x-goog-api-key": self.config.api_key}
async with session.post(url, json=body, headers=headers) as response:
    ...
```

**工时**：1h

---

#### P1-8. SQL 注入修复

**位置**：`model_speed_test/web/app.py` 的 `update_model()` 端点

**问题**：
```python
# f-string 动态拼接 SQL 字段名
sql = f"UPDATE models SET {field} = ? WHERE name = ?"
```

**修复**：
```python
# 白名单校验
ALLOWED_FIELDS = {"api_key", "base_url", "model_id", "temperature", "max_tokens"}
if field not in ALLOWED_FIELDS:
    raise HTTPException(status_code=400, detail=f"Invalid field: {field}")
sql = f"UPDATE models SET {field} = ? WHERE name = ?"
```

**工时**：0.5h

---

### 3.3 Webhook Secret 加密存储（2h）

#### P1-9. 引入加密存储

**位置**：`model_speed_test/src/scheduler.py`

**修复**：
```python
from cryptography.fernet import Fernet
import os

class SecretCipher:
    """敏感字段加密/解密"""
    def __init__(self):
        key = os.getenv("SECRET_ENCRYPTION_KEY")
        if not key:
            key = Fernet.generate_key().decode()
            print("[WARN] 未设置 SECRET_ENCRYPTION_KEY，使用临时密钥（重启后失效）")
        self._cipher = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ciphertext
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ciphertext  # 兼容历史明文数据

# 使用
_cipher = SecretCipher()
task = ScheduledTask(
    webhook_secret=_cipher.encrypt(task_data.get("webhook_secret"))
    if task_data.get("webhook_secret") else None
)
```

**工时**：1.5h

---

### 3.4 条件竞争修复（2h）

#### P1-10. recorder.py manifest 竞态修复

**位置**：`model_speed_test/src/recorder.py`

**问题**：多个协程同时 read-modify-write manifest.json，后写覆盖先写。

**修复**：
```python
import asyncio

class IORecorder:
    def __init__(self):
        self._manifest_lock = asyncio.Lock()

    async def _update_manifest(self, key: str, value: Any):
        async with self._manifest_lock:
            # 在锁内完成 read → modify → write
            manifest = await self._read_manifest()
            manifest[key] = value
            await self._write_manifest(manifest)

    async def _read_manifest(self) -> dict:
        try:
            async with aiofiles.open(self.manifest_file, "r") as f:
                return json.loads(await f.read())
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            # 区分 FileNotFound 和损坏：损坏时备份后重置
            import shutil
            shutil.copy2(self.manifest_file, f"{self.manifest_file}.corrupted.{int(time.time())}")
            return {}
```

**工时**：1h

---

#### P1-11. database.py 单例线程安全

**位置**：`model_speed_test/src/database.py`

**修复**：
```python
import threading

_lock = threading.Lock()
_instance = None

def get_database() -> Database:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:  # double-check
                _instance = Database()
    return _instance
```

**工时**：0.5h

---

## ⚡ 四、Phase 2：性能与稳定性（20h）

> **目标**：消除阻塞点、修复并发 Bug、防止内存泄漏

### 4.1 异步 I/O 全面改造（8h）

#### P2-1. 创建异步 I/O 工具模块

**新建文件**：`model_speed_test/src/async_io.py`

```python
"""异步文件 I/O 工具集"""
import asyncio
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import aiofiles

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async-io")

async def read_json(path: str) -> Any:
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return json.loads(await f.read())
    except FileNotFoundError:
        return None

async def write_json(path: str, data: Any, indent: int = 2) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)

async def atomic_write_json(path: str, data: Any, indent: int = 2) -> None:
    """原子写入：写临时文件 → rename（POSIX 原子操作）"""
    content = json.dumps(data, ensure_ascii=False, indent=indent)
    dir_path = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

async def run_in_executor(func, *args, **kwargs):
    """在后台线程执行同步函数（用于 sqlite3 等）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args, **kwargs)
```

**工时**：1h

---

#### P2-2. recorder.py 同步 I/O → 异步

**位置**：`model_speed_test/src/recorder.py`

**改造清单**（12 处 `open()` + `json.dump()`）：

| 原代码 | 改为 |
|--------|------|
| `with open(path, "w") as f: json.dump(data, f)` | `await async_io.write_json(path, data)` |
| `with open(path, "r") as f: data = json.load(f)` | `data = await async_io.read_json(path)` |
| 关键路径（manifest 写入） | `await async_io.atomic_write_json(path, data)` |

**工时**：2h

---

#### P2-3. database.py 改为 aiosqlite

**位置**：`model_speed_test/src/database.py`

**改造方式**：
```python
import aiosqlite

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def execute(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, params)
            await db.commit()

    async def fetchall(self, sql: str, params: tuple = ()) -> list:
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

**工时**：3h

---

#### P2-4. test_case_manager.py / scheduler.py / logging_utils.py 异步化

**影响文件**：
- `test_case_manager.py`：4 处 JSON 读写
- `scheduler.py`：`tasks.json` 读写（改为 `atomic_write_json`）
- `logging_utils.py`：日志文件写入

**工时**：2h

---

### 4.2 调度器增强（3h）

#### P2-5. 重叠检测

**位置**：`model_speed_test/src/scheduler.py`

```python
async def _run_scheduler(self, check_interval: int = 60):
    while self._running:
        now = datetime.now()
        tasks_snapshot = list(self._tasks.values())  # 复制避免遍历中修改
        for task in tasks_snapshot:
            if not task.enabled:
                continue
            if now >= task.next_run and task.status != "running":
                task.status = "running"
                asyncio.create_task(self._execute_with_cleanup(task.id))
        await asyncio.sleep(check_interval)

async def _execute_with_cleanup(self, task_id: str):
    """执行任务并在结束时清理状态"""
    try:
        await self.execute_task(task_id)
    finally:
        if task_id in self._tasks:
            self._tasks[task_id].status = "idle"
```

**工时**：1.5h

---

#### P2-6. tasks.json 原子写入

**位置**：`model_speed_test/src/scheduler.py`

```python
# Before
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(self._to_dict(), f, indent=2)

# After
from src.async_io import atomic_write_json
await atomic_write_json(filepath, self._to_dict())
```

**工时**：1h

---

#### P2-7. 调度器异常时状态恢复

确保 `execute_task` 任何异常路径都会将任务状态从 "running" 恢复为 "idle"。

**工时**：0.5h

---

### 4.3 rate_limiter 信号量泄漏修复（1h）

#### P2-8. 显式释放信号量

**位置**：`model_speed_test/src/rate_limiter.py`

```python
# Before
async def acquire(self):
    async with self._semaphore:
        await asyncio.wait_for(
            self._bucket.acquire(),
            timeout=self.timeout
        )  # ← TimeoutError 时信号量泄漏

# After
async def acquire(self):
    await self._semaphore.acquire()
    try:
        await asyncio.wait_for(
            self._bucket.acquire(),
            timeout=self.timeout
        )
    except Exception:
        self._semaphore.release()
        raise
```

**工时**：0.5h

---

### 4.4 前端内存泄漏修复（4h）

#### P2-9. 事件监听器清理

**位置**：`model_speed_test/frontend/src/views/Dashboard.vue`

```typescript
onUnmounted(() => {
    // 清理拖拽监听器
    document.removeEventListener('mousemove', onCardDrag)
    document.removeEventListener('mouseup', stopCardDrag)
    document.removeEventListener('mousemove', onPanelDrag)
    document.removeEventListener('mouseup', stopPanelDrag)

    // 清理定时器
    if (refreshTimer) clearInterval(refreshTimer)
    if (sseReconnectTimer) clearTimeout(sseReconnectTimer)

    // 关闭 SSE 连接
    if (eventSource) eventSource.close()
})
```

**工时**：1h

---

#### P2-10. SSE 重连策略优化

**位置**：`model_speed_test/frontend/src/composables/useSSE.ts`

```typescript
const MAX_RECONNECT_ATTEMPTS = 5
const BASE_DELAY = 1000  // 1s
const MAX_DELAY = 30000  // 30s
let reconnectAttempts = 0

function connectSSE() {
    const es = new EventSource(url)

    es.onopen = () => {
        reconnectAttempts = 0
        status.value = 'connected'
    }

    es.onerror = () => {
        es.close()
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            status.value = '连接失败，请刷新页面'
            return
        }
        reconnectAttempts++
        const delay = Math.min(BASE_DELAY * Math.pow(2, reconnectAttempts), MAX_DELAY)
        status.value = `重连中 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`
        setTimeout(connectSSE, delay)
    }

    es.onmessage = (event) => {
        try {
            handleEvent(JSON.parse(event.data))
        } catch (err) {
            console.error('[SSE] 解析失败:', err, 'raw:', event.data)
        }
    }
}
```

**工时**：1h

---

#### P2-11. 日志缓冲区上限

**位置**：`model_speed_test/frontend/src/composables/useLogs.ts`

```typescript
const MAX_LOG_ENTRIES = 10000

function addLog(entry: LogEntry) {
    logs.value.push(entry)
    if (logs.value.length > MAX_LOG_ENTRIES) {
        logs.value = logs.value.slice(-MAX_LOG_ENTRIES)  // 保留最新
    }
}
```

**工时**：0.5h

---

#### P2-12. fetch 统一错误处理

**位置**：使用 Phase 1 创建的 `useApi.ts` 替换所有裸 `fetch` 调用：

```typescript
// Before（Dashboard.vue 多处）
const res = await fetch('/config/models')
const data = await res.json()  // ← 未检查 res.ok

// After
try {
    const data = await apiFetch('/config/models')
} catch (err) {
    if (err instanceof ApiError) {
        showToast(`请求失败 (${err.status}): ${err.message}`, 'error')
    } else {
        showToast(`网络错误: ${err.message}`, 'error')
    }
}
```

**工时**：1.5h

---

### 4.5 数据库优化（3h）

#### P2-13. folder_id 索引

**新建文件**：`model_speed_test/migrations/add_indexes.py`

```python
"""添加性能索引"""
import sqlite3
from pathlib import Path

def migrate():
    db_path = Path("results/config.db")
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_test_cases_folder_id ON test_cases(folder_id)",
        "CREATE INDEX IF NOT EXISTS idx_test_results_folder_id ON test_results(folder_id)",
        "CREATE INDEX IF NOT EXISTS idx_test_results_model_case ON test_results(model_name, test_case_name)",
        "CREATE INDEX IF NOT EXISTS idx_test_groups_created ON test_groups(created_at)",
    ]

    for sql in indexes:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError as e:
            print(f"[WARN] 索引创建跳过: {e}")

    conn.commit()
    conn.close()
    print("✅ 索引已创建")

if __name__ == "__main__":
    migrate()
```

**工时**：0.5h

---

#### P2-14. 列表端点添加分页

**位置**：`model_speed_test/web/app.py`

```python
@app.get("/api/history")
async def list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    offset = (page - 1) * page_size
    total = await db.fetchone("SELECT COUNT(*) as cnt FROM test_groups")
    items = await db.fetchall(
        "SELECT * FROM test_groups ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    )
    return {
        "items": items,
        "total": total["cnt"],
        "page": page,
        "page_size": page_size,
    }
```

**工时**：1h

---

#### P2-15. 添加 health check 端点

**位置**：`model_speed_test/web/app.py`

```python
@app.get("/health")
async def health_check():
    try:
        db = get_database()
        await db.fetchone("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "timestamp": datetime.now().isoformat(),
    }
```

**工时**：0.5h

---

#### P2-16. SSE 连接数限制

**位置**：`model_speed_test/web/emitter.py`

```python
MAX_SSE_CONNECTIONS = 100
_active_connections = 0

async def event_stream(request: Request):
    global _active_connections
    if _active_connections >= MAX_SSE_CONNECTIONS:
        raise HTTPException(status_code=503, detail="Too many SSE connections")

    _active_connections += 1
    try:
        # ... SSE 逻辑
        yield
    finally:
        _active_connections -= 1
```

**工时**：0.5h

---

### 4.6 依赖补全（1h）

#### P2-17. requirements.txt 补全

**位置**：`model_speed_test/requirements.txt`

```txt
# 追加
python-dotenv>=1.0.0
aiofiles>=23.0.0
aiosqlite>=0.19.0
cryptography>=41.0.0

# 移除已废弃依赖
# fastapi-utils（最后更新 2022 年，改为手动实现）
```

**工时**：0.5h

---

#### P2-18. start.sh 修正

```bash
# python → python3
python3 main.py "$@"

# 添加依赖检查
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "❌ 请先安装依赖: pip install -r requirements.txt"
    exit 1
fi
```

**工时**：0.5h

---

## 🏗️ 五、Phase 3：架构重构（44h）

> **目标**：解决代码腐化问题，建立可持续的工程基础

### 5.1 Dashboard.vue 拆分（16h）

**目标**：7512 行 → ~800 行编排层 + 子组件各司其职

#### P3-1. 拆分策略

```
views/Dashboard.vue (编排层，~800 行)
├── <DashboardHeader />           — 已存在，直接引用
├── <DashboardSidebar />          — 已存在，直接引用
├── <TaskGrid />                  — 新建，替代内联 task cards
│   └── <TaskCard />              — 已存在
├── <LogPanel />                  — 已存在，直接引用
├── <AiAnalysisModal />           — 新建，替代内联 AI 弹窗
├── <TaskDetailModal />           — 已存在
├── <StartConfigModal />          — 已存在
├── <ReportPreviewModal />        — 已存在
└── <div> 弹窗层（状态驱动）</div>
```

**分步执行**：

| 步骤 | 内容 | 工时 |
|------|------|:----:|
| 1 | 抽取 AI 分析为 `AiAnalysisModal.vue` | 3h |
| 2 | 抽取卡片网格为 `TaskGrid.vue` | 3h |
| 3 | 抽取拖拽缩放为 `composables/useDragResize.ts` | 3h |
| 4 | 抽取 Markdown 渲染为独立组件 | 2h |
| 5 | 重构 Dashboard.vue 编排层 | 3h |
| 6 | 删除未使用的子组件代码 | 2h |

**工时**：16h

---

### 5.2 TypeScript 类型完善（8h）

#### P3-2. 消除 `any` 类型

```typescript
// Before
const tasks = ref<any>([])
const currentTask = ref<any>(null)

// After
interface Task {
    id: string
    name: string
    status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
    modelIds: string[]
    testCaseIds: string[]
    rounds: number
    concurrency: number
    createdAt: string
    results?: TestResult[]
}

const tasks = ref<Task[]>([])
const currentTask = ref<Task | null>(null)
```

**改动范围**：`Dashboard.vue`、`useTasks.ts`、`useConfig.ts`、`useLogs.ts`、`useSSE.ts`

**工时**：8h

---

### 5.3 Provider 系统统一（6h）

#### P3-3. 双套架构合并

**问题**：现有两套 Provider 注册系统：
- `__init__.py` 中有旧版注册函数（死代码）
- `registry.py` 有两个互不一致的 ProviderManager

**统一方案**：

```python
# 删除 __init__.py 中旧版 _register_all_providers()（L17-38）
# 保留新版实现（L44-73）

# 重构 registry.py：统一为一个 ProviderRegistry
class ProviderRegistry:
    """统一的 Provider 注册中心"""
    _providers: Dict[str, Type[BaseProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: Type[BaseProvider]):
        cls._providers[name] = provider_cls

    @classmethod
    def get(cls, name: str) -> Type[BaseProvider]:
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(cls._providers.keys())}")
        return cls._providers[name]

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls._providers.keys())
```

**工时**：6h

---

### 5.4 SDK 修复（4h）

#### P3-4. JS SDK — fetch-based SSE 实现

**位置**：`model_speed_test/sdk/javascript/index.js`

**问题**：`new EventSource(url, { headers })` 在浏览器标准 API 中无效。

**修复**：
```javascript
class BenchmarkClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl
        this.apiKey = apiKey
    }

    async streamTest(config, onEvent) {
        const response = await fetch(`${this.baseUrl}/test/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': this.apiKey,
            },
            body: JSON.stringify(config),
        })

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${await response.text()}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop()

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6).trim()
                    if (data === '[DONE]') return
                    onEvent(JSON.parse(data))
                }
            }
        }
    }
}

// 统一导出为 ESM
export default BenchmarkClient
```

**工时**：2h

---

#### P3-5. Python SDK — 连接泄漏修复

**位置**：`model_speed_test/sdk/python/__init__.py`

**问题**：`events()` 生成器中 `requests.get(stream=True)` 的 Response 无法被自动关闭。

**修复**：
```python
def events(self, config: dict):
    """使用 context manager 确保连接关闭"""
    with requests.post(
        f"{self.base_url}/test/start",
        json=config,
        headers={"X-API-Key": self.api_key},
        stream=True,
        timeout=self.timeout
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:].strip()
                    if data == '[DONE]':
                        return
                    yield json.loads(data)
```

**工时**：1h

---

#### P3-6. SDK 示例代码更新

- `sdk/javascript/example.js`：更新模型名、使用新版 API
- `sdk/python/example.py`：同上

**工时**：1h

---

### 5.5 测试覆盖补充（8h）

#### P3-7. 新建测试文件

| 文件 | 覆盖模块 | 工时 |
|------|---------|:----:|
| `tests/test_database.py` | 数据库 CRUD、迁移、并发 | 2h |
| `tests/test_providers.py` | 5 个 Provider mock 测试 | 2h |
| `tests/test_scheduler.py` | 调度器、重叠检测 | 1.5h |
| `tests/test_web_api.py` | FastAPI TestClient 端到端 | 1.5h |
| `tests/test_tester.py` | 测试执行器 | 1h |

**示例测试**：
```python
# tests/test_scheduler.py
import pytest
import asyncio
from src.scheduler import Scheduler

@pytest.mark.asyncio
async def test_no_overlap_during_long_task():
    """长任务执行中，下次轮询不应重复触发"""
    scheduler = Scheduler()
    call_count = 0

    async def slow_task():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(2)

    task = ScheduledTask(id="t1", name="slow", cron="* * * * *", callback=slow_task)
    scheduler.add_task(task)

    await scheduler.start()
    await asyncio.sleep(3)
    await scheduler.stop()

    assert call_count == 1, f"期望执行 1 次，实际 {call_count} 次"


@pytest.mark.asyncio
async def test_rate_limiter_no_semaphore_leak():
    """连续超时后信号量不应泄漏"""
    limiter = RateLimiter(max_concurrent=5, timeout=0.001)
    for _ in range(100):
        try:
            await limiter.acquire()
        except asyncio.TimeoutError:
            pass
    assert limiter._semaphore._value == 5  # 初始值不变
```

**工时**：8h

---

### 5.6 代码清理（2h）

#### P3-8. 删除冗余文件

```bash
# 备份文件
rm model_speed_test/src/tester.py.bak
rm model_speed_test/src/recorder.py.bak
rm model_speed_test/frontend/src/views/History.vue.bak

# 无关文档
rm 提示词.md 提示词.html UI评估报告-Cline界面.md

# 根目录冗余
rm model_speed_test/package.json
rm model_speed_test/test_lmstudio_debug.py
rm model_speed_test/debug_dsv4_stream.py
rm scripts/test_dsv4_stream_output.txt

# 重复文档（合并后删除）
# MODIFICATION_REPORT.md → 合并入 代码审查报告.md
# 代码审查报告.md → 合并入 result.md
```

**工时**：0.5h

---

#### P3-9. `stop.sh` 改用 PID 文件

```bash
#!/bin/bash
PID_FILE="model_speed_test/server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "✅ 服务器已停止 (PID: $PID)"
        rm "$PID_FILE"
    else
        echo "⚠️  PID 文件存在但进程不存在，清理中..."
        rm "$PID_FILE"
    fi
else
    echo "⚠️  未找到 PID 文件"
fi
```

**工时**：0.5h

---

#### P3-10. 日志文件名改用时间戳

**位置**：`model_speed_test/src/logging_utils.py`

```python
# Before
log_filename = Path(__file__).stat().st_mtime  # 文件修改时间，无意义

# After
from datetime import datetime
log_filename = datetime.now().strftime("test_run_%Y%m%d_%H%M%S.log")
```

**工时**：0.5h

---

## 📐 六、实施计划总表

| 阶段 | 内容 | 工时 | 依赖 | 并行度 |
|------|------|:----:|------|:------:|
| **Phase 0** | 崩溃修复 + 高危安全 | 4h | — | 串行 |
| **Phase 1** | 安全加固 | 12h | Phase 0 | 部分并行 |
| **Phase 2** | 性能与稳定性 | 20h | Phase 1 | 可并行 |
| **Phase 3** | 架构重构 | 44h | Phase 2 | 可并行 |
| **合计** | | **~80h** | | |

### 并行策略

```
Day 1: Phase 0（全员串行，4h）
       ↓
Day 2-3: Phase 1
       ├─ 后端安全（认证/脱敏/SQL注入）— 8h
       └─ 前端安全（CORS/useApi）        — 4h
       ↓
Day 4-6: Phase 2
       ├─ 异步 I/O 改造（后端）           — 8h
       ├─ 调度器 + rate_limiter（后端）   — 4h
       └─ 前端内存泄漏 + SSE（前端）      — 8h
       ↓
Day 7-12: Phase 3
       ├─ Dashboard 拆分（前端）          — 16h
       ├─ Provider 统一（后端）           — 6h
       ├─ SDK 修复（全栈）                — 4h
       ├─ 测试补充（全栈）                — 8h
       └─ TypeScript 类型（前端）         — 8h
```

---

## 📊 七、验收标准

### 7.1 功能性

- [ ] `python3 main.py` 正常启动不报错
- [ ] Dashboard 路由全部可达（`/`、`/test`、`/history`、`/settings`）
- [ ] 所有 CRUD 操作正常
- [ ] SSE 连接断线后最多重试 5 次
- [ ] 配置了 `WEB_API_KEY` 后未认证请求返回 401

### 7.2 安全性

- [ ] SSL 证书验证已恢复（除显式配置）
- [ ] API Key 不在日志/数据库/前端中泄露
- [ ] Gemini Key 改用 Header 传递
- [ ] SQL 注入已修复（白名单校验）
- [ ] CORS 限制为配置的来源

### 7.3 性能

- [ ] manifest.json 并发写入无数据丢失（10 协程 × 100 次验证）
- [ ] rate_limiter 1000 次超时后并发度不下降
- [ ] 数据库高并发下无 "database is locked" 错误
- [ ] Dashboard 进出 10 次内存不增长（内存快照对比）

### 7.4 代码质量

- [ ] Dashboard.vue < 1000 行
- [ ] 无 `ref<any>` 类型
- [ ] 无 `.bak` 文件残留
- [ ] 测试覆盖率 ≥ 30%

---

## ⚠️ 八、风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|:----:|---------|
| async/await 改造导致新 Bug | 🟠 | 每文件改造后单独验证，保留原函数做回退 |
| aiosqlite 行为差异 | 🟡 | 全量回归测试现有功能 |
| Dashboard 拆分遗漏功能 | 🟠 | 拆分前录制 Playwright 截图对比 |
| Provider 统一导致注册失效 | 🟡 | 保留原注册方式做 wrapper |
| SDK 重构破坏现有用户 | 🟠 | 保持旧 API 兼容，新版用新方法名 |

### 回滚方案

```bash
# 整体回滚
git revert <commit-range>

# 数据库回滚
cp results/config.db.backup results/config.db

# 单文件回滚
git checkout HEAD~1 -- model_speed_test/src/recorder.py
```

### 备份策略

```bash
# 每次 Phase 开始前执行
cp results/config.db results/config.db.backup_$(date +%Y%m%d_%H%M%S)
cp model_speed_test/tasks.json model_speed_test/tasks.json.backup 2>/dev/null
git tag -a "before-phase-{N}" -m "Phase {N} 开始前快照"
```

---

## 📅 九、时间表

| 日期 | 阶段 | 预计工时 |
|------|------|:----:|
| Day 1 | Phase 0 紧急止血 | 4h |
| Day 1-2 | Phase 1 安全加固 | 12h |
| Day 2-4 | Phase 2 性能与稳定性 | 20h |
| Day 4-8 | Phase 3 架构重构 | 44h |
| Day 8 | 整体验收 + 文档更新 | 4h |
| **总计** | | **~10 工作日** |

---

*方案制定时间：2026-06-30 08:45*
*基于：2026-06-29 独立源代码审查（209 条问题）*
*影响分析时间：2026-06-30 09:15*

---

## 🔬 十、影响分析

> **分析方式**：基于实际代码的 import/reference 依赖链路和逐项副作用审查

### 10.1 核心模块依赖关系（改动波及视图）

#### database.py（11 个文件依赖）

| 依赖文件 | 引用方式 | 受影响函数 |
|---------|---------|-----------|
| `web/app.py` | `from src.database import get_database` | 39 个端点中的 ~15 个 |
| `src/recorder.py` | `from .database import TestDatabase, get_database` | `save_record()` / `save_round_results()` |
| `src/tester.py` | `from .database import TestDatabase, get_database` | `run_test()` / `_save_results()` |
| `src/scheduler.py` | `from .database import TestDatabase, get_database` | `execute_task()` |
| `src/metrics.py` | `from .database import TestDatabase, get_database` | 指标写入路径 |
| `src/evaluator.py` | `from .database import TestDatabase, get_database` | 评估结果存储 |
| `web/emitter.py` | `from src.database import TestDatabase, get_database` | SSE 事件发射器 |
| `web/report_generator.py` | `from src.database import TestDatabase, get_database` | 报告生成 |
| `web/excel_exporter.py` | `from src.database import TestDatabase` | Excel 导出 |
| `src/test_case_manager.py` | `from .database import TestDatabase, get_database` | 测试用例 CRUD |
| `src/client.py` | `from .database import TestDatabase, get_database` | 客户端初始化 |

**⚠️ 关键影响**：`database.py` 改为 `aiosqlite` 后，所有 11 个文件的 `cursor.fetchall()` 返回值类型从 `sqlite3.Row` 变为 `aiosqlite.Row`，需要检查下游是否依赖 `row["field"]` 字典访问 vs `row[0]` 索引访问（当前代码使用字典方式，aiosqlite.Row 兼容）。

#### recorder.py（5 个文件依赖）

| 依赖文件 | 受影响函数 |
|---------|-----------|
| `src/tester.py` | `_record_result()` → `recorder.save_record()` |
| `src/scheduler.py` | `execute_task()` → `recorder.finalize_round()` |
| `src/main.py` | `run_tests_with_web()` → `recorder` 实例创建和调用 |
| `src/evaluation_manager.py` | `run_evaluation()` → 读取 recorder 输出的 manifest.json |
| `web/app.py` | `/test/start` → 创建 recorder 实例 |

**⚠️ 关键影响**：recorder.py 改为异步后，`tester.py` 中所有 `self.recorder.save_record()` 调用必须加上 `await`，否则返回 coroutine 对象而不执行，数据永久丢失。`scheduler.py` 同理。

#### scheduler.py（4 个文件依赖）

| 依赖文件 | 受影响函数 |
|---------|-----------|
| `web/app.py` | `/test/start` 创建 Scheduler 实例 |
| `src/main.py` | 调度器初始化和后台任务 |
| `src/tester.py` | 调度器回调注册 |
| `web/emitter.py` | 通过 scheduler 获取任务状态 |

#### rate_limiter.py（2 个文件依赖）

| 依赖文件 | 受影响函数 |
|---------|-----------|
| `src/tester.py` | `_throttled_request()` 中调用 `await limiter.acquire()` |
| `src/client.py` | 初始化 RateLimiter 实例 |

**✅ 低影响**：rate_limiter 改动仅在内部方法，不改变对外接口，下游无需修改。

#### async_io.py（新建，6 个文件需要改造）

如果创建 `async_io.py`，以下文件的同步 I/O 需改为调用 `async_io` 函数：

| 文件 | 改造工作量 |
|------|:--------:|
| `src/recorder.py` | ~12 处 `open()` / `json.dump()` |
| `src/database.py` | ~20 处 `sqlite3.connect()` / `cursor.execute()` |
| `src/test_case_manager.py` | ~4 处 JSON 配置文件读写 |
| `src/scheduler.py` | ~2 处 tasks.json 读写 |
| `src/logging_utils.py` | ~2 处日志文件写入 |
| `web/app.py` | ~8 处文件操作（报告生成等） |

#### web/app.py → 前端影响链路

| 端点 | 前端调用位置 | 改动影响 |
|------|------------|---------|
| `POST /config/models` | `useConfig.ts` / `Settings.vue` | 认证头新增后前端需适配 |
| `GET /config/models` | `useConfig.ts` / `Dashboard.vue` | 同上 |
| `POST /test/start` | `useSSE.ts` 或 `Dashboard.vue` 中 fetch | 同上 |
| `POST /test/stop` | `Dashboard.vue` 中 fetch | 同上 |
| `DELETE /api/history/:id` | `History.vue` | 同上 |
| `GET /api/history` | `useTasks.ts` / `Dashboard.vue` | 分页参数新增后需适配 |

#### Dashboard.vue → 组件引用关系

| 已存在的子组件 | Dashboard.vue 中是否使用 | 状态 |
|---------------|:----------------------:|------|
| `DashboardHeader.vue` | ✅ 已使用 | 可保留 |
| `DashboardSidebar.vue` | ✅ 已使用 | 可保留 |
| `TaskCard.vue` | ✅ 已使用 | 可保留 |
| `LogPanel.vue` | ✅ 已使用 | 可保留 |
| `TaskDetailModal.vue` | ✅ 已使用 | 可保留 |
| `StartConfigModal.vue` | ✅ 已使用 | 可保留 |
| `ReportPreviewModal.vue` | ✅ 已使用 | 可保留 |
| `TreeView.vue` / `TreeItem.vue` | ✅ 已使用 | 可保留 |
| `ContextMenu.vue` | ✅ 已使用 | 可保留 |

**⚠️ 关键影响**：子组件虽已拆分，但 Dashboard.vue 内仍有内联实现的逻辑与子组件重复（如 `calculateAverages`），拆分时需注意两套实现的功能差异。

---

### 10.2 Phase 0 逐项副作用分析

#### P0-1. `all_results` 未定义修复

- **依赖破坏**：✅ 无。纯 bug 修复，仅增加一行初始化。
- **数据兼容**：✅ 无影响。
- **运行时变更**：无行为变更，仅修复崩溃。
- **部署风险**：✅ 无。

#### P0-2. `eval_manager` 初始化

- **依赖破坏**：🟡 中等。添加 `self.eval_manager = None` 后，L761 的 `self.eval_manager.eval_client` 访问会在 `eval_manager` 为 `None` 时触发 `AttributeError: 'NoneType' object has no attribute 'eval_client'`。当前代码路径可能因上游条件永不触发，但初始化后反而可能暴露新错误。
- **建议**：初始化后对 L761 加 `hasattr` 保护或补全 eval_manager 的完整初始化逻辑。

#### P0-3. `input()` 交互式日志

- **依赖破坏**：✅ 无。仅改变 `setup_logging()` 内部实现。
- **运行时变更**：🟢 正向。Docker/CI 环境不再崩溃，用户可通过 `ENABLE_FILE_LOGGING=1` 环境变量控制。
- **部署风险**：需在部署文档中注明新增环境变量。

#### P0-4. 空列表 SQL 修复

- **依赖破坏**：✅ 无。纯 bug 修复。
- **数据兼容**：✅ 无影响。

#### P0-5. App.vue 缺少 `<router-view />`

- **依赖破坏**：🟠 较高。添加 `<router-view />` 后，`/test`、`/history`、`/settings` 路由变为可达，但这些页面可能因长期未使用存在未发现的 bug。当前 Dashboard 是所有功能的唯一入口，拆分后需验证每个路由都能正常工作。
- **运行时变更**：需要为各路由页面补充导航链接和返回按钮。

#### P0-6. SSL 证书验证恢复

- **运行时变更**：🟠 高风险。**所有自签名证书的本地/内网端点将连接失败**，包括：
  - LMStudio 本地部署（`https://localhost:1234`）
  - 移动云内网 API（`https://api-yidongyun.local`）
  - 任何使用 `CERT_NONE` 的第三方代理
- **缓解方案**：必须同时实施 `ALLOW_INSECURE_SSL=true` 环境变量控制，并在文档中说明。建议默认为 `true`（向后兼容），由用户决定是否收紧。

#### P0-7. 数据库迁移改为 PRAGMA 检查

- **依赖破坏**：✅ 无。仅改变迁移逻辑的内部实现。
- **数据兼容**：✅ 完全兼容。`PRAGMA table_info()` 比 `try/except OperationalError` 更精确。
- **风险**：需确保 `PRAGMA table_info()` 在 SQLite 3.8+ 都可用（✅ 是）。

#### P0-8. Provider 注册系统死代码清理

- **依赖破坏**：🟠 中高风险。需要精确确认：
  - `__init__.py` 旧版 `_register_all_providers()`（L17-38）无任何调用方 → 安全删除
  - `registry.py` 两个 ProviderManager 中,需确认 `main.py`、`client.py`、`web/app.py` 实际 import 的是哪一个 → 可能在 `__init__.py` 中有 re-export
- **建议**：先 grep 确认所有 `from src.providers import` 的使用方式，再逐文件替换。

---

### 10.3 Phase 1 逐项副作用分析

#### P1-1. API 认证启用

- **依赖破坏**：🟠 高风险。为 39 个端点添加 `dependencies=[Depends(require_auth)]` 后：
  - 前端所有 `fetch()` 请求必须带 `X-API-Key` 头，否则 401
  - 启动脚本、curl 测试、第三方集成全部断裂
  - `GET` 请求（读操作）是否也需要认证？design.md 中仅对写操作添加了认证，但 `/config/models` 等包含 API Key 的读端点也应该保护
- **缓解**：`WEB_API_KEY` 为空时自动放行（require_auth 逻辑已兼容）。建议先部署空配置，然后逐步启用。

#### P1-2. 前端 API 适配（useApi.ts 新建）

- **依赖破坏**：🟡 中等。新建 `useApi.ts` 后，需要改造 Dashboard.vue 中所有 `fetch()` 调用。未改造的调用不受影响，但无法享受统一错误处理。
- **建议**：先新建文件，再逐步替换，不一次性全量替换。

#### P1-5/P1-6. API Key 脱敏

- **依赖破坏**：✅ 无。`_sanitize_error_text()` 是新增静态方法，不修改现有接口。
- **运行时变更**：🟢 仅正向影响。错误信息从「含 Key」变为「脱敏后」，日志和前端显示更安全。
- **风险**：脱敏正则可能过于激进，将正常的 Base64 编码内容误判为 Key → 采用保守正则，仅匹配已知模式。

#### P1-7. Gemini Key 改用 Header

- **依赖破坏**：🟡 中等。Google Gemini API 同时支持 query string 和 `x-goog-api-key` header，切换不应导致功能失效。但需要验证当前使用的 Gemini API 版本（v1 vs v1beta）是否都支持 header 认证。

#### P1-8. SQL 注入白名单修复

- **依赖破坏**：✅ 无。增加字段名白名单仅影响非法输入，合法调用不受影响。

#### P1-9. Webhook Secret 加密存储

- **数据兼容**：🟠 需要迁移逻辑。`decrypt()` 中已设计 `except Exception: return ciphertext` 兼容历史明文数据，但需确认：
  - `tasks.json` 中已有任务在加密后重启是否会丢失
  - `SECRET_ENCRYPTION_KEY` 更换后旧数据不可解密
- **建议**：新增环境变量 `SECRET_ENCRYPTION_KEY`，提供生成脚本 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`。

#### P1-10. manifest.json 竞态修复

- **运行时变更**：✅ 仅正向。添加 `asyncio.Lock` 后并发写入不会数据丢失。
- **性能影响**：轻微的锁竞争开销（<1ms），可忽略。

---

### 10.4 Phase 2 逐项副作用分析

#### P2-1 ~ P2-4. 异步 I/O 改造

- **依赖破坏**：🟠 高风险。`recorder.py` 12 处改为异步后：
  - `tester.py` 所有 `self.recorder.save_xxx()` 必须 `await`
  - `scheduler.py` 所有 `self.recorder.xxx()` 必须 `await`
  - `main.py` 中 recorder 调用必须 `await`
  - `web/app.py` 中 recorder 调用必须 `await`
  - **漏改任一处都会导致 coroutine 不执行，数据静默丢失**
- **数据库改造**：`database.py` 改为 `aiosqlite` 后：
  - 当前大量同步函数（例如 `search_groups` 是普通 `def`）需改为 `async def`
  - 所有调用方的 `db.xxx()` 需加 `await`
  - `web/app.py` 中 15+ 个端点的数据库调用需加 `await`
  - 如果 `web/app.py` 中某些端点是同步函数而非 `async def`，需要改为 `async def`（FastAPI 同时支持两者）
- **旧数据兼容**：manifest.json 格式不变，仅读写方式从同步改为异步，✅ 兼容。
- **建议**：先改 database.py，再改 recorder.py，最后改调用方。每步都运行现有测试验证。

#### P2-5. 调度器重叠检测

- **运行时变更**：新增 `task.status == "running"` 检查 → 长任务不会重复触发。但如果 `execute_task` 内部异常，需要确保 `finally` 块将状态恢复为 `idle`，否则任务永久卡在 `running` 状态。
- **建议**：在 `_execute_with_cleanup` 的 `finally` 中确保状态恢复（design.md 代码示例已包含 ✅）。

#### P2-9. 事件监听器清理

- **运行时变更**：✅ 仅正向。添加 `onUnmounted` 清理逻辑后，Dashboard 组件销毁时不再有悬挂监听器。
- **风险**：确保所有被注册的监听器名称与注册时一致（`onCardDrag` vs `handleCardDrag` 等命名不一致可能导致移除无效）。

#### P2-10. SSE 重连策略

- **运行时变更**：🟡 行为变更。从「无限重连」变为「5 次后停止」。如果网络波动超过 5 次（约 30s + 60s + 120s + 240s + 480s ≈ 15 分钟），连接永久断开需要用户手动刷新。
- **建议**：将 `MAX_RECONNECT_ATTEMPTS` 和 `BASE_DELAY` 作为可配置参数，而非硬编码。

#### P2-11. 日志缓冲区上限

- **运行时变更**：🟡 排查影响。10000 条日志上限后，如果问题复现需要 12000 条日志，早期日志被截断。对于长时间运行（>2 小时）的测试任务可能不足。
- **建议**：将上限设为 50000 或作为可配置项。

#### P2-13. folder_id 索引

- **部署风险**：✅ 低。`CREATE INDEX IF NOT EXISTS` 幂等，多次执行不会报错。但在已有大量数据的数据库上首次创建索引可能耗时较长（100 万行约需 3-5 秒）。

#### P2-14. 列表分页

- **依赖破坏**：🟠 API 变更。`GET /api/history` 从返回全部数据变为返回分页数据 + `total`/`page`/`page_size` 字段。前端需要适配新的响应格式。如果一次性切换，Dashboard.vue 中所有调用 `/api/history` 的代码都会报错。
- **建议**：新增 `/api/history?page=1&page_size=50` 参数，不传时保持原有行为（全量返回），渐进式切换。

#### P2-16. SSE 连接数限制

- **运行时变更**：✅ 安全加固。对正常使用无影响（通常只有 1-2 个 SSE 连接），仅防止恶意连接耗尽 fd。

---

### 10.5 Phase 3 逐项副作用分析

#### P3-1. Dashboard.vue 拆分

- **并行冲突**：🟠 高冲突风险。如果 Phase 2 的「监听器清理」(P2-9)、「fetch 错误处理」(P2-12) 与 Phase 3 的 Dashboard 拆分并行开发，会产生大量合并冲突，因为都在改同一个文件（7512 行的 Dashboard.vue）。

- **建议执行顺序**：
  1. 先完成 Phase 2 中 Dashboard.vue 的小改动（P2-9, P2-12）
  2. 再开始 Phase 3 的大拆分
  3. TypeScript 类型完善（P3-2）可与拆分并行，但建议在拆分后基于新组件结构进行

- **遗漏功能风险**：内联实现的 `calculateAverages` 与 `useTasks.ts` 中的版本不一致 → 拆分时需对比功能差异并合并。

#### P3-2. TypeScript 类型完善

- **并行冲突**：🟡 中等。与 Dashboard 拆分共享大量接口定义，建议在拆分完成后统一实施，避免类型定义分散在旧文件和新文件中。

#### P3-3. Provider 系统统一

- **依赖破坏**：🟠 高风险。当前有两个 ProviderManager 实现，需确认 `main.py`（L105-129 的 `load_config()`）、`client.py`、`web/app.py` 中实际使用的注册系统是哪个。若删除错误版本，会导致 Provider 注册失败，所有模型测试不可用。
- **建议**：
  1. `grep -rn "ProviderManager\|register_provider\|_register_all" model_speed_test/src model_speed_test/web model_speed_test/main.py`
  2. 确认实际使用路径后，保留使用的版本，删除另一个
  3. 统一后更新所有 import 路径

#### P3-4. JS SDK 重写

- **依赖破坏**：🟠 API 变更。新 SDK 使用 `fetch` 替代 `EventSource`：
  - SSE 消息解析从浏览器原生改为手动 `ReadableStream` 解析
  - 需要处理 `data:` 前缀、`[DONE]` 结束信号
  - 旧代码 `new EventSource()` 将不可用
- **建议**：保持旧 API 签名兼容，新增一个 `streamTestV2()` 方法，逐步迁移。

#### P3-5. Python SDK 连接泄漏修复

- **运行时变更**：✅ 仅正向。从 `requests.get(stream=True)` 改为 `with requests.post(...)` context manager，连接自动关闭。
- **风险**：`iter_lines()` 行为与 `response.body.getReader()` 略有差异，需验证分块传输编码的兼容性。

#### P3-7. 测试补充

- **风险**：✅ 仅正向。新增测试不影响现有功能。但 mock 对象如果与真实 Provider 行为不一致，可能掩盖真实问题。

---

### 10.6 新增依赖分析

| 依赖 | 版本要求 | 安装方式 | 冲突风险 |
|------|---------|---------|:------:|
| `python-dotenv` | ≥1.0.0 | pip | ✅ 纯 Python，无冲突 |
| `aiofiles` | ≥23.0.0 | pip | ✅ 纯 Python，无冲突 |
| `aiosqlite` | ≥0.19.0 | pip | 🟡 需要 SQLite 3.8+（✅ 已满足），可能与系统中已有的 `sqlite3` 模块冲突需验证 |
| `cryptography` | ≥41.0.0 | pip | 🟡 依赖 `cffi`，在某些精简 Docker 镜像中可能缺少 C 编译器。建议在 `requirements.txt` 中固定版本 |

---

### 10.7 环境变量新增清单

| 变量 | 未配置时的行为 | 是否优雅降级 |
|------|--------------|:----------:|
| `WEB_API_KEY` | API 认证跳过（兼容开发环境） | ✅ |
| `CORS_ALLOWED_ORIGINS` | 默认 `http://localhost:5173,http://localhost:3000` | ✅ |
| `ALLOW_INSECURE_SSL` | 默认 `false`（SSL 必须验证） | 🟡 向后不兼容，建议默认 `true` |
| `SECRET_ENCRYPTION_KEY` | 自动生成临时密钥（重启后失效） | 🟡 需打印警告 |
| `ENABLE_FILE_LOGGING` | 默认 `false`（不创建日志文件） | ✅ |

---

### 10.8 执行顺序依赖图

```
Phase 0（必须串行，4h）
  P0-1 ~ P0-4（后端 Bug 修复，可并行）
  P0-5（前端 Vue 修复，可与其他并行）
  P0-6 ~ P0-8（安全检查，依赖 bug 修复完成）
     ↓
Phase 1（后端/前端可并行）
  ├─ 后端：P1-1 → P1-5 → P1-6 → P1-7 → P1-8 → P1-9 → P1-10 → P1-11
  └─ 前端：P1-2 → P1-3 → P1-4
     ↓
Phase 2（需严格顺序）
  ├─ 2A 依赖安装：P2-17 → P2-1（创建 async_io.py）
  ├─ 2B 后端改造：P2-3（database.py，最大影响面）→ P2-2（recorder.py）→ P2-4（其他文件）
  ├─ 2C 调度器：P2-5 → P2-6 → P2-7（需要 2B 完成后才能验证）
  ├─ 2D 前端：P2-9 → P2-10 → P2-11 → P2-12（需要 2B 完成后验证 SSE）
  └─ 2E 运维：P2-13 → P2-14 → P2-15 → P2-16 → P2-18
     ↓
Phase 3（建议按顺序，减少冲突）
  ├─ 3A 前端拆分：P3-1 → P3-2（必须先拆，再补类型）
  ├─ 3B 后端统一：P3-3（可与 3A 并行）
  ├─ 3C SDK：P3-4 → P3-5 → P3-6
  ├─ 3D 测试：P3-7（依赖以上全部完成）
  └─ 3E 清理：P3-8 → P3-9 → P3-10
```

---

### 10.9 总体风险评估

| 风险等级 | 数量 | 主要集中阶段 |
|---------|:----:|-----------|
| 🔴 高风险（需额外设计） | 5 | Phase 2 异步化（依赖破坏链长）、Phase 0 SSL（默认值争议） |
| 🟠 中风险（需验证） | 12 | Phase 1 认证（全系统适配）、Phase 3 Dashboard 拆分（合并冲突） |
| 🟢 低风险 | 18 | 大部分 Bug 修复和增量改动 |

### 关键建议

1. **SSL 默认值调整**：`ALLOW_INSECURE_SSL` 建议默认 `true`（向后兼容），文档中引导用户改为 `false`
2. **database.py 异步化风险最高**：11 个文件依赖，建议先改 database.py，再逐个改调用方，每改一个就运行一次完整测试
3. **分页 API 向后兼容**：建议新增 `?page=` 参数，不传时保持全量返回
4. **Dashboard 拆分放在最后一个大阶段**：先完成其他所有改动，避免合并冲突
5. **每个 Phase 开始前打 git tag**，便于出问题时快速回滚

