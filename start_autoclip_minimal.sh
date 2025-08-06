#!/bin/bash

# AutoClip 最小启动脚本
# 仅安装必要依赖，快速启动开发环境

echo "🚀 启动 AutoClip (最小模式)..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 错误处理
handle_error() {
    echo -e "${RED}❌ 错误: $1${NC}"
    cleanup
    exit 1
}

cleanup() {
    echo -e "\n${YELLOW}🛑 正在停止所有服务...${NC}"
    
    if [[ -n "$BACKEND_PID" ]]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    
    if [[ -n "$FRONTEND_PID" ]]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    if [[ -n "$CELERY_PID" ]]; then
        kill $CELERY_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

trap cleanup SIGINT SIGTERM

# 检查Redis
if ! redis-cli ping &> /dev/null; then
    echo -e "${YELLOW}📡 启动Redis...${NC}"
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes --port 6379
        sleep 2
    else
        handle_error "Redis未安装，请运行: brew install redis"
    fi
fi

# 创建虚拟环境
echo -e "${BLUE}🐍 设置Python环境...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv || handle_error "创建虚拟环境失败"
fi

source venv/bin/activate || handle_error "激活虚拟环境失败"

# 安装最小依赖
echo -e "${BLUE}📦 安装最小依赖...${NC}"
pip install --upgrade pip

# 逐个安装核心依赖，如果某个失败不影响其他
echo "安装核心依赖..."
pip install fastapi || echo "⚠️ fastapi安装失败"
pip install "uvicorn[standard]" || echo "⚠️ uvicorn安装失败"
pip install sqlalchemy || echo "⚠️ sqlalchemy安装失败"
pip install "celery[redis]" || echo "⚠️ celery安装失败"
pip install redis || echo "⚠️ redis安装失败"
pip install pydantic || echo "⚠️ pydantic安装失败"
pip install websockets || echo "⚠️ websockets安装失败"
pip install requests || echo "⚠️ requests安装失败"

echo -e "${GREEN}✅ 核心依赖安装完成${NC}"

# 检查前端依赖
echo -e "${BLUE}📦 检查前端依赖...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    npm install || handle_error "前端依赖安装失败"
fi
cd ..

# 创建.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 创建.env配置文件...${NC}"
    cp env.example .env
fi

# 启动服务
echo -e "\n${BLUE}🚀 启动服务...${NC}"

# 启动后端 (简化版)
echo -e "${BLUE}🔧 启动后端 (简化版)...${NC}"
source venv/bin/activate
cd backend
export PYTHONPATH=$PYTHONPATH:$(pwd)
python -c "
try:
    from core.database import create_tables
    create_tables()
    print('数据库表创建成功')
except Exception as e:
    print(f'数据库初始化警告: {e}')
"
python -m uvicorn main_simple:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 启动Celery (简化版)
echo -e "${BLUE}⚙️  启动Celery (简化版)...${NC}"
export PYTHONPATH=.:$PYTHONPATH
celery -A backend.core.celery_simple worker --loglevel=info --concurrency=1 &
CELERY_PID=$!

# 启动前端
echo -e "${BLUE}🎨 启动前端...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo -e "\n${GREEN}✅ AutoClip 启动完成！${NC}"
echo -e "${GREEN}📱 前端:${NC} http://localhost:3000"
echo -e "${GREEN}🔌 后端:${NC} http://localhost:8000"
echo -e "${RED}按 Ctrl+C 停止所有服务${NC}"

wait