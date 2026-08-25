# AI模型速度测试框架

用于测试多种AI模型的调用速度，支持流式/非流式、并发、多模态、定时任务与报告导出。

## 功能特性

- **多 Provider 支持** - OpenAI 兼容（MiniMax/DeepSeek/硅基流动等）、Anthropic Claude、Google Gemini、LMStudio/Ollama 本地模型、Azure OpenAI
- **多指标测试**:
  - TTFT (Time To First Token) - 首Token响应时间
  - TPFT (Time Per First Token) - 排除首Token后的生成时间
  - Total Time - 总响应时间
  - Tokens/sec - 吞吐量
  - Think/Answer 拆分 - 思考过程与回答的耗时、Token 独立统计
- **多模态** - 支持图片+文本混合输入（ContentPart 类型系统）
- **并发测试** - 多模型 × 多测试用例并发执行
- **Web 可视化** - Vue3 前端 + SSE 实时推送测试进度与流式输出
- **定时任务** - 支持 ONCE / DAILY / WEEKLY / MONTHLY / CRON 调度
- **报告导出** - PDF / Excel / Markdown 报告
- **AI 校对** - 配置标准答案后可自动校对模型输出正确性

## 项目结构

```
model_speed_test/
├── main.py                  # CLI 入口（测试逻辑）
├── start.sh                 # 启动后端+前端
├── src/
│   ├── client.py            # 统一客户端（Provider 分发）
│   ├── client_adapter.py    # Provider 系统 ↔ ModelClient 适配器
│   ├── tester.py            # 核心测试引擎（流式/并发）
│   ├── metrics.py           # 指标计算（TTFT/TPFT/think-answer）
│   ├── recorder.py          # 输入输出记录器（按轮次归档）
│   ├── scheduler.py         # 定时任务调度器（含 cron 解析）
│   ├── database.py          # SQLite 持久化（测试结果）
│   ├── providers/           # LLM Provider 层（openai/anthropic/gemini/azure/local）
│   ├── evaluator.py         # AI 校对评估
│   └── rate_limiter.py      # 令牌桶限流
├── web/
│   ├── app.py               # FastAPI Web 服务（REST + SSE）
│   ├── emitter.py           # SSE 事件发射器
│   └── report_generator.py  # 报告生成
├── frontend/                # Vue3 前端
├── results/                 # 测试结果目录（含 config.db 配置库）
├── tests/                   # pytest 测试
└── requirements.txt
```

## 安装

```bash
pip install -r requirements.txt

# 前端（可选，仅 Web 界面需要）
cd frontend && npm install
```

## 配置

> **注意**：模型与测试用例配置存储在 `results/config.db`（SQLite），通过 Web 界面管理。
> 环境变量见 `.env.example`（复制为 `.env` 并填入真实 API Key）。

### 环境变量

```bash
# MiniMax API Key
MINIMAX_API_KEY=your_api_key_here

# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Web API 认证密钥（本地使用可留空）
WEB_API_KEY=

# CORS 允许的来源
CORS_ALLOWED_ORIGINS=http://localhost:14001
```

### 添加模型

通过 Web 界面（模型管理）或 SDK 添加，支持字段：name / provider / endpoint / api_key / model / temperature / max_tokens / thinking_enabled 等。

### 添加测试用例

支持两种内容格式：
- `messages`：多轮对话消息数组（含多模态 ContentPart）
- `prompt`：简单提示词

可配置 `expected_output` + `eval_model` 启用 AI 校对。

## 使用方法

### Web 界面（推荐）

```bash
./start.sh
# 前端: http://localhost:14001  (vite dev)
# 后端: http://localhost:15010
```

### CLI 测试

```bash
python main.py                    # 运行测试套件中的所有用例
python main.py --models 模型A 模型B  # 指定模型
python main.py --test-case 用例名  # 指定测试用例
python main.py --list             # 列出测试用例
python main.py --no-concurrent    # 顺序执行
python main.py --web              # 启动 Web 界面并测试
```

### 运行测试

```bash
python3 -m pytest tests/ -q
```

## 输出结果

测试结果保存在 `results/` 目录：

- `results/{group_id}_{task_name}/` - 每次测试的归档（JSON + Markdown + manifest）
- `results/test_results.db` - 历史测试结果数据库
- `results/config.db` - 模型/用例/调度配置库
- 报告导出：Web 历史页可生成 PDF / Excel / Markdown

## 测试指标说明

| 指标 | 说明 |
|------|------|
| TTFT | Time To First Token，首Token响应时间 |
| TPFT | Time Per First Token，排除首Token后的生成时间 |
| Total Time | 完整响应时间 |
| Tokens/sec | 吞吐量（每秒输出token数） |
| Think/Answer 时间与Token | 思考过程与回答的独立统计 |
| 成功率/校对评分 | 结合 expected_output 的 AI 校对结果 |

## 已知说明

- 本地测评工具，未内置认证（WEB_API_KEY 可选配置）
- 测试结果 `test_results.db` 若损坏，可从 `results/*.backup_*` 恢复
