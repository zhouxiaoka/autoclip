#!/bin/bash

# AutoClip 桌面客户端环境配置脚本
# 一键设置开发环境和依赖

set -e  # 遇到错误立即退出

echo "🚀 AutoClip 桌面客户端环境配置开始..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装"
        return 1
    else
        print_success "$1 已安装"
        return 0
    fi
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

print_info "项目根目录: $PROJECT_ROOT"

# 1. 检查系统要求
print_info "检查系统要求..."

# 检查Python
if ! check_command python3; then
    print_error "请先安装 Python 3.11+"
    exit 1
fi

# 检查Python版本
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ $(echo "$PYTHON_VERSION < 3.11" | bc -l) -eq 1 ]]; then
    print_error "Python版本过低，需要 3.11+，当前版本: $PYTHON_VERSION"
    exit 1
fi
print_success "Python版本: $PYTHON_VERSION"

# 检查Node.js
if ! check_command node; then
    print_error "请先安装 Node.js 18+"
    exit 1
fi

# 检查Node.js版本
NODE_VERSION=$(node --version | sed 's/v//')
if [[ $(echo "$NODE_VERSION < 18.0" | bc -l) -eq 1 ]]; then
    print_error "Node.js版本过低，需要 18+，当前版本: $NODE_VERSION"
    exit 1
fi
print_success "Node.js版本: $NODE_VERSION"

# 检查npm
if ! check_command npm; then
    print_error "npm 未安装"
    exit 1
fi

# 检查Rust
if ! check_command rustc; then
    print_warning "Rust 未安装，正在安装..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
    print_success "Rust 安装完成"
fi

RUST_VERSION=$(rustc --version | cut -d' ' -f2)
print_success "Rust版本: $RUST_VERSION"

# 2. 创建Python虚拟环境
print_info "设置Python虚拟环境..."

VENV_DIR="$PROJECT_ROOT/venv"
if [ -d "$VENV_DIR" ]; then
    print_warning "虚拟环境已存在，跳过创建"
else
    print_info "创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    print_success "虚拟环境创建完成"
fi

# 激活虚拟环境
print_info "激活虚拟环境..."
source "$VENV_DIR/bin/activate"

# 升级pip
print_info "升级pip..."
pip install --upgrade pip

# 3. 安装Python依赖
print_info "安装Python依赖..."

# 安装基础依赖
pip install -r requirements.txt

# 安装开发依赖
pip install pyinstaller

# 确保Pydantic v2
pip install "pydantic>=2.0.0" pydantic-settings

print_success "Python依赖安装完成"

# 4. 安装前端依赖
print_info "安装前端依赖..."

cd frontend
npm install

# 安装Tauri CLI
if ! command -v tauri &> /dev/null; then
    print_info "安装Tauri CLI..."
    npm install -g @tauri-apps/cli
    print_success "Tauri CLI 安装完成"
else
    print_success "Tauri CLI 已安装"
fi

cd "$PROJECT_ROOT"

# 5. 设置环境变量
print_info "设置环境变量..."

# 创建环境变量文件
ENV_FILE="$PROJECT_ROOT/.env.desktop"
if [ ! -f "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EOF
# AutoClip Desktop 模式配置
AUTOCLIP_MODE=desktop
AUTOCLIP_DESKTOP_MODE=true

# 服务配置
HOST=127.0.0.1
PORT=8000
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///data/autoclip.db

# Celery配置 - 使用SQLite Transport
CELERY_BROKER_URL=db+sqlite:///data/celery_broker.db
CELERY_RESULT_BACKEND=db+sqlite:///data/celery_results.db
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json
CELERY_TIMEZONE=Asia/Shanghai
CELERY_ENABLE_UTC=true

# 并发配置 - 桌面模式限制并发
CELERY_WORKER_CONCURRENCY=1
CELERY_TASK_ALWAYS_EAGER=false

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=data/logs/autoclip.log

# 路径配置
DATA_DIR=data
PROJECTS_DIR=data/projects
TEMP_DIR=data/temp
UPLOADS_DIR=data/uploads
LOGS_DIR=data/logs

# API配置
DASHSCOPE_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
SILICONFLOW_API_KEY=

# 模型配置
DEFAULT_MODEL=qwen-plus
MAX_TOKENS=4000
TIMEOUT=30

# 处理配置
CHUNK_SIZE=5000
MIN_SCORE_THRESHOLD=0.7
MAX_CLIPS_PER_COLLECTION=5
MAX_RETRIES=3
EOF
    print_success "环境变量文件创建完成"
else
    print_warning "环境变量文件已存在，跳过创建"
fi

# 6. 创建数据目录
print_info "创建数据目录..."

DATA_DIRS=("data" "data/projects" "data/temp" "data/uploads" "data/logs")
for dir in "${DATA_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_success "创建目录: $dir"
    fi
done

# 7. 设置执行权限
print_info "设置脚本执行权限..."

chmod +x scripts/*.py
chmod +x scripts/*.sh

print_success "脚本权限设置完成"

# 8. 验证安装
print_info "验证安装..."

# 验证Python包
python3 -c "import fastapi, uvicorn, celery, sqlalchemy, pydantic; print('Python包验证成功')"

# 验证Node.js包
cd frontend
npm list --depth=0 > /dev/null
cd "$PROJECT_ROOT"

# 验证Rust
rustc --version > /dev/null

print_success "安装验证完成"

# 9. 显示使用说明
print_info "环境配置完成！"
echo ""
echo "📋 使用说明："
echo "1. 开发环境启动："
echo "   python scripts/dev_desktop.py start"
echo ""
echo "2. 构建桌面应用："
echo "   python scripts/build_desktop.py"
echo ""
echo "3. 运行测试："
echo "   python scripts/test_desktop.py"
echo ""
echo "4. 环境变量："
echo "   export AUTOCLIP_PYTHON=\"$VENV_DIR/bin/python\""
echo ""
echo "🎉 AutoClip 桌面客户端环境配置完成！"
