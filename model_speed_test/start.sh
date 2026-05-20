#!/bin/bash

# AI Model Speed Test - Start Script
# 只启动 Web 服务器（不运行测试）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting AI Model Speed Test..."
echo "=========================================="

# 加载 .env 环境变量
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "📋 Loading environment variables from .env..."
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# 检查 Python
if ! command -v python &> /dev/null; then
    echo "❌ Python not found!"
    exit 1
fi

# 检查依赖
echo "📦 Checking dependencies..."
python -c "import fastapi, uvicorn, aiohttp, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Installing..."
    pip install -r requirements.txt
fi

# 停止旧进程
echo "🧹 Cleaning up old processes..."
# 杀掉占用 15010 端口的进程
lsof -ti:15010 2>/dev/null | xargs kill -9 2>/dev/null
pkill -f "uvicorn" 2>/dev/null
pkill -f "python.*main.py" 2>/dev/null
sleep 1

# 启动后端 Web 服务器
echo "🔧 Starting Backend server..."
python -c "from web.app import run_server; run_server()" &
WEB_PID=$!

# 等待后端启动
sleep 2

# 启动前端 Vue 开发服务器
echo "🔧 Starting Frontend server..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo "=========================================="
echo "✅ Started successfully!"
echo "   Backend PID: $WEB_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo "   Backend API: http://localhost:15010"
echo "   Frontend UI: http://localhost:14001"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop all processes"

# 等待
trap "echo ''; echo '🛑 Stopping...'; kill $WEB_PID 2>/dev/null; exit" INT TERM

wait