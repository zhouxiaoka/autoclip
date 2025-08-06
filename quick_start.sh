#!/bin/bash

# AutoClip 快速启动脚本 (适用于已完成初始化的环境)
# 快速启动所有服务，跳过依赖检查和安装

echo "🚀 快速启动 AutoClip..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 清理函数
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
    redis-server --daemonize yes --port 6379
    sleep 1
fi

# 激活虚拟环境
source venv/bin/activate

# 启动后端
echo -e "${BLUE}🔧 启动后端...${NC}"
cd backend
export PYTHONPATH=$PYTHONPATH:$(pwd)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 启动Celery
echo -e "${BLUE}⚙️  启动Celery...${NC}"
export PYTHONPATH=.:$PYTHONPATH
cd backend
celery -A core.celery_app worker --loglevel=info --concurrency=1 &
CELERY_PID=$!
cd ..

# 启动前端
echo -e "${BLUE}🎨 启动前端...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo -e "\n${GREEN}✅ 所有服务已启动！${NC}"
echo -e "${GREEN}📱 前端:${NC} http://localhost:3000"
echo -e "${GREEN}🔌 后端:${NC} http://localhost:8000"
echo -e "${RED}按 Ctrl+C 停止所有服务${NC}"

wait