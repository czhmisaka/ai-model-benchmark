# 前端代码审查报告 — model_speed_test/frontend

> 审查范围：`frontend/src`（Vue 3.4 + Vite 5 + TS 5.3 + ECharts 5 + vue-echarts 6）
> 审查方式：全部源文件已通读（含 `git diff` 未提交修改），并与后端 `web/app.py` / `main.py` / `src/metrics.py` 契约核对
> 严重程度：🔴高 / 🟡中 / 🟢低

---

## 0. 结构与规模概况

```
frontend/src
├── App.vue                        (全局样式 :root 主题)
├── main.ts                        (注册 Pinia/router/v-chart + echarts use())
├── router/index.ts                (/, /test, /history, /settings)
├── views/
│   ├── Dashboard.vue              ★ 7546 行单体巨组件（含全部内嵌弹窗/日志/拖拽/SSE）
│   ├── TestRun.vue                (演示页，契约已断裂)
│   ├── History.vue                (echarts 手动实例)
│   └── Settings.vue               (占位页，仅写 localStorage)
├── composables/  useApi / useConfig / useLogs / useSSE / useTasks   ★ 全部未被引用（死代码）
└── components/dashboard/
    ├── TreeView.vue / TreeItem.vue / ContextMenu.vue                (实际使用)
    ├── modals/ TestSetManagerModal.vue / StartConfigModal.vue       (实际使用)
    ├── modals/ TaskDetailModal.vue / ModelCaseModal.vue / HistoryModal.vue   ★ 死代码
    ├── LogPanel.vue / TaskCard.vue / DashboardHeader.vue / DashboardSidebar.vue ★ 死代码
    ├── popovers/ CasePopover / ModelPopover / RoundPopover           ★ 死代码
    └── common/ EmptyState / Toast                                   ★ 死代码
```

**核心结论**：约一半源码（≈4700 行组件 + 5 个 composable）是未被任何文件 import 的死代码；而实际运行的主页被塞进一个 7546 行的 `Dashboard.vue`，其中又以"内嵌副本"的形式复刻了 LogPanel、TaskCard、任务详情弹窗、历史弹窗、三类 Popover 的全部逻辑。本次 git 未提交的 `TaskDetailModal.vue` 修改恰好落在一个**未接入渲染树的死组件**上（详见 §4）。

---

## 1. 🔴 高严重度

### H1. SSE 重连逻辑导致 EventSource 泄漏与事件重复 — Dashboard.vue:3521-3542
```ts
eventSource.onerror = () => {
  sseConnected.value = false
  sseStatus.value = 'RETRY'
  setTimeout(connectSSE, 3000)   // ← 未先 close 旧连接
}
```
- **问题**：`EventSource` 原生就会自动重连，断线期间 `onerror` 会**反复触发**，每次都会再排一个 3s 后的 `connectSSE`；而 `connectSSE` 直接 `new EventSource('/events')` 覆盖引用、**从不 close 旧实例**。后端恢复后可能同时存活多个连接：`start` 事件重复创建任务、`chunk` 事件把输出文本重复拼接、`complete` 重复触发。
- **修复**：直接改用仓库里已写好的 `composables/useSSE.ts`（有指数退避 + 重连前 close，可惜是死代码），或在 `onerror` 中先 `eventSource?.close()` 并引入"是否已计划重连"去重标志。

### H2. TestRun.vue 调用不存在的后端路由，页面功能必然 404 — TestRun.vue:502
- 后端真实路由是 `POST /test/start`（web/app.py:1936），前端写的是 `fetch('/api/test/start', ...)`（TestRun.vue:502）。该页另有两处脱节：模型列表硬编码（TestRun.vue:163）；响应字段 `r.ttft / r.tps / data.results`（TestRun.vue:103-105,515）与后端 metrics 的 `ttft_seconds / tokens_per_second` 命名不符。
- **影响**：`router` 中 `/test` 路由仍可达，进入即"开始测试 → 404"。
- **修复**：对齐 `/test/start` 与字段名，或将该演示页从路由移除。

### H3. AI 报告 / 报告预览 XSS — Dashboard.vue:1172-1175, 826；ReportPreviewModal.vue:26,100
`marked`（v12）**不做 HTML 消毒**，`v-html` 直插 AI 模型输出 / 后端报告内容。若 AI 输出包含 `<img onerror=...>` / `<script>` 等即形成存储型 XSS。
- **修复**：渲染前用 `DOMPurify.sanitize()`（引入 dompurify），或改用带安全策略的渲染方式。

### H4. 后端 API Key 等敏感信息明文存储/展示 — Settings.vue:92；Dashboard.vue:719-722
- `saveSettings()` 把 `apiKey` 明文写入 `localStorage`（Settings.vue:92）；Dashboard 模型 Popover 模板含 `{{ modelPopoverData.key }}` 悬停展示逻辑（Dashboard.vue:719-722，若数据形状匹配即会泄露 Key）。
- **修复**：Key 只应在表单中临时持有并仅发送给后端保存，不回传、不落 localStorage。

---

## 2. 🟡 中严重度

### M1. 约 50% 源码为死代码（未被 import）
- **Composables（全部无引用）**：`useApi.ts`、`useConfig.ts`、`useLogs.ts`、`useSSE.ts`、`useTasks.ts`（456 行）。
- **组件（全部无引用）**：`TaskDetailModal`、`ModelCaseModal`(929行)、`HistoryModal`、`LogPanel`(950行)、`TaskCard`(752行)、`DashboardHeader`、`DashboardSidebar`、三个 popovers、`common/EmptyState`、`common/Toast`。
- **依赖**：`axios`、`@vueuse/core`、`pinia`（main.ts:31 注册但**没有任何 store**）均未使用。
- **影响**：维护成本翻倍，且两组实现必然漂移（本次 TaskDetailModal 修复即是最好的例子）。建议按"唯一事实来源"清理：要么把 Dashboard 内嵌逻辑抽回这些组件并接上 import，要么删除未引用文件与依赖。

### M2. 前后端契约不一致清单（详见 §6 核对表）
- **TestRun.vue:502** 路由不存在（H2）。
- **移动用例存在两套端点**：`useConfig.moveTestCase`（死代码）正确使用 `PUT /config/test-cases/{id}/move`（web/app.py:962，含文件夹存在性校验）；而实际渲染的 `Dashboard.vue:2282` 走的是通用 `PUT /config/test-cases/{id}`（web/app.py:1053），绕过校验。
- **TestSetManagerModal.vue:138-146**：`targetFolderId === ''` 时 `prompt('请输入目标文件夹名称')` 收集的是**名称**，却作为 `folder_id` 发给后端 → 后端查不到该 id，移动必然失败（Dashboard.vue:2280-2286 同样把用户输入当 id 用）。
- **ReportPreviewModal.vue:152**：`copyLink` 生成 `/report/{groupId}`，路由表无此路由（死链接）；History.vue 导入了 ReportPreviewModal 但模板从未渲染（History.vue:103,116,361），`showPreview` 是死状态。

### M3. 任务 key 用"名称拼接"而非 ID — Dashboard.vue:1550-1556
`getTaskId = ``${modelName}__${caseName}``。后端用例以 `case_id` 为唯一键，前端以**名称**为键：
- 两个**同名用例**（允许存在于不同文件夹）会互相覆盖任务；
- 名称含 `__` 时 key 碰撞；
- 重命名/删除后 localStorage 里的 selectedCases 引用失效（无清理）。
- **修复**：SSE 事件携带 `case_id` / `test_case_id`（后端已有该信息），前端以 id 为 key。

### M4. 未提交修改（TaskDetailModal.vue）是"修错了地方 + 修不彻底"（专项分析见 §4）

### M5. 双主题变量定义冲突 — App.vue:15-44 vs styles/variables.scss:2-56
- `App.vue` 全局 `:root` 定义 `--primary:#f97316`（橙）、`--gray-*` 一套；`variables.scss` 通过 vite.config.ts:45 的 `additionalData` 注入每个组件，定义 `--primary:#2563eb`（蓝）、`--gray-50` 等另一套。scoped 样式里注入的 `:root` 会被编译成 `:root[data-v-xxx]` 而不匹配 `<html>`，最终生效值取决于级联顺序（App.vue 未 scoped，后置定义胜出）。
- **后果**：`var(--gray-50)`（Dashboard.vue:4004 等）未定义导致 hover 背景失效；主题色"看起来是橙、变量文件里是蓝"，语义分裂。建议只保留一处主题源。

### M6. 图表实例泄漏与竞态 — History.vue:120-122, 405-409
- 三个 `echarts.init` 实例在 `onUnmounted` 未 `dispose`（离开页面泄漏 canvas/监听）；
- `watch(selectedGroup)` + 两处 `setTimeout(renderCharts)`（History.vue:190-193, 405-409）存在竞态：快速切换分组时可能对旧 DOM 初始化。建议用 vue-echarts 组件或统一 `dispose` 并取消定时器。

### M7. useConfig/useApi 的请求错误处理不统一且默认值覆盖用户配置 — useConfig.ts:70-200
- 多个函数不检查 `res.ok`，仅靠 `result.error` 约定（部分接口失败时返回 HTML，`res.json()` 直接抛错）；
- `updateModel` 强制 `enabled:true`、`addTestCase/updateTestCase` 强制 `stream:true, temperature:0.7`（useConfig.ts:89,175,187），覆盖用户已保存的 temperature；`deleteFolder` 内嵌 `confirm()`（useConfig.ts:142），UI 逻辑混入数据层。
- （虽为死代码，若按 M1 接入前应先修正。）

---

## 3. 🟢 低严重度

| # | 位置 | 问题 |
|---|------|------|
| L1 | useSSE.ts:64 | `console.error('...(' + ${MAX_RECONNECT_ATTEMPTS})...')` 用单引号包裹模板插值，运行时原样打印字面量 |
| L2 | Dashboard.vue:173 / CSS:4771 | 内联 `gridTemplateColumns` 作用于 `display:flex` 容器（.round-matrix），样式无效 |
| L3 | Dashboard.vue:1503-1521 | `extractThinkAndAnswer` 第 1、2 段正则完全相同（重复代码），且该函数整体未被调用（全文件仅 1 处出现） |
| L4 | Dashboard.vue:1485-1489, 3027-3033, 1675-1679 | `sortTasks`（空实现）、`toggleExpand`、`escapeHtml` 均为定义后未调用 |
| L5 | Dashboard.vue:3671-3685 | `addLog` 的 `fullTime` 用**本地时钟** `now.toISOString()`，而 `time` 是后端时间；时间范围过滤基于本地时钟，跨时区/时钟偏差时不准确 |
| L6 | Dashboard.vue:3688-3695 | `showToast` 每次调用都开新 `setTimeout` 且不清理旧 timer，快速连点会闪烁 |
| L7 | Dashboard.vue:3584-3595 | `data.metrics?.ttft_seconds?.toFixed(3) || '--'`：当值为 0 时 `(0).toFixed(3)='0.000'` 为真值，显示 "0.000s" 而非 '--'（中断/错误轮次指标全 0 时界面显示 0 而非缺失） |
| L8 | Dashboard.vue:3530-3535 | SSE `handleEvent` 里 `catch (err) {}` 静默吞掉解析错误，无任何日志 |
| L9 | Dashboard.vue:157 | 状态徽标 `doneCount/总数` 每次渲染遍历 `Object.keys(task.sub_tasks).length` |
| L10 | Dashboard.vue:689-724 | 模型 Popover 数据形状（key/publisher/architecture/params_string/quantization…）与 `config.models`（name/endpoint/api_key/model）完全不匹配，popover 实际基本空白（死 UI） |
| L11 | main.ts:5-33 + TestRun.vue:141-160 | echarts 按需注册执行两次（全局 + 页面内），幂等但冗余 |
| L12 | vite.config.ts:12-40 | 代理按路径前缀逐个罗列（/api /config /test /events /status /reset），与后端路由列表强耦合，新增前缀易漏 |

---

## 4. 专项：TaskDetailModal.vue 未提交修改分析

**diff 内容**（git diff，6 行）：三处 `v-if` 由真值判断改为 `!== undefined && !== null`（answerSpeed / thinkTokens / answerTokens）。

**审查结论（三个问题）**：

1. **改错文件（最关键）**：全项目 grep 无任何 `import TaskDetailModal`，该组件是死代码。实际渲染的是 `Dashboard.vue:483-602` 的**内嵌任务详情弹窗**，其中仍是旧判断（Dashboard.vue:545 `v-if="subTask.metrics.answerSpeed"`、556-557 thinkTokens/answerTokens）。因此本次修改**对线上 UI 零效果**，真正的修复应落在 Dashboard.vue 内嵌弹窗（或按 M1 把组件接回渲染树）。

2. **修改本身对实际数据是 no-op**：metrics 对象在 Dashboard.vue:3584-3595（SSE complete）与 3756-3771（/status 恢复）两处构造，**始终以 `|| '--'` 兜底**，即 `answerSpeed/thinkTokens/answerTokens` 只可能是数字转字符串或字面量 `'--'`，永远不为 `undefined/null`。新条件与旧真值判断对真实数据等价，只是"意图更清晰"。

3. **真正缺陷仍未修复**：无该指标时（如非思考模型），界面仍会渲染 `(Answer: -- t/s)`。正确守卫应排除 `'--'`：
```html
<span v-if="m.answerSpeed !== undefined && m.answerSpeed !== null && m.answerSpeed !== '--'">
```
或在指标映射层用 `null` 表示缺失（推荐：一处修复，全端生效）。

---

## 5. 类型安全

- **tsconfig 已开 `strict:true` + `noUnusedLocals/Parameters`（tsconfig.json:14-17）**，但源码大量逃逸到 `any`：
  - Dashboard.vue:847 `config = ref<any>({})`；1130 `taskDetailData = ref<any>({})`；1134 `historyList = ref<any[]>([])`；1140 `popoverData = ref<any>({})`；935 `metrics: any`；
  - TestRun.vue:170 `results = ref<any[]>([])`；History.vue:105 `history = ref<any[]>([])`；图表 formatter 参数 `params: any`（TestRun.vue:255 等）；`catch (e: any)`（Dashboard.vue:518 等）。
- **没有后端响应类型层**：`Config/Model/TestCase` 定义在 useConfig.ts（死代码）里，Dashboard 自建一份更宽松的接口并大量 `any`，两端类型漂移。
- **构建不含类型检查**：`build` 仅 `vite build`（package.json:8），vue-tsc 未接入，类型错误不阻断发布。
- **建议**：以 `src/types/api.ts` 统一定义后端契约类型（字段名与 web/app.py 返回值对齐），Dashboard 等改用之；把 `any` 收敛到边界（SSE 解析处），并将 `vue-tsc --noEmit` 加入 CI/build。

---

## 6. 前后端交互契约核对表（前端调用 → 后端路由 web/app.py → 结论）

| 前端调用（位置） | 后端路由 | 结论 |
|---|---|---|
| GET /config（Dashboard.vue:3700） | GET /config (214) | ✅ |
| POST/PUT/DELETE /config/models(/{name})（Dashboard.vue:2481,2546,2601） | 347 / 430 / 553 | ✅ |
| POST /config/models/ping（Dashboard.vue:3450） | 608 | ✅ |
| POST/PUT/DELETE /config/test-cases(/{id})（Dashboard.vue:2516,2584,2611） | 840 / 1053 / 1428 | ✅（字段名一致） |
| PUT /config/test-cases/{id}/move（useConfig.ts:156，死代码） | 962 | ✅（但实际渲染的 Dashboard.vue:2282 走通用 PUT，见 M2） |
| GET/POST/PUT/DELETE /config/test-case-folders(/{id})（Dashboard.vue:2222,2262,2303） | 1229 / 1254 / 1300 / 1379 | ✅ |
| POST /test/start body{models,cases,test_rounds,max_concurrent,interval,test_name}（Dashboard.vue:2646-2657） | 1936（同名字段） | ✅；响应 `config.{models,cases,total_rounds,concurrency}` 与 Dashboard.vue:2666-2676 读取一致 |
| POST /test/stop / GET /test/status / GET /status / POST /reset | 2292 / 2346 / 139 / 159 | ✅；/status 的 rounds.metrics 键（ttft_seconds…）与 Dashboard.vue:3756-3771 转换一致 |
| GET /events SSE（Dashboard.vue:3523） | 90 | ✅；事件字段见下 |
| GET /api/analysis?model_name=（Dashboard.vue:1199-1206） | 1554（model_name 参数一致） | ✅ |
| GET /api/history?limit / GET /api/history/{id}/results / DELETE /api/history/{id} | 2358 / 2434 / 2481 | ✅ |
| GET /api/models（History.vue:140） | 2529 | ✅ |
| GET /api/history/{id}/report/{pdf,markdown,excel,all}（History.vue:366-385） | 2580 / 2705 / 2601 / 2633 | ✅ |
| GET /api/report/templates（ReportPreviewModal.vue:77） | 2621 | ✅ |
| **POST /api/test/start（TestRun.vue:502）** | **不存在** | ❌ 404（H2） |

**SSE 事件字段核对**（emitter.py ↔ Dashboard.vue handleEvent:3544-3667）：
- `start`: {models, test_cases, total_rounds} ✅（Dashboard.vue:3555-3564）
- `progress`: {model_name, test_case_name, current_round, total_rounds} ✅（3567-3572）
- `chunk`: {content, …} ✅（3574-3578）
- `complete`: {metrics(ttft_seconds/tpft_seconds/output_tokens/tokens_per_second/think_time_seconds/answer_time_seconds/think_tokens/answer_tokens/think_tokens_per_second/answer_tokens_per_second), success, prompt, response, evaluation{is_correct,rate,reason}, think_content, answer_content, input_images} ✅（与 metrics.py:186-203 to_dict 及 main.py:1009-1023 完全对齐）
- `summary`: {total_duration_seconds} ✅（3643-3655）
- `error`: {error} ✅（3657-3666）

---

## 7. 性能

| 项 | 位置 | 评估 |
|---|---|---|
| SSE chunk 高频 `output +=` 拼接 | Dashboard.vue:3574-3578 | 每个 chunk 触发响应式重渲染；大输出 + 多任务时为主要瓶颈。可节流/批量 flush，或用非响应式缓冲 + rAF 更新 |
| 每秒 `setInterval` 更新 `now` | Dashboard.vue:1580-1588 | 所有卡片每秒重算 `getTaskDuration`，任务多时无谓重渲染 |
| 轮次矩阵每按钮 `Object.keys().indexOf` | Dashboard.vue:1558-1561,175-184 | 每渲染 O(n²)；100 轮 × 多任务时可见 |
| 日志过滤 | Dashboard.vue:989-1017 | 上限 100 条，每次输入全量过滤，可接受 |
| ECharts 用法 | TestRun.vue 用 vue-echarts `autoresize`（✅ 合理）；History.vue 手动 init 且未 dispose（❌ M6） | 混用两种模式，建议统一 vue-echarts |
| 列表渲染 | 规模小（models/用例/任务卡片），无虚拟滚动需求 | 可接受 |

---

## 8. 修复优先级建议

1. **P0（功能/安全）**：H1 SSE 重连泄漏；H2 TestRun 404；H3 XSS（引入 DOMPurify）；H4 Key 泄露。
2. **P1（正确性）**：§4 的 TaskDetailModal 修复落到 Dashboard.vue 内嵌弹窗并排除 `'--'`；M2 移动用例端点/输入统一；M3 任务 key 改用 id。
3. **P2（可维护性）**：M1 死代码清理（或"抽组件并接线"二选一）；M5 主题变量归一；M6 图表 dispose；M7 统一 API 层（激活 useApi/useConfig 前先修其缺陷）。
4. **P3（工程化）**：类型收敛 + vue-tsc 入 CI；删除 axios/@vueuse/pinia 死依赖。

---

*（报告文件路径：frontend-code-review-report.md；所有行号基于当前工作区文件内容与 git HEAD diff 核对）*