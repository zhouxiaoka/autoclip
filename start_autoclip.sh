#!/bin/bash

# AutoClip 统一启动脚本
# 启动所有必要的服务：前端、后端、Celery、数据库等

echo "🚀 正在启动 AutoClip 自动切片工具..."
echo "======================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 错误处理函数
handle_error() {
    echo -e "${RED}❌ 错误: $1${NC}"
    cleanup
    exit 1
}

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}🛑 正在停止所有服务...${NC}"
    
    # 停止所有后台进程
    if [[ -n "$BACKEND_PID" ]]; then
        echo "停止后端服务器 (PID: $BACKEND_PID)"
        kill $BACKEND_PID 2>/dev/null
    fi
    
    if [[ -n "$FRONTEND_PID" ]]; then
        echo "停止前端开发服务器 (PID: $FRONTEND_PID)"
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    if [[ -n "$CELERY_PID" ]]; then
        echo "停止Celery工作进程 (PID: $CELERY_PID)"
        kill $CELERY_PID 2>/dev/null
    fi
    
    if [[ -n "$REDIS_PID" ]]; then
        echo "停止Redis服务器 (PID: $REDIS_PID)"
        kill $REDIS_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 检查必要命令
check_command() {
    if ! command -v $1 &> /dev/null; then
        handle_error "$1 未安装，请先安装 $1"
    fi
}

echo -e "${BLUE}🔍 检查系统环境...${NC}"

# 检查必要的命令
check_command "python3"
check_command "node"
check_command "npm"

# 检查Redis（尝试启动如果未运行）
if ! command -v redis-server &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis未安装，尝试使用Homebrew安装...${NC}"
    if command -v brew &> /dev/null; then
        brew install redis || handle_error "无法安装Redis"
    else
        handle_error "请先安装Redis: brew install redis"
    fi
fi

# 检查Redis是否运行
if ! redis-cli ping &> /dev/null; then
    echo -e "${YELLOW}📡 启动Redis服务器...${NC}"
    redis-server --daemonize yes --port 6379 &
    REDIS_PID=$!
    sleep 2
    
    # 验证Redis启动
    if ! redis-cli ping &> /dev/null; then
        handle_error "Redis启动失败"
    fi
    echo -e "${GREEN}✅ Redis服务器已启动${NC}"
else
    echo -e "${GREEN}✅ Redis服务器已运行${NC}"
fi

# 创建Python虚拟环境
echo -e "${BLUE}🐍 设置Python环境...${NC}"
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv || handle_error "创建虚拟环境失败"
fi

# 激活虚拟环境
source venv/bin/activate || handle_error "激活虚拟环境失败"

# 创建requirements.txt（如果不存在）
if [ ! -f "requirements.txt" ]; then
    echo -e "${YELLOW}📝 创建requirements.txt文件...${NC}"
    cat > requirements.txt << 'EOF'
fastapi
uvicorn[standard]
sqlalchemy
alembic
celery[redis]
redis
pydantic
pydantic-settings
python-multipart
websockets
requests
aiofiles
python-jose[cryptography]
passlib[bcrypt]
pytest
pytest-cov
pytest-mock
cryptography
EOF
fi

# 安装Python依赖
if [ ! -f ".venv_deps_installed" ] || [ "requirements.txt" -nt ".venv_deps_installed" ]; then
    echo -e "${BLUE}📦 安装后端依赖...${NC}"
    pip install --upgrade pip || handle_error "升级pip失败"
    
    # 首先尝试安装requirements.txt
    if pip install -r requirements.txt; then
        echo -e "${GREEN}✅ 所有依赖安装成功${NC}"
    else
        echo -e "${YELLOW}⚠️  部分依赖安装失败，尝试安装核心依赖...${NC}"
        # 如果失败，逐个安装核心依赖
        pip install fastapi uvicorn[standard] sqlalchemy celery[redis] redis pydantic websockets requests || handle_error "安装核心依赖失败"
        echo -e "${GREEN}✅ 核心依赖安装成功${NC}"
    fi
    
    touch .venv_deps_installed
else
    echo -e "${GREEN}✅ 后端依赖已是最新${NC}"
fi

# 检查前端依赖
echo -e "${BLUE}📦 检查前端依赖...${NC}"
cd frontend || handle_error "进入frontend目录失败"

if [ ! -d "node_modules" ] || [ "package.json" -nt "node_modules/.package-lock.json" ]; then
    echo "安装前端依赖..."
    npm install || handle_error "安装前端依赖失败"
fi

cd .. || handle_error "返回根目录失败"
echo -e "${GREEN}✅ 前端依赖检查完成${NC}"

# 初始化数据库
echo -e "${BLUE}🗄️  初始化数据库...${NC}"

# 检查并创建.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}📝 创建.env配置文件...${NC}"
    cp env.example .env
    echo -e "${YELLOW}⚠️  请编辑.env文件设置API密钥等配置${NC}"
fi

# 设置环境变量 - 从项目根目录设置
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 初始化数据库表
python -c "
import sys
import os
# 添加项目根目录到Python路径
project_root = os.path.abspath('.')
sys.path.insert(0, project_root)
# 切换到backend目录进行导入
os.chdir('backend')
from core.database import create_tables, init_database
create_tables()
init_database()
print('数据库初始化完成')
" || handle_error "数据库初始化失败"
echo -e "${GREEN}✅ 数据库初始化完成${NC}"

# 启动服务
echo -e "\n${BLUE}🚀 启动所有服务...${NC}"

# 1. 启动后端API服务器
echo -e "${BLUE}🔧 启动后端API服务器...${NC}"
source venv/bin/activate
export PYTHONPATH=.:$PYTHONPATH

# 尝试启动完整版后端（从项目根目录启动）
echo "尝试启动完整版后端..."
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 等待后端启动
echo "等待后端服务启动..."
sleep 5

# 验证后端启动
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo -e "${GREEN}✅ 完整版后端API服务器已启动 (PID: $BACKEND_PID)${NC}"
elif curl -s http://localhost:8000/ > /dev/null; then
    echo -e "${YELLOW}⚠️  简化版后端API服务器已启动 (PID: $BACKEND_PID)${NC}"
    echo -e "${YELLOW}💡 完整版API可能因导入问题使用了简化版${NC}"
else
    handle_error "后端服务启动失败"
fi

# 2. 启动Celery工作进程
echo -e "${BLUE}⚙️  启动Celery工作进程...${NC}"
source venv/bin/activate
export PYTHONPATH=.:$PYTHONPATH
celery -A backend.core.celery_simple worker --loglevel=info --concurrency=1 &
CELERY_PID=$!
echo -e "${GREEN}✅ Celery工作进程已启动 (PID: $CELERY_PID)${NC}"

# 3. 启动前端开发服务器
echo -e "${BLUE}🎨 启动前端开发服务器...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✅ 前端开发服务器已启动 (PID: $FRONTEND_PID)${NC}"

# 等待所有服务完全启动
echo "等待所有服务完全启动..."
sleep 3

echo -e "\n${GREEN}🎉 AutoClip 自动切片工具启动完成！${NC}"
echo "======================================"
echo -e "${GREEN}📱 前端地址:${NC} http://localhost:3000"
echo -e "${GREEN}🔌 后端API:${NC} http://localhost:8000"
echo -e "${GREEN}📚 API文档:${NC} http://localhost:8000/docs"
echo -e "${GREEN}📊 Redis监控:${NC} redis-cli monitor"
echo ""
echo -e "${BLUE}📋 运行的服务:${NC}"
echo "  • Redis服务器 (端口: 6379)"
echo "  • 后端API服务器 (端口: 8000, PID: $BACKEND_PID)"
echo "  • Celery工作进程 (PID: $CELERY_PID)"
echo "  • 前端开发服务器 (端口: 3000, PID: $FRONTEND_PID)"
echo ""
echo -e "${YELLOW}💡 使用说明:${NC}"
echo "  • 前端包含了Zustand状态管理和WebSocket实时通信"
echo "  • WebSocket连接会自动建立用于任务进度推送"
echo "  • 所有模块已启动，可以开始使用完整功能"
echo ""
echo -e "${RED}按 Ctrl+C 停止所有服务${NC}"

# 等待用户中断
wait