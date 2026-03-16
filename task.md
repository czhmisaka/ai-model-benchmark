<!--
 * @Date: 2026-03-02 10:03:43
 * @LastEditors: CZH
 * @LastEditTime: 2026-03-16 09:40:00
 * @FilePath: /模型速度测试/task.md
-->
# 任务列表

## 模型速度测试项目

### 已完成

- [x] 扩展数据库，添加 models、test_cases、datasets 表
- [x] 修改 web/app.py API 端点操作数据库
- [x] 添加数据迁移逻辑（JSON -> 数据库）
- [x] 测试验证功能正常

### 说明

已将模型配置和测试用例配置从 JSON 文件迁移到 SQLite 数据库：

1. **数据库位置**: `results/config.db`
2. **API 端点**: `/config` 现在从数据库读取配置
3. **数据迁移**: 首次启动时自动从 `config/config_fixed.json` 导入
4. **测试结果数据库**: 保持使用 `results/test_results.db`

保留 JSON 文件作为备份，可手动删除。

---

### 2026-03-12 模型添加

- [x] 添加 MiniMax-M2.5 模型
  - API Key: sk-sp-258bcc0908d2444c91f79ea02c213125
  - Endpoint: https://coding.dashscope.aliyuncs.com/v1/chat/completions
  - 模型名称: MiniMax-M2.5
  - 状态: 已启用

### 2026-03-12 Think Token 记录

- [x] 数据库添加 think_tokens 相关字段
  - 新增字段: think_tokens, answer_tokens, think_time_seconds, answer_time_seconds
  - 更新 database.py 的 add_result 方法以保存这些字段
  - 确保与 TestMetrics.to_dict() 字段名一致

### 2026-03-12 LMStudio 模型输出问题修复

- [x] 问题：LMStudio (Qwen3.5) 模型输出为空
  - 原因：LMStudio 使用 `reasoning_content` 字段返回思考过程，而非 `content` 字段
  - 修复：修改 client.py 流式处理逻辑，同时处理 `content` 和 `reasoning_content` 字段
  - 位置：第 486-488 行和第 524-526 行

- [x] 问题：保存测试结果失败 (22 values for 21 columns)
  - 原因：旧数据库文件字段数量不匹配
  - 修复：删除旧的 test_results.db 并重新创建
  - 状态：已重新创建数据库，问题已修复

- [x] LMStudio (Qwen3.5) Think/Answer 分离问题
  - 原因：LMStudio 使用 `reasoning_content` 字段返回思考过程，但代码没有正确设置 is_think 标志
  - 修复：修改 client.py 中的两处流式处理逻辑，分别处理 reasoning_content 和 content
    - reasoning_content 设置 is_think = True（Think 内容）
    - content 设置 is_think = False（Answer 内容）
  - 位置：第 486-517 行和第 555-598 行
  
- [x] LMStudio 模型输出被截断问题
  - 原因：测试用例的 max_tokens=500 不够，模型还在输出 Answer 时就达到上限
  - 验证：通过增加 max_tokens=4096 测试，确认可以正确输出 Answer
  - 结论：需要确保测试用例的 max_tokens 足够大（至少 2000-4096）

- [x] 前端显示 Think/Answer 统计问题
  - 原因：metrics.py 使用 '<think>' 标签检测 Think，但 LMStudio 使用 is_think 字段
  - 修复：修改 metrics.py 优先使用 is_think 标志检测 Think 内容
  - 状态：已修复代码，需要重新测试验证

### 2026-03-13 错误修复

- [x] 问题：流式请求错误 `object of type 'NoneType' has no len()`
  - 原因：MiniMax API 返回 `reasoning_content: null` 时，`delta.get("reasoning_content", "")` 返回 `None`
  - 修复：client.py 第 489 行和 620 行改为 `delta.get("reasoning_content") or ""`

- [x] 问题：保存测试结果失败 `22 values for 21 columns`
  - 原因：emitter.py 传入参数与 database.py 期望的不匹配，缺少 output_text 参数
  - 修复：emitter.py 正确传入 output_text 参数，database.py 移除所有截断逻辑（不截断任何内容）

### 2026-03-16 日志模块优化

- [x] 优化 useLogs.ts composable
  - 新增日志级别类型定义 (LogLevel, FilterType)
  - 新增日志统计功能 (LogStats)
  - 支持区分大小写搜索和正则表达式搜索
  - 支持时间范围筛选
  - 日志数量限制从 100 提升到 500 条
  - 新增 markAllAsRead、getRecentErrors 等辅助函数

- [x] 优化 LogPanel.vue 组件
  - 新增日志级别统计指示器（错误、警告、成功、进行中数量）
  - 新增高级搜索面板（区分大小写、正则表达式选项）
  - 新增警告、成功级别的过滤按钮
  - 新增自动滚动开关按钮
  - 日志项支持展开/折叠查看完整内容
  - 新增滚动到顶部按钮
  - 优化日志项交互体验（悬停显示操作按钮）
  - 支持双击展开日志详情
  - 支持 Escape 键清空搜索
