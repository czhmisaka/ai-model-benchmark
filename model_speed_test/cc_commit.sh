#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix: task.md 待办批量处理 — 校对配置/config瘦身/超长输出/转义/路由清理

- scripts/config_eval_model.py: 批量配置校对模型工具
- 官方553题已全部配置 eval_model=MiniMax-M2.7-Highspeed
  （修复官方题跑评测时AI校对被跳过的问题）
- web/app.py: GET /config 轻量模式（messages超2000字符替换占位符，
  响应9MB降至647KB），新增 /config/test-cases/{id}/full 完整端点
- 3道原捞针题 max_tokens -1 修复为 2048
- main.py: 2处裸except修复
- src/logging_utils.py: 1处裸except修复
- report_generator.py: 启用 Jinja2 autoescape
- router: 移除 /test 死页路由"
echo EXIT=$?
