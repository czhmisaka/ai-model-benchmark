# AI 模型速度测试框架 — 功能修复实施计划 v1.0

> **制定时间**：2026-08-25
> **依据**：四轮深度代码审查（web后端 / Provider层 / 测试引擎 / 前端）交叉验证结论
> **范围**：聚焦**功能性问题**（本地测评工具，安全项不作为本计划重点，仅列可选加固项）
> **原则**：每阶段可独立交付验证；先止血、后正确性、再体验；每个修复配回归验证

---

## 一、目标与验收总览

| 目标 | 验收标准 |
|---|---|
| 所有测试场景能跑通 | 多模态 / Anthropic / 非流式 / 并发 / 定时任务均不崩溃、结果落盘 |
| 指标准确 | TTFT/TPFT/吞吐量/think-answer 拆分口径统一、无丢失 |
| 服务稳定 | 停止测试后服务可恢复、进度不丢、无事件重复 |
| 可回归 | pytest 全绿、核心路径有单测覆盖 |
| 可维护 | 死代码清理、契约类型化、文档同步 |

---

## 二、问题地图（已确认，按阶段归组）

### 阶段 A：数据急救 + 崩溃止血（P0，~4h）

| ID | 问题 | 位置 | 验证方式 |
|---|---|---|---|
| A1 | test_results.db 损坏（51MB），历史结果不可读 | results/test_results.db | integrity_check=ok；历史页可读 |
| A2 | 多模态 token 估算 TypeError 崩溃 | metrics.py:82-126 + tester.py:286 | 多模态用例实测通过 |
| A3 | Anthropic max_tokens=-1 + thinking+temperature → 400 | tester.py:82 + anthropic.py:151,233 | Claude 用例实测通过 |
| A4 | 非流式测试误判空输出失败 | client_adapter.py:60-67,117-128 | 非流式/多轮消息实测通过 |
| A5 | 测试套件损坏（1 error+6 failed） | tests/*.py | pytest 全绿 |

### 阶段 B：停止/调度可靠性（P0-P1，~3h）

| ID | 问题 | 位置 | 验证方式 |
|---|---|---|---|
| B1 | 强杀线程致 _test_running 卡死、服务不可恢复 | web/app.py:1510-1537,2201-2202 | 停止后能再次启动测试 |
| B2 | 强杀失败时新旧测试并发双写 | web/app.py:2340 | 连续 start/stop 无污染 |
| B3 | ONCE/CRON 任务无限重复执行 | scheduler.py | 定时任务仅执行一次/按 cron |
| B4 | monthly 跨月 ValueError | scheduler.py:77-81 | 月末+31日配置不崩 |

### 阶段 C：指标正确性（P1，~4h）

| ID | 问题 | 位置 | 验证方式 |
|---|---|---|---|
| C1 | 流式 usage 恒 None、first_token_time 死代码 | client.py:143-153 | 流式返回 usage |
| C2 | 流式 reasoning 并入 content（语义不一致） | client.py:137-139 | content 只含 answer |
| C3 | Anthropic 思考文本双计 | client_adapter.py:152-163 | think_tokens 不翻倍 |
| C4 | 非流式丢失 reasoning_content | openai.py:132-153 | think_content 有值 |
| C5 | 本地 Provider 流式丢失 reasoning | local.py:186-194 | LMStudio 思考分离 |
| C6 | metrics.py:289 翻转逻辑回归标签型模型 | metrics.py:289-291 | 标签型/无标签型单测通过 |
| C7 | tiktoken 与 API usage 双口径 | tester/metrics | 流式/非流式可比较 |
| C8 | 各 provider is_first/TTFT 语义不统一 | anthropic/gemini/azure/local | TTFT 不含服务延迟 |

### 阶段 D：前端功能修复（P1-P2，~4h）

| ID | 问题 | 位置 | 验证方式 |
|---|---|---|---|
| D1 | SSE 重连泄漏→事件重复 | Dashboard.vue:3521-3542 | 断网恢复无重复 |
| D2 | 任务 key 名称拼接→同名覆盖 | Dashboard.vue:1550-1556 | 同名用例不冲突 |
| D3 | 移动用例两套端点+名称当id | Dashboard.vue:2282 + TestSetManagerModal.vue:138 | 移动用例成功 |
| D4 | TestRun.vue 404 演示页 | TestRun.vue:502 | 路由可用或移除 |
| D5 | 双主题变量冲突 | App.vue vs variables.scss | 主题色唯一、--gray-50 生效 |
| D6 | History.vue 图表未 dispose | History.vue:120-122 | 切换无泄漏 |
| D7 | 报告渲染不可靠（v-html 注入） | Dashboard.vue:1172 + ReportPreviewModal | 模型输出不注入 |
| D8 | 状态文件双写竞态 | emitter.py:174-205 | 并发请求无半写 |

### 阶段 E：工程化收尾（P2-P3，~4h）

| ID | 问题 | 位置 | 验证方式 |
|---|---|---|---|
| E1 | Dashboard.vue 7546 行拆分 或 死代码清理（二选一） | frontend/src | 模块化可维护 |
| E2 | 前后端契约类型化（types/api.ts） | frontend/src | 类型检查通过 |
| E3 | vue-tsc 接入 build + CI | package.json | build 含类型检查 |
| E4 | 依赖版本锁定 | requirements.txt | pip install 可复现 |
| E5 | README/文档同步（配置方式、新架构） | README*.md | 按文档可部署 |
| E6 | results/ 数据清理策略 | results/ | 备份+清理脚本 |
| E7 | SDK webhook 端点缺失 | sdk/python + web/app.py | SDK 功能可用 |

### 可选加固（本地工具，低优先）

| ID | 问题 | 位置 |
|---|---|---|
| S1 | SSL 默认校验 + verify_ssl 开关 | openai.py:42-45 |
| S2 | 认证 fail-closed（WEB_API_KEY 必填才启动） | web/app.py:30-54 |
| S3 | API Key 响应脱敏 | web/app.py 返回处 |
| S4 | 路径遍历 group_id 白名单 | database.py:589-622 |
| S5 | SSE /events 认证 | web/app.py:90 |

---


---

## 三、各任务实施细节（方案 + 验证）

### A1. 恢复损坏数据库
- **操作**：停服务 → 备份损坏文件 → 用 test_results.db.backup_20260525_111200 恢复 → 校验 integrity
- **风险**：5月25日后数据不可恢复（损坏前无其他备份）；确认后由用户决定是否接受
- **验证**：PRAGMA integrity_check = ok；历史页列出旧记录

### A2. 多模态 token 估算修复
- **方案**：metrics.py 的 count_tokens/estimate_tokens 增加 list 分支——抽取 part 中 type=text 的 text 字段拼接后计数；image part 固定估算（如 85 tokens/图）
- **涉及**：metrics.py:37-60, 62-99；调用方 tester.py:286 保持不动
- **验证**：新增单测（list content 正常返回数字）；多模态用例实测通过

### A3. Anthropic 兼容修复
- **方案**：
  1. tester.py:82 的 max_tokens=-1 改为 test_case 配置值（默认 4096），或在 anthropic.py 对 ≤0 做保护（对齐 openai.py:77-80 的写法）
  2. anthropic.py thinking 启用时不发送 temperature（或置 1）
- **验证**：Claude 流式/非流式实测通过；单测 payload 断言

### A4. ProviderAdapter 非流式契约补齐
- **方案**：chat() 签名增加 messages/system_prompt 参数；返回 dict 增加 input_tokens/output_tokens 顶层键（对齐 ModelClient.chat 契约）
- **验证**：非流式多轮消息用例通过；单测断言返回键

### A5. 测试套件修复
- **方案**：
  1. test_client.py:10 改为从 src.providers.base 导入 RetryConfig（或从 client 转发导出）
  2. test_recorder.py 全部测试改为 async + await（record/finalize/generate_summary/export_csv）
  3. test_metrics.py 修正 total_time 断言为 1.5（对齐实现语义）
- **验证**：pytest -q 全绿

### B1/B2. 协作式停止替代强杀
- **方案**：
  1. 删除 _async_raise/stop_test_thread 强杀路径，stop 只 set(stop_event)（协作取消，main.py should_stop 已支持）
  2. run_test 包裹 try/finally 保证 _test_running=False 必然复位
  3. stop_test 不再无条件置 False；改为轮询线程结束或设置超时兜底
  4. 线程改 daemon=True + asyncio.run 包裹异常
- **验证**：反复 start/stop 循环 10 次，状态始终正确；阻塞在慢请求时停止也能恢复

### B3/B4. 调度器修复
- **方案**：
  1. ONCE：执行后置 completed（不再回到 idle），next_run 置空
  2. CRON：引入 croniter 解析 cron_expression（新增依赖）或实现 5 字段解析器
  3. monthly：replace 前做天数 clamp（calendar.monthrange）
  4. _execute_with_cleanup 不再覆盖 completed/failed 状态
- **验证**：单测（once 只执行一次、cron 下一时刻计算正确、月末不崩）；集成：启调度器观察 2 周期

### C1-C8 指标统一
- **统一方案**：建立"Provider 返回原始 usage + 流式重算兜底"的双通道策略：
  1. client.py 流式循环记录 last_usage 并返回；content 只装 answer、reasoning 单独聚合
  2. client_adapter 修复思考文本双计（is_think 时只进 think_content_parts）
  3. openai 非流式提取 reasoning_content；local 流式提取 reasoning_content
  4. metrics.py 翻转逻辑加"跳过开启 think 的同一 chunk"守卫 + 两组单测（标签型/无标签型）
  5. is_first 统一语义："第一个携带内容（含 reasoning）的块"，anthropic 移到首个内容块，gemini/azure/local 补实现
- **验证**：构造各 provider 的 mock 流式响应单测；真实模型对比流式/非流式输出一致性

### D1-D8 前端修复
- **D1**：直接换用已写好的 composables/useSSE.ts（指数退避+重连前 close）
- **D2**：SSE 事件携带 case_id，前端以 id 为 key（后端 emitter 已含该信息）
- **D3**：统一走 PUT /config/test-cases/{id}/move；TestSetManagerModal 改为传 folder_id 或先查 id
- **D4**：对齐 /test/start 与字段名，或从路由移除
- **D5**：只保留 App.vue 主题源，variables.scss 改为引用
- **D6**：onUnmounted 统一 dispose + 取消定时器
- **D7**：引入 DOMPurify 消毒后再 v-html
- **D8**：emitter 状态读写加 threading.Lock；运行中 /status 直接读内存不 reload
- **验证**：浏览器手测各场景 + 契约核对表回归

---

## 四、执行顺序与依赖

| 阶段 | 依赖 | 说明 |
|---|---|---|
| Phase A（A1→A2→A3→A4→A5） | 无 | A1 可独立并行 |
| Phase B（B1/B2 → B3/B4） | 依赖 A | 避免在坏数据上调试 |
| Phase C（C1-C8） | 依赖 B1 | 停止可靠后才能反复验证 |
| Phase D（D1-D8） | 依赖 A | 后端修复后前端才有意义 |
| Phase E（E1-E7） | 依赖 D | 前端清理在功能修复后 |

**并行策略**：A1 数据恢复可与 A2-A5 并行；C 与 D 的前端部分可部分并行（独立文件）。

---

## 五、风险与回滚

| 风险 | 缓解 |
|---|---|
| DB 恢复丢失 5/25-7/13 数据 | 先备份损坏文件，与用户确认后恢复；确认无更新备份 |
| 协作取消改造引入新卡死 | 保留 stop_event 轮询 + 超时兜底（线程 join(timeout) 后强制） |
| scheduler 引入 croniter 新依赖 | 若无网络，用自实现 5 字段解析（~80 行，含单测） |
| 前端改动影响现有 Dashboard | 每项修复独立 commit + 手测清单；死代码清理放最后 |
| 指标口径统一改变历史结果含义 | 明确"修复后结果与前版本不可比"，记录 changelog |

---

## 六、回滚策略
- 每个 Phase 完成时打 tag / commit
- 关键文件（database.py / emitter.py / web/app.py / scheduler.py）改动前先备份
- 数据库恢复前对损坏文件做完整副本

---

## 七、工时汇总

| 阶段 | 工时 | 产出 |
|---|---|---|
| A 数据急救+崩溃止血 | ~4h | 全部测试场景可跑 |
| B 停止/调度可靠性 | ~3h | 服务稳定可恢复 |
| C 指标正确性 | ~4h | 结果可信 |
| D 前端功能 | ~4h | 交互完整 |
| E 工程化 | ~4h | 可维护可回归 |
| S 可选加固 | ~3h | 本地部署建议的 2-3 项 |
| **合计** | **~22h（含 S ~25h）** | |

---

*本文档基于四轮审查报告（web/app、Provider、测试引擎、前端）汇总，所有问题均已在原报告中附【文件:行号】验证。*

