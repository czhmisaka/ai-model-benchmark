#!/bin/bash

# AI模型速度测试框架 - 停止脚本（增强版）

echo "🛑 正在停止所有服务..."
echo "=========================================="

# 1. 按端口杀死进程 (15010 是 Web 服务端口, 14001 是前端端口)
echo "📍 检查端口 15010..."
if lsof -ti:15010 2>/dev/null; then
    echo "   杀死占用 15010 端口的进程..."
    lsof -ti:15010 | xargs kill -9 2>/dev/null
    echo "   ✅ 端口 15010 已释放"
else
    echo "   ✅ 端口 15010 无进程"
fi

echo "📍 检查端口 14001..."
if lsof -ti:14001 2>/dev/null; then
    echo "   杀死占用 14001 端口的进程..."
    lsof -ti:14001 | xargs kill -9 2>/dev/null
    echo "   ✅ 端口 14001 已释放"
else
    echo "   ✅ 端口 14001 无进程"
fi

# 2. 终止 uvicorn 进程
echo "🔧 检查 uvicorn..."
pkill -9 -f "uvicorn" 2>/dev/null && echo "   ✅ uvicorn 进程已终止" || echo "   ✅ 无 uvicorn 进程"

# 3. 终止前端 vite 进程
echo "📄 检查 Vite 前端..."
pkill -9 -f "node.*vite" 2>/dev/null && echo "   ✅ Vite 进程已终止" || echo "   ✅ 无 Vite 进程"

# 5. 终止 main.py 进程  
echo "📄 检查 main.py..."
pkill -9 -f "python.*main.py" 2>/dev/null && echo "   ✅ main.py 进程已终止" || echo "   ✅ 无 main.py 进程"

# 6. 终止 web/app.py 进程
echo "🌐 检查 web/app.py..."
pkill -9 -f "python.*web.app" 2>/dev/null && echo "   ✅ web/app.py 进程已终止" || echo "   ✅ 无 web/app.py 进程"

# 7. 终止所有 python 相关进程（如果上面都没杀掉）
echo "🐍 检查所有 Python 进程..."
pkill -9 -f "model_speed_test" 2>/dev/null && echo "   ✅ 相关 Python 进程已终止" || echo "   ✅ 无残留 Python 进程"

# 等待一下
sleep 1

# 8. 最终检查
echo ""
echo "📊 最终检查..."
sleep 0.5

echo ""
echo "检查端口占用:"
lsof -i:15010 2>/dev/null && echo "   ❌ 端口15010仍被占用!" || echo "   ✅ 端口15010已空闲"
lsof -i:14001 2>/dev/null && echo "   ❌ 端口14001仍被占用!" || echo "   ✅ 端口14001已空闲"

echo ""
echo "检查进程:"
ps aux | grep -E "(main.py|uvicorn|web.app)" | grep -v grep && echo "   ❌ 有残留进程!" || echo "   ✅ 无残留进程"

echo ""
echo "=========================================="
echo "✅ 清理完成!"
echo "=========================================="