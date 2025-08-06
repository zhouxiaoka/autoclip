#!/bin/bash

# AutoClip 停止脚本
# 停止所有相关服务进程

echo "🛑 正在停止 AutoClip 所有服务..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 停止FastAPI后端服务器
echo -e "${BLUE}🔧 停止后端API服务器...${NC}"
pkill -f "uvicorn.*main:app" && echo -e "${GREEN}✅ 后端服务器已停止${NC}" || echo -e "${YELLOW}⚠️  后端服务器未运行${NC}"

# 停止Celery工作进程
echo -e "${BLUE}⚙️  停止Celery工作进程...${NC}"
pkill -f "celery.*worker" && echo -e "${GREEN}✅ Celery工作进程已停止${NC}" || echo -e "${YELLOW}⚠️  Celery工作进程未运行${NC}"

# 停止前端开发服务器
echo -e "${BLUE}🎨 停止前端开发服务器...${NC}"
pkill -f "vite" && echo -e "${GREEN}✅ 前端开发服务器已停止${NC}" || echo -e "${YELLOW}⚠️  前端开发服务器未运行${NC}"

# 可选：停止Redis（通常不建议，因为可能被其他应用使用）
read -p "是否停止Redis服务器? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}📡 停止Redis服务器...${NC}"
    pkill -f "redis-server" && echo -e "${GREEN}✅ Redis服务器已停止${NC}" || echo -e "${YELLOW}⚠️  Redis服务器未运行${NC}"
fi

echo -e "\n${GREEN}🎉 AutoClip 所有服务已停止！${NC}"