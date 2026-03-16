#!/usr/bin/env python3
"""
Python SDK 使用示例
"""
from model_speed_test import ModelSpeedTest

# 初始化客户端
client = ModelSpeedTest(
    base_url="http://localhost:15010",
    api_key="your-api-key"  # 可选
)

# 1. 获取配置
print("=== 获取配置 ===")
config = client.get_config()
print(f"模型数量: {len(config.get('models', []))}")
print(f"测试用例数量: {len(config.get('test_cases', []))}")

# 2. 添加模型
print("\n=== 添加模型 ===")
new_model = client.add_model({
    "name": "GPT-4",
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "api_key": "sk-xxx",
    "model": "gpt-4",
    "provider": "openai",
    "enabled": True
})
print(f"添加模型结果: {new_model}")

# 3. 启动测试
print("\n=== 启动测试 ===")
result = client.start_test(
    models=["MiniMax-M2.5-HighSpeed"],
    cases=["tc_ontology_1"],
    test_rounds=5
)
print(f"启动结果: {result}")

# 4. 监听事件流
print("\n=== 监听事件 ===")
for event in client.events():
    print(f"事件: {event}")
    # 处理事件...
    # event 示例: {"type": "progress", "data": {...}}

# 5. 获取状态
print("\n=== 获取状态 ===")
status = client.get_status()
print(f"测试状态: {status}")

# 6. 获取历史
print("\n=== 获取历史 ===")
history = client.get_history(limit=10)
print(f"历史记录: {history}")

# 7. 配置 Webhook
print("\n=== 配置 Webhook ===")
webhook = client.configure_webhook(
    url="https://your-server.com/webhook",
    events=["test_complete", "test_error"],
    secret="your-secret"
)
print(f"Webhook 配置: {webhook}")

# 8. 停止测试
print("\n=== 停止测试 ===")
stop_result = client.stop_test()
print(f"停止结果: {stop_result}")