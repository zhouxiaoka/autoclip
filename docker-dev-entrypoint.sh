#!/bin/bash

# Docker开发环境启动脚本
# 专门为开发环境设计，解决前端vite问题

set -euo pipefail

echo "🚀 启动AutoClip开发环境..."

# 设置环境变量
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# 确保数据目录存在
mkdir -p /app/data/projects /app/data/uploads /app/data/temp /app/data/output /app/logs

# 激活虚拟环境
source /app/venv/bin/activate

# 检查并安装前端依赖
echo "📦 检查前端依赖..."
cd /app/frontend
if [ ! -d node_modules ] || [ ! -f node_modules/.bin/vite ]; then
    echo "安装前端依赖..."
    npm install
fi

# 检查vite是否正确安装
if [ ! -f node_modules/.bin/vite ]; then
    echo "❌ vite未正确安装，重新安装..."
    npm install vite
fi

# 返回根目录
cd /app

# 启动后端服务
echo "🔧 启动后端服务..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端服务
echo "🌐 启动前端服务..."
cd /app/frontend
npx vite --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!

# 返回根目录
cd /app

echo "✅ 服务启动完成"
echo "  后端API: http://localhost:8000"
echo "  前端界面: http://localhost:3000"

# 等待所有进程
wait