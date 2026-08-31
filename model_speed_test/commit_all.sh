#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix: task.md 待办全量处理 — 校对配置/config瘦身/超长输出/转义/路由清理

- scripts/config_eval_model.py: 批量配置校对模型工具（553/553 官方题已配置
  MiniMax-M2.7-Highspeed），修复官方题跑评测时 AI 校对被跳过的问题
- GET /config 增加轻量模式：messages 超 2000 字符替换为占位符
  （响应 9MB 降到 647KB，-93%），新增 /config/test-cases/{id}/full 完整端点
- 修复 3 道原捞针题 max_tokens=-1 → 2048
- report_generator.py: 启用 Jinja2 autoescape（原空元组=未生效）
- 路由移除 /test 死页（TestRun.vue 文件保留）
- 裸 except 清零（main.py 2处 + logging_utils.py 1处）"
echo EXIT=$?
