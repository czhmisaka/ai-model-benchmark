<!--
 * @Date: 2026-03-02 10:03:43
 * @LastEditors: CZH
 * @LastEditTime: 2026-05-20 14:20:43
 * @FilePath: /模型速度测试/task.md
-->
# AI 智能分析功能 - MiniMax M2.7 任务

## 目标
- 在 Dashboard 页面添加「AI 智能分析」按钮
- 点击按钮后收集当前页面上所有测评任务数据
- 调用 MiniMax M2.7 模型进行智能分析
- SSE 流式展示 Markdown 格式分析报告

## 任务清单

- [x] **前端按钮开发**：在 Dashboard 页面的 header 添加「AI 智能分析」按钮（`Dashboard.vue`）
- [x] **前端 Modal 开发**：创建展示分析报告的 Modal（流式输入 Markdown 内容）
- [x] **前端 SSE 逻辑**：实现 `runAiAnalysis()` 函数，使用 EventSource 接收后端流式分析结果
- [x] **前端样式**：添加 AI 分析专用的 UI 样式（Modal + 按钮 + report 内容）
- [x] **后端 API 端点**：`app.py` 中已有 `GET /api/analysis`（第 1165 行），直接使用 MiniMax API 流式生成报告
- [x] **修复重复端点**：删除 `app.py` 中重复的 `POST /api/analysis`（第 2021 行）及其辅助函数
- [x] **重启服务验证**：重启后端服务并验证分析功能是否正常工作
