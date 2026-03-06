# AI模型速度测试框架

用于测试多种AI模型的调用速度、输出输入记录。

## 功能特性

- **统一API接口** - 使用OpenAI兼容格式，支持任意模型
- **多指标测试**:
  - TTFT (Time To First Token) - 首Token响应时间
  - TPFT (Time Per First Token) - 排除首Token后的生成时间
  - Total Time - 总响应时间
  - Tokens/sec - 吞吐量
- **并发测试** - 支持多并发请求
- **输入输出记录** - 保存每次调用的prompt和response

## 项目结构

```
model_speed_test/
├── config/
│   ├── models.yaml          # 模型配置文件
│   └── settings.yaml        # 测试参数配置
├── src/
│   ├── __init__.py
│   ├── client.py            # 统一API客户端
│   ├── tester.py            # 核心测试逻辑
│   ├── metrics.py           # 指标计算
│   └── recorder.py          # 输入输出记录器
├── results/                 # 测试结果输出目录
├── main.py                  # 入口脚本
└── requirements.txt         # 依赖
```

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### 1. 模型配置 (config/models.yaml)

```yaml
models:
  - name: "gpt-4o"
    endpoint: "https://api.openai.com/v1/chat/completions"
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
```

### 2. 测试设置 (config/settings.yaml)

```yaml
test:
  prompt: "请用一句话介绍人工智能的发展历史。"
  max_tokens: 500
  temperature: 0.7
  stream: true

concurrency:
  num_requests: 1
  test_rounds: 3
  interval: 1
```

## 使用方法

### 基本测试

```bash
cd model_speed_test
python main.py
```

### 指定模型测试

```bash
python main.py --models gpt-4o gpt-4o-mini
```

### 并发测试模式

```bash
python main.py --concurrent
```

### 自定义配置

```bash
python main.py --config config/models.yaml --settings config/settings.yaml
```

## 输出结果

测试结果会保存在 `results/` 目录：

- `io_records_*.jsonl` - 详细的输入输出记录
- `logs/` - 每次调用的详细日志
- `summary.json` - 汇总统计结果
- `summary_*.csv` - CSV格式导出

## 测试指标说明

| 指标 | 说明 |
|------|------|
| TTFT | Time To First Token，首Token响应时间 |
| TPFT | Time Per First Token，排除首Token后的生成时间 |
| Total Time | 完整响应时间 |
| Tokens/sec | 吞吐量（每秒输出token数） |