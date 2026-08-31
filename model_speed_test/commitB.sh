#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "refactor(backend): 优化批次B — 错误处理统一 + 指标口径透明化 + DB增量写

- web/app.py: 统一错误处理（AppError + 全局handler），28处 str(e) 回显改为
  规范HTTP状态码+服务端日志；16处裸except清零（12处改精确JSONDecodeError）
- metrics.py: tokens_source 字段透明化（api_usage/tiktoken_estimate）；
  修复 usage=0 时不回退重算的bug（单测抓出）
- tests/test_tokens_source.py: 4个口径单测
- database.py: 新增 increment_group_progress 增量UPDATE（替代每轮全表COUNT）
- emitter.py: _update_group_progress 改用增量方法（减少并发写放大）"
echo EXIT=$?
