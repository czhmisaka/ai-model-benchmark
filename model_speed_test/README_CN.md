# AI模型速度测试 - 使用手册

## 快速启动

### 方式一：使用原有 Web 界面（推荐）
```bash
cd /Volumes/mobileDisk/test/模型速度测试/model_speed_test

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
./start.sh
```

访问: http://localhost:15010

### 方式二：使用新版 Vue3 前端（开发中）
```bash
cd /Volumes/mobileDisk/test/模型速度测试/model_speed_test/frontend

# 安装前端依赖
npm install

# 启动开发服务器（同时需要启动后端）
npm run dev
```

访问: http://localhost:3000

> ⚠️ Vue3 前端需要同时运行后端服务（端口 15010）

### 2. 配置 API Key
编辑 `config/config.json`，将 `YOUR_API_KEY_HERE` 替换为真实的 MiniMax API Key。

## 界面说明

### 布局
- **左侧**: 模型和测试用例选择
- **中间**: 输入/输出内容 + 进度条
- **右侧**: 性能指标 (TTFT, TPFT, TOKENS, SPEED)
- **底部**: 实时日志

### 操作流程
1. 勾选要测试的模型
2. 勾选要测试的用例
3. 点击 **START** 开始测试
4. 实时查看进度和指标

### 状态指示
- **SSE**: 连接状态 (OK = 已连接)
- **TEST**: 测试状态 (IDLE/RUNNING/DONE)

## 技术架构

### 启动流程
```
./start.sh 
  → 启动 FastAPI Web 服务器 (端口15010)
  → 打开浏览器访问 http://localhost:15010
```

### 点击开始流程
```
前端 POST /test/start
  → 后端创建测试线程
  → 调用 main.py 的 run_tests_with_web()
  → 使用 test_emitter 推送 SSE 事件
  → 前端 /events 接收并显示
```

### API 端点
| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/config` | GET | 获取配置 |
| `/test/start` | POST | 开始测试 |
| `/test/stop` | POST | 停止测试 |
| `/test/status` | GET | 测试状态 |
| `/events` | GET | SSE 事件流 |

## 常见问题

### 1. 401 错误
- 检查 `config/config.json` 中的 API Key 是否正确

### 2. 端口占用
```bash
# 停止旧进程
pkill -f uvicorn
pkill -f python.*main.py
```

### 3. 测试不运行
- 确保已选择至少一个模型和测试用例
- 检查 API Key 配置正确

## 文件结构
```
model_speed_test/
├── main.py              # 主入口 + 测试逻辑
├── start.sh             # 启动脚本
├── config/
│   └── config.json      # 配置文件
├── web/
│   ├── app.py          # FastAPI 应用
│   ├── emitter.py      # SSE 事件发射器
│   └── templates/
│       └── index.html   # Web 界面
├── src/
│   ├── client.py       # API 客户端
│   ├── tester.py       # 测试运行器
│   └── metrics.py      # 指标计算
└── results/            # 测试结果