# 优化实施计划 v2 — 层次 2（O6-O10 + 性能专项）

> **制定时间**：2026-08-25
> **前置**：层次 1 优化（O1-O5）已完成并验证；本计划覆盖剩余可执行优化项
> **数据依据**：基于当前代码实测（vue-tsc noUnusedLocals 40 个未使用符号、app.py 2845 行/16 裸except/30 str(e)回显、tester 858行/10方法零测试等）
> **原则**：每项独立可交付、可回滚；优先修"正确性"其次"可维护性"，最后"锦上添花"

---

## 一、任务总览与优先级

| 阶段 | 任务 | 优先级 | 工时 | 风险 |
|---|---|---|---|---|
| P1 正确性 | P1-1 History.vue 图表竞态修复 | 高 | 0.5h | 低 |
| P1 正确性 | P1-2 指标口径统一（O7） | 高 | 2h | 中 |
| P1 正确性 | P1-3 双系统调用收敛（ModelClient 单入口） | 中 | 1.5h | 中 |
| P2 稳定性 | P2-1 web/app.py 错误处理统一（16裸except+30回显） | 高 | 2h | 低 |
| P2 稳定性 | P2-2 database.py 事务边界与批量写优化 | 中 | 1h | 中 |
| P3 性能 | P3-1 SSE chunk 渲染节流（rAF/批量flush） | 中 | 1.5h | 中 |
| P3 性能 | P3-2 每秒 setInterval 全量重算优化 | 低 | 0.5h | 低 |
| P3 性能 | P3-3 echarts 按需引入（进一步减包） | 低 | 0.5h | 低 |
| P4 可维护 | P4-1 Dashboard.vue 死代码删除（40符号） | 高 | 1.5h | 低 |
| P4 可维护 | P4-2 ai_analysis/start_test 拆分 | 中 | 2h | 中 |
| P4 可维护 | P4-3 tester.py 单测补充（mock provider） | 高 | 2h | 低 |
| P4 可维护 | P4-4 emitter/database 单测补充 | 中 | 1.5h | 低 |

合计：约 16.5h（可按阶段裁剪）

---

## 二、各任务实施细节

### P1-1. History.vue 图表竞态修复（0.5h，低风险）

**现状**（已核实）：
- History.vue:190、414 两处 setTimeout(renderCharts, 200/200ms)
- 快速切换分组时旧定时器仍触发，对已替换的 DOM init 图表

**方案**：
1. 引入 renderTimer 变量；watch 回调中 clearTimeout 旧 timer 再 setTimeout
2. renderCharts 内部开头加 guard：图表容器不存在或 selectedGroup 已变化则直接 return
3. 统一 200ms 常量 RENDER_DELAY

**验证**：快速连续切换历史分组 10 次，图表渲染正确、console 无 echarts 警告

### P1-2. 指标口径统一（2h，中风险）

**现状**（已核实）：
- 流式：tester.py/_test_stream 用 tiktoken 重算 output_tokens
- 非流式：_test_nonstream 用 API 返回 usage
- 同一模型两种模式数据不可比

**方案**（双通道统一为"API usage 优先 + tiktoken 兜底"）：
1. 流式路径：openai 兼容端点在流末尾 usage 块返回 tokens（openai.py 已提取 usage 传入 StreamChunk）；_test_stream 收集 last_usage
2. 计算 output_tokens 时：last_usage 存在 → 用 API 值；否则 → tiktoken 兜底（当前行为）
3. metrics 增加 tokens_source 字段（"api_usage" | "tiktoken_estimate"）入库并在前端指标卡标注，让数据来源透明
4. 顺带统一：非流式 temperature 与流式取值逻辑对齐（都从 test_config 取）

**验证**：
- 单测：mock 流含 usage → 计数用 API 值；mock 流无 usage → tiktoken
- 实测：同一模型流式/非流式各跑 3 轮对比 token 数差异 <2%

### P1-3. 双系统调用收敛（1.5h，中风险）

**现状**（已核实）：
- main.py 混用：create_clients 优先 ProviderAdapter、失败回退 ModelClient（3 层 try/except 嵌套）
- web/app.py ping 端点直接 new ModelClient
- 两套客户端行为差异是历史 bug 温床（adapter 曾缺 output_tokens）

**方案**：
1. 明确 ModelClient 为唯一对外入口（内部委托 Provider，已实现）
2. main.py create_clients 简化：直接用 ModelClient（内部已有 provider 分发），删除 ProviderAdapter 直调与回退链
3. 校对客户端（eval_client）创建逻辑同步简化（删除嵌套 try/except）
4. client_adapter.py 保留但标记 deprecated（SDK 兼容），或直接删除

**验证**：CLI 测试一轮 + Web 测试一轮结果一致；eval 校对流程正常

### P2-1. web/app.py 错误处理统一（2h，低风险）

**现状**（已核实）：2845 行中 16 处裸 except、30 处 return {"error": str(e)}（HTTP 200）

**方案**：
1. 新增统一异常处理：FastAPI exception_handler(AppError) + 自定义 AppError(status_code, message)
2. 30 处 str(e) 回显 → 统一改为 raise AppError(500, "操作失败") + logger.exception（服务端留全量日志，不回显内部细节）
3. 16 处裸 except → except Exception + logging.exception（保留行为，补日志）
4. 前端 apiFetch 已有 res.ok 检查，配合无障碍（错误仍可见）

**验证**：模拟错误场景（删除不存在的组、非法 body），前端 toast 正常显示、服务端日志有堆栈

### P2-2. database.py 事务与批量优化（1h，中风险）

**现状**：每条 add_result 独立事务（open→write→close），并发多模型时 IO 放大；_update_group_progress 每轮全表 COUNT

**方案**：
1. add_result 支持调用方传入已开启事务的连接（复用）或加批量接口 add_results(list)
2. _update_group_progress 改为增量 UPDATE（completed_rounds+1、success_count+1）而非全量 SELECT COUNT
3. 保留现有单条接口兼容

**验证**：并发 5 模型 × 10 轮测试，DB 写入耗时对比（目标 -40%）；结果行数完整

### P3-1. SSE chunk 渲染节流（1.5h，中风险）

**现状**（已核实）：Dashboard.vue:3650 chunk 事件直接 tasks.value[...].output += data.content —— 每个 SSE chunk 触发响应式更新+重渲染，大输出（数千 token）时明显卡顿

**方案**：
1. chunk 内容先写入非响应式 buffer（Map<taskId, string>）
2. requestAnimationFrame 或 80ms 定时器批量 flush 到响应式 tasks
3. complete 事件时 flush 全部 buffer 兜底
4. 页面卸载时清空 buffer/timer

**验证**：长输出（2000+ tokens）流式测试，前端无明显卡顿；最终输出内容完整无缺字

### P3-2. 每秒定时器优化（0.5h，低风险）

**现状**：Dashboard.vue setInterval 每秒更新 now.value → 所有任务卡每秒重算 getTaskDuration 并重渲染

**方案**：仅对"运行中"任务启用计时（完成的任务 duration 固定）；或节流为 5s 且用 computed 缓存

**验证**：任务多时（20+ 卡）CPU 占用对比；显示不受影响

### P3-3. echarts 按需引入（0.5h，低风险）

**现状**：echarts chunk 1MB（gzip 343KB）全量引入

**方案**：main.ts 已按需注册核心组件；History.vue 用 import * as echarts 全量——改为从 main.ts 的注册模块复用（echarts/core + 已注册的图表类型），预计再减 30-50%

**验证**：echarts chunk 体积对比；History 页图表正常

### P4-1. Dashboard.vue 死代码删除（1.5h，低风险）

**现状**（已核实）：noUnusedLocals 开启后 40 个未使用符号，集中在：
- 日志面板拖拽/resize 死逻辑（startLogPanelDrag/startLogResize* 等 10+）
- 旧 popover 死状态（showCasePopover 相关已删，残余）
- sortTasks/extractThinkAndAnswer/escapeHtml 等空实现或未调用

**方案**：
1. 逐个确认无模板引用后删除（grep 模板 + script 双重确认）
2. 对应的 style 死样式一并清理（.log-panel-drag 等）
3. 删除后重新开启 tsconfig noUnusedLocals 保持零容忍
4. 目标：Dashboard.vue 缩减约 800-1200 行

**验证**：build 通过 + 手测日志面板/任务卡/弹窗功能正常

### P4-2. ai_analysis / start_test 拆分（2h，中风险）

**现状**：ai_analysis 382 行（数据收集+提示词构建+SSE流式+统计全部内联）；start_test 355 行（配置读取+客户端创建+线程管理）

**方案**：
1. ai_analysis → _collect_analysis_data() + _build_analysis_prompt() + _stream_ai_response()
2. start_test → _load_test_config_from_db() + _build_case_folder_map()（与 main.py 重复的配置读取统一）
3. 提取 web/services.py 存放复用的配置读取（消除 15+ 处硬编码 config_db_path）

**验证**：路由行为不变（对比拆分前后 /api/analysis 与 /test/start 响应）

### P4-3. tester.py 单测补充（2h，低风险）

**现状**：858 行核心测试引擎零测试

**方案**：新增 tests/test_tester.py：
- 用 FakeClient（实现 chat_stream/chat 接口，可控返回）测试 ModelTester
- 覆盖：流式指标计算、多轮 run_test_rounds、停止信号（stop_event）提前退出、超时路径、空输出判失败
- ConcurrentTester：并发正确聚合、限流

**验证**：pytest 全绿；停止逻辑（B1 修复）获得回归保障

### P4-4. emitter/database 单测补充（1.5h，低风险）

**方案**：
- tests/test_emitter.py：事件发射、订阅队列、状态保存/恢复（tmp 目录）、DB 集成开关
- tests/test_database.py：组/结果 CRUD、文件夹级联、WAL 连接配置

**验证**：pytest 全绿；DB 行为回归保障

---

## 三、执行顺序与依赖

| 顺序 | 任务 | 依赖 |
|---|---|---|
| 1 | P1-1 图表竞态 | 无 |
| 2 | P4-1 Dashboard 死代码删除 | 无（先做减少后续干扰） |
| 3 | P1-2 指标口径 | 无 |
| 4 | P1-3 双系统收敛 | 无 |
| 5 | P2-1 错误处理统一 | P4-2 之前做（避免改两遍） |
| 6 | P4-2 巨型函数拆分 | 依赖 P2-1 的 AppError 基建 |
| 7 | P3-1/P3-2/P3-3 性能三项 | 依赖 P4-1（死代码清理后改） |
| 8 | P4-3/P4-4 单测补充 | 建议在 P1-3/P4-2 改动后做（测最终形态） |

**推荐批次**：
- 批次 A（~4h，正确性+低风险）：P1-1 → P4-1 → P1-3
- 批次 B（~4h，核心质量）：P1-2 → P2-1 → P2-2
- 批次 C（~4h，体验与保障）：P3-1 → P3-2 → P3-3 → P4-3 → P4-4
- 批次 D（~2h，收尾）：P4-2

---

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| P1-2 指标口径变化导致历史数据不可比 | tokens_source 字段透明化；changelog 说明 |
| P1-3 删除 ProviderAdapter 直调影响 eval 流程 | eval_client 改用 ModelClient 后实测一轮校对 |
| P2-1 错误处理改动影响前端解析 | 前端 apiFetch 已按 HTTP 状态处理；逐端点回归 |
| P3-1 buffer flush 丢字 | complete 时全量 flush + 单测覆盖拼接正确性 |
| P4-1 误删仍被引用代码 | 删除前 grep 双重确认 + build 门禁 |

每项独立 commit；改动前 git tag（optimization-start）。

---

## 五、验收总清单

- [ ] pytest ≥ 60 passed（新增 tester/emitter/database 测试）
- [ ] 前端 build 零错误 + echarts chunk 显著缩小
- [ ] 长输出流式测试无卡顿、内容完整
- [ ] Dashboard.vue ≤ 6500 行 + noUnusedLocals 重新开启且 0 报错
- [ ] web/app.py 裸 except ≤ 3（仅兼容性保留）、str(e) 回显归零
- [ ] 同一模型流式/非流式 token 差异 <2%（tokens_source 标注）
- [ ] 所有优化独立 commit，可单独回滚

---

*本计划基于 2026-08-25 代码实测数据（vue-tsc/eslint/grep 统计），所有行号以当前工作区为准。*
