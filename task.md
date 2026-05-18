# 模型测试报告导出系统开发计划

## 项目目标
为模型速度测试系统添加完整的报告导出功能，支持 PDF、Markdown、Excel 格式，以及实时图表可视化。

## 已完成的功能 ✅

### 阶段一：依赖更新
- [x] 更新 requirements.txt（添加 reportlab, openpyxl, markdown, jinja2）
- [x] 更新 package.json（添加 marked 依赖）

### 阶段二：后端报告服务
- [x] 创建 report_generator.py - Markdown/PDF 报告生成器（含 Jinja2 模板引擎）
- [x] 创建 excel_exporter.py - Excel 导出器
- [x] 更新 web/app.py - 添加报告 API 端点（PDF、Excel、Markdown）+ template 参数

### 阶段三：前端报告预览
- [x] 创建 ReportPreviewModal.vue - 报告预览弹窗组件
- [x] 更新 History.vue - 添加导出按钮（PDF、Markdown、Excel、预览）
- [x] 添加导出按钮样式

### 阶段四：TestRun.vue 实时图表
- [x] 添加实时图表组件（使用 ECharts/vue-echarts）
- [x] 实现实时数据更新（TTFT趋势 / TPS趋势 / Token分布 / 成功率饼图）

### 阶段五：Markdown Jinja2 模板系统
- [x] 创建 Jinja2 模板文件（default_report.md.j2 / minimal_report.md.j2）
- [x] 重写 report_generator.py 使用 Jinja2 模板引擎
- [x] web/app.py 报告端点添加 template 参数支持
- [x] 添加 `/api/report/templates` 端点列出可用模板

### 阶段六：Bug 修复
- [x] 修复 StreamChunk 流式解析逻辑（OpenAI Provider）
- [x] 修复 ReportPreviewModal.vue exportMarkdown 下载内容为 JSON 的问题

## 待完成的功能 📋

- [x] 报告预览支持模板切换（下拉选择 + 切换实时刷新 + 导出参数联动）
- [x] PDF 报告格式美化（字体、排版、页面布局）
- [x] 测试全部报告导出功能（Markdown、HTML/PDF、Excel 均通过验证）
- [ ] 添加中文语言支持（前端国际化，涉及 30+ 文件，建议作为下期独立任务）

## 代码审查修复 ✅ (2026-04-28)

- [x] 修复 test_minimax.py 硬编码 API key → 改用环境变量 `YIDONGYUN_API_KEY`
- [x] 修复 test_modelclient.py 硬编码 API key → 改用环境变量 `YIDONGYUN_API_KEY`
- [x] 修复 test_yidongyun_api.py 硬编码 API key → 改用环境变量 `YIDONGYUN_API_KEY`
- [x] 修复 test_yidongyun_thinking.py 硬编码 API key → 改用环境变量 `YIDONGYUN_API_KEY`
- [x] 审查 web/app.py 未使用 imports → 确认 `threading/inspect/ctypes/datetime/Jinja2Templates` 均有使用
- [x] 审查 excel_exporter.py 死代码 → 确认 `export_to_excel` 被 `web/app.py` 引用，无死代码

## 技术栈

### 后端
- Python 3.8+
- Jinja2（模板引擎）
- WeasyPrint（HTML → PDF）
- OpenPyXL（Excel 导出）

### 前端
- Vue 3 + TypeScript
- ECharts（图表）
- Marked（Markdown 解析）

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/history/{group_id}/report/pdf` | GET | 生成 PDF 报告（支持 `?template=xxx`） |
| `/api/history/{group_id}/report/excel` | GET | 生成 Excel 报告 |
| `/api/history/{group_id}/report/markdown` | GET | 获取 Markdown 内容（支持 `?template=xxx`） |
| `/api/report/templates` | GET | 列出可用报告模板 |

## 下一步
1. ~~PDF 报告格式美化~~ ✅
2. ~~测试全部报告导出功能~~ ✅
3. 添加中文语言支持
