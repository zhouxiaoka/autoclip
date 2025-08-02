#!/bin/bash

# 自动切片工具开发环境启动脚本

echo "🚀 启动自动切片工具开发环境"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装，请先安装Node.js"
    exit 1
fi

# 安装后端依赖
echo "📦 检查后端依赖..."
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 检查是否需要安装依赖
# 如果requirements.txt比.venv_deps_installed新，或者.venv_deps_installed不存在，则重新安装
if [ ! -f ".venv_deps_installed" ] || [ "requirements.txt" -nt ".venv_deps_installed" ]; then
    echo "安装后端依赖..."
    pip install -r requirements.txt
    # 创建标记文件
    touch .venv_deps_installed
else
    echo "后端依赖已是最新，跳过安装"
fi

# 检查前端依赖
echo "📦 检查前端依赖..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi
cd ..

# 启动后端服务器
echo "🔧 启动后端API服务器..."
source venv/bin/activate
python backend_server.py &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端开发服务器
echo "🎨 启动前端开发服务器..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "✅ 开发环境启动完成！"
echo "📱 前端地址: http://localhost:3000"
echo "🔌 后端API: http://localhost:8000"
echo "📚 API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap 'echo "\n🛑 正在停止服务..."; kill $BACKEND_PID $FRONTEND_PID; exit' INT
wait