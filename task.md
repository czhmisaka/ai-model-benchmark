<!--
 * @Date: 2026-03-02 10:03:43
 * @LastEditors: CZH
 * @LastEditTime: 2026-03-16 11:10:17
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

### 2026-03-16 添加多轮对话测试用例

- [x] 添加"技术深度问答-分布式系统"测试用例到数据库
  - case_id: tc_multi_round_distributed_system
  - 类型: multi_round
  - 描述: 用于测试长上下文下的模型输出速度。真正测试的是最后一轮的响应速度
  - 10轮对话，每轮包含 user 和 assistant 消息
  - 存储位置: results/config.db test_cases 表

- [x] 数据结构映射方案
  - 每轮对话展开为独立的 messages 对
  - metadata 保存场景元信息（scenario_id, total_rounds 等）
  - 符合项目现有数据库结构

### 2026-03-16 并发/输出/阈值配置迁移到数据库

- [x] 将 concurrency、output、thresholds 配置迁移到 SQLite 数据库
  - 在 results/config.db 添加 system_config 表
  - 存储三个配置项：concurrency（并发配置）、output（输出配置）、thresholds（阈值配置）
  - 修改 web/app.py 的 /config 接口从数据库读取
  - 修改 main.py 的 load_config 函数从数据库读取
  - 添加 PUT /config/system 接口用于保存配置到数据库
  - 删除 config.json 文件（不再需要）

### 2026-03-16 添加 qwen3_5 模型

- [x] 添加 qwen3_5 模型到数据库
  - Endpoint: http://20.6.2.59:8026/v1/chat/completions
  - 模型名称: qwen3_5
  - 提供商: custom
  - 状态: 已启用
  - 记录ID: 18

### 2026-03-16 修复模型编辑 API

- [x] 修复模型编辑功能无法保存 API Key 的问题
  - 原因：PUT /config/models 接口只操作 JSON 文件，没有操作数据库
  - 修复：修改 app.py 中所有模型相关接口（添加/更新/删除）都操作 SQLite 数据库
  - 状态：需要重启后端服务生效

### 2026-03-16 修复 qwen3_32b/qwen3_5 模型 API Key

- [x] 问题：测试时出现 "API Key 未正确展开" 警告
  - 原因：qwen3_32b 和 qwen3_5 模型的 API Key 为空字符串
  - 这两个模型连接的是本地 LM Studio 服务（http://20.6.2.59:8025/8026），不需要 API Key
  - 修复：更新数据库中两个模型的 api_key 为 "not-needed"
  - 状态：✅ 已修复

### 2026-03-16 修复前端更新模型后列表置空问题

- [x] 问题：在前端页面编辑/更新模型后列表置空
  - 原因：后端 API (PUT /config/models/{name}) 只返回 `{"status": "success"}`，没有返回更新后的模型列表
  - 前端代码期望 API 返回 `models` 列表来更新本地状态
  - 修复：修改 app.py 中以下 API 端点，返回更新后的列表：
    - POST /config/models (添加模型)
    - PUT /config/models/{model_name} (更新模型)
    - DELETE /config/models/{model_name} (删除模型)
    - PUT /config/test-cases/{test_case_id} (更新测试用例)
    - DELETE /config/test-cases/{test_case_id} (删除测试用例)
  - 状态：✅ 已修复并重启服务

### 2026-03-16 修复测试轮次完成状态不更新问题

- [x] 问题：模型输出结束后没有判定成当前轮次请求完成
  - 原因：emit_complete() 只更新了 test_results 表，但没有更新 test_groups 表的 completed_rounds
  - 只有当 emit_summary() 被调用时（测试全部完成），才会更新 test_groups 表的状态
  - 数据库证据：test_results 表有数据（如 11 条），但 test_groups 表的 completed_rounds=0，status=running
  - 修复：
    1. 在 emitter.py 添加 _update_group_progress() 方法
    2. 在 emit_complete() 中调用 _update_group_progress() 更新数据库
    3. 在 emit_error() 中也调用 _update_group_progress() 更新数据库
  - 状态：✅ 已修复代码

### 2026-03-17 代码清理

- [x] 删除不再需要的备份文件
  - config/config.json.bak (已迁移到数据库)
  - frontend/src/views/Dashboard.vue.bak_full
  - frontend/src/views/Dashboard.vue.bak2

- [x] 删除未使用的源代码
  - src/model_manager.py (使用 JSON 文件，已被数据库替代)
  - config/evaluation_datasets.py (未被引用)

### 2026-03-17 修复模型编辑和参数功能

- [x] 修复模型编辑时名称可以修改
  - 前端：移除 Name 输入框的 disabled 限制
  - 后端：更新 API 处理名称变更逻辑，检查新名称是否已存在
  - 前端：名称变更后更新选中状态（selectedModels）
  - 状态：✅ 已完成

- [x] 修复前端编辑模型时加载参数
  - 后端：更新 add_model、update_model、delete_model API 返回完整参数字段
  - 前端：editModel 函数填充所有参数（temperature, top_p, max_tokens 等）
  - 状态：✅ 已完成

- [x] 数据库已包含模型参数字段
  - temperature, top_p, max_tokens, presence_penalty, frequency_penalty, thinking_enabled
  - 状态：✅ 已存在
