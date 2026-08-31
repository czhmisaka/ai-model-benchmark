#!/bin/bash
cd /Volumes/mobileDisk/test/模型速度测试
git add -A model_speed_test/
git commit -m "fix(concurrency): 修复 Web 模式 max_concurrent 并发控制失效

检查结论：
- ConcurrentTester（CLI --concurrent）：concurrency + interval 生效，正常
- run_enhanced_concurrent_test（含 RateLimiter 令牌桶）：零调用方，死代码
- Web 主路径（/test/start）：max_concurrent 被读取但从未使用，
  N模型xM用例全部同时发出请求，无任何并发度限制 —— 已修复

修复：
- run_tests_with_web 增加 case_semaphore 参数（用例级并发信号量）
- web/app.py 创建跨模型共享的信号量传入（总在途请求 = max_concurrent）
- 信号量在轮间等待时释放（不占坑）
- tests/test_concurrency.py: 3 个并发控制单测（峰值约束/跨组共享/间隔不占坑）"
echo EXIT=$?
