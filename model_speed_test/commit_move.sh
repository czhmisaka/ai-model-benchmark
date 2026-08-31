#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix(benchmark): 修复用例移动后 folder_id 序列化不一致（null 被转为空串）

问题：6 处响应构建使用 row['folder_id'] or ''，把 DB 中的 NULL（移到根目录）
序列化为空串。前端树/移动逻辑按 null 语义判断，'' 与 null 混用导致
移动到根目录后状态显示不一致。

修复：
- 统一 6 处序列化：folder_id 透传 NULL（不再 or ''）
- 实测：move-to-root 返回 null、move-to-folder 精确匹配，双向验证通过"
echo EXIT=$?
