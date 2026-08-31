# 项目功能审查 — 修改计划

> **审查时间**：2026-08-31
> **审查方式**：逐文件通读（后端 src/web/main + 前端 views/components/composables）
> **状态标记**：☐ 待处理 | ☑ 已完成 | ⚠️ 有争议/需决策

---

## 一、已发现的待修改项（逐文件扫描中，持续追加）


### 后端（30 个 Python 文件扫描完成）

#### main.py
- [ ] print 输出 94 处（生产应统一 logging + 级别控制）
- [ ] 巨型函数：_run_stream_test_with_events（397行）、run_tests_with_web（261行）、run_concurrent_tests（110行）、main（120行）
- [x] 裸 except 2 处 已完成

#### web/app.py
- [ ] 巨型函数：ai_analysis 加 event_generator（合计660行）、start_test 加 run_test（600行）、update_test_case（126行）、get_config（129行）
- [ ] 硬编码 results/config.db 路径 15+ 处（应提取 config_repo）
- [ ] 模型/用例 SELECT 加构建列表代码重复 10+ 处
- [x] 错误处理统一（AppError，28处 str(e) 已改）
- [x] 裸 except 清零（16 到 0）

#### src/tester.py
- [ ] 巨型函数：_test_stream（225行）、_test_nonstream（128行）、run_enhanced_concurrent_test（133行）
- [ ] run_enhanced_concurrent_test（含 RateLimiter 完整实现）零调用方，死代码，应删除或接线
- [ ] print 输出 100 处

#### src/database.py
- [ ] _init_tables（101行）schema 定义内联
- [x] WAL 加 foreign_keys 已开启；连接管理无泄漏

#### web/emitter.py
- [ ] emit_complete（129行）
- [x] DB 调用已委托线程池（7处）

#### web/report_generator.py
- [ ] _generate_full_html_template（387行）HTML 模板硬编码在 Python，应外置 Jinja2

### 功能配置问题（影响评测效果）

- [x] 官方 553 题全部未配 eval_model 已完成（校对模型）：跑官方题时跳过 AI 校对，看不到正确率/rate。修复：导入脚本增加自动配置 eval_model 选项，或提供批量配置端点
- [x] 海底捞针题 max_tokens=-1 已完成（不限制）配长文档时部分模型输出超长回答，建议 1024
- [x] GET /config 响应 9MB 已完成（553题完整 messages 含60万字符捞针文档全部下发）导致前端加载慢。修复：列表端点剥离 messages 全文

### 前端（33 个源文件扫描完成）

- [x] 未使用符号 0（noUnusedLocals 零容忍）
- [ ] any 类型 44 处（集中在 Dashboard SSE 处理和任务卡）
- [ ] console.log 残留 12 处
- [ ] Dashboard.vue 7373 行（技术债，维持）
- [x] TestRun.vue 已完成（795行）：功能全坏演示页，无导航入口但路由可达，建议从路由移除

### 检查过确认正常的功能

- [x] 全部 42 个 API 端点响应正常（含异常输入容错）
- [x] 前后端契约（API 路径/SSE 事件字段）逐项一致
- [x] SQL 全参数化；WAL 加 foreign_keys 生效
- [x] 捞针题质量：针位置精确、答案全文唯一
- [x] 并发控制：max_concurrent 信号量跨模型共享生效
- [x] 协作式停止：stop_event 加 try/finally 复位

### 补充扫描发现（report_generator.py / evaluation_service.py）

- [ ] web/report_generator.py:33 autoescape=select_autoescape(enabled_extensions=()) 空元组=自动转义未生效
- [ ] generate_html/markdown 转 HTML 无消毒：模型输出含 HTML/script 标签会进入 PDF/HTML 报告（显示异常面）
- [ ] evaluation_service.py:129 extract_answer_only 的 THINK 清理正则可能吞掉答案内容（边界待测）

### 评测功能缺口（建议增补）

- [ ] 官方题批量配置校对模型：脚本或端点一键为 553 题设置 eval_model（当前仅 8 题配置）
- [ ] 长上下文题的 expected_output 建议补充 needle 精确匹配模式（而非 AI 校对，降低不确定性）
