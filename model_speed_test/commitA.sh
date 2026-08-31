#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "perf+refactor(frontend/backend): 优化批次A — 竞态修复/死代码清理/客户端收敛

- History.vue: 图表渲染竞态修复（scheduleRender 统一调度 + 渲染守卫 + timer 清理）
- Dashboard.vue: 死代码删除（40 个未使用符号：日志面板拖拽/旧popover/空实现，-390 行）
- tsconfig: noUnusedLocals/noUnusedParameters 重新开启（0 报错零容忍）
- TreeView/ContextMenu/Settings/TestRun/History: 未使用导入清理
- main.py: create_clients 收敛为 ModelClient 单入口（删除 ProviderAdapter 直调与 3 层回退链）；
  eval_client 创建逻辑简化（-60 行嵌套 try/except）
- client_adapter.py 已无调用方（保留文件备查）"
echo EXIT=$?
