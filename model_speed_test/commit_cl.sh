#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "refactor(benchmark): 移除自研38题，仅保留 zx-bench 官方题库并规范命名

- 删除自研 zx_ 38题及 zx评测题库 文件夹树（与官方题库内容重叠）
- 文件夹重命名：去掉'官方-'前缀（编程/数学推理/幻觉抵抗 等 10 个）
- scripts/import_zx_official.py: DIM_LABELS 同步去前缀
- 当前题库：553 题（官方全量，跳过21题Docker执行类）+ 18 原有用例"
echo EXIT=$?
