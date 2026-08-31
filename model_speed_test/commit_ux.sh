#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix(ui): 体验优化 — 中文文案统一 + fetch 超时防护 + 删除反馈补齐

- 12 处英文 toast 本地化（Model added→模型已添加、Please fill→请填写 等）
- 删除确认对话框英文文案中文化（Delete Model→删除模型）
- Dashboard 增加 fetchWithTimeout：/test/start(30s)、/test/stop(25s) 超时防护，
  防止后端挂起时 UI 无限等待
- History 删除操作补 try/catch 与失败日志
- Settings 保存反馈生效（按钮文案变化）"
echo EXIT=$?
