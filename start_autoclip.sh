#!/bin/bash

# AutoClip 一键启动脚本
# 版本: 2.0
# 功能: 启动完整的AutoClip系统（后端API + Celery Worker + 前端界面）

set -euo pipefail

# =============================================================================
# 配置区域
# =============================================================================

# 服务端口配置
BACKEND_PORT=8000
FRONTEND_PORT=3000
REDIS_PORT=6379

# 服务超时配置
BACKEND_STARTUP_TIMEOUT=60
FRONTEND_STARTUP_TIMEOUT=90
HEALTH_CHECK_TIMEOUT=10

# 日志配置
LOG_DIR="logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
CELERY_LOG="$LOG_DIR/celery.log"

# PID文件
BACKEND_PID_FILE="backend.pid"
FRONTEND_PID_FILE="frontend.pid"
CELERY_PID_FILE="celery.pid"

# =============================================================================
# 颜色和样式定义
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 图标定义
ICON_SUCCESS="✅"
ICON_ERROR="❌"
ICON_WARNING="⚠️"
ICON_INFO="ℹ️"
ICON_ROCKET="🚀"
ICON_GEAR="⚙️"
ICON_DATABASE="🗄️"
ICON_WORKER="👷"
ICON_WEB="🌐"
ICON_HEALTH="💚"

# =============================================================================
# 工具函数
# =============================================================================

log_info() {
    echo -e "${BLUE}${ICON_INFO} $1${NC}"
}

log_success() {
    echo -e "${GREEN}${ICON_SUCCESS} $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}${ICON_WARNING} $1${NC}"
}

log_error() {
    echo -e "${RED}${ICON_ERROR} $1${NC}"
}

log_header() {
    echo -e "\n${PURPLE}${ICON_ROCKET} $1${NC}"
    echo -e "${PURPLE}$(printf '=%.0s' {1..50})${NC}"
}

log_step() {
    echo -e "\n${CYAN}${ICON_GEAR} $1${NC}"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查端口是否被占用
port_in_use() {
    lsof -i ":$1" >/dev/null 2>&1
}

# 等待服务启动
wait_for_service() {
    local url="$1"
    local timeout="$2"
    local service_name="$3"
    
    log_info "等待 $service_name 启动..."
    
    for i in $(seq 1 "$timeout"); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            log_success "$service_name 已启动"
            return 0
        fi
        sleep 1
    done
    
    log_error "$service_name 启动超时"
    return 1
}

# 检查进程是否运行
process_running() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# 停止进程
stop_process() {
    local pid_file="$1"
    local service_name="$2"
    
    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止 $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                log_warning "强制停止 $service_name..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

# =============================================================================
# 环境检查函数
# =============================================================================

check_environment() {
    log_header "环境检查"
    
    # 检查操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_success "检测到 macOS 系统"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "检测到 Linux 系统"
    else
        log_warning "未识别的操作系统: $OSTYPE"
    fi
    
    # 检查必要的命令
    local required_commands=("python3" "node" "npm" "redis-cli")
    for cmd in "${required_commands[@]}"; do
        if command_exists "$cmd"; then
            log_success "$cmd 已安装"
        else
            log_error "$cmd 未安装，请先安装"
            exit 1
        fi
    done
    
    # 检查Python版本
    local python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    log_info "Python 版本: $python_version"
    
    # 检查Node.js版本
    local node_version=$(node --version)
    log_info "Node.js 版本: $node_version"
    
    # 检查虚拟环境
    if [[ ! -d "venv" ]]; then
        log_error "虚拟环境不存在，请先创建: python3 -m venv venv"
        exit 1
    fi
    log_success "虚拟环境存在"
    
    # 检查项目结构
    local required_dirs=("backend" "frontend" "data")
    for dir in "${required_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            log_success "目录 $dir 存在"
        else
            log_error "目录 $dir 不存在"
            exit 1
        fi
    done
}

# =============================================================================
# 服务启动函数
# =============================================================================

start_redis() {
    log_step "启动 Redis 服务"
    
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis 服务已运行"
        return 0
    fi
    
    log_info "启动 Redis 服务..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command_exists brew; then
            brew services start redis
            sleep 3
        else
            log_error "请手动启动 Redis 服务"
            exit 1
        fi
    else
        systemctl start redis-server 2>/dev/null || service redis-server start 2>/dev/null || {
            log_error "无法启动 Redis 服务，请手动启动"
            exit 1
        }
    fi
    
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis 服务启动成功"
    else
        log_error "Redis 服务启动失败"
        exit 1
    fi
}

setup_environment() {
    log_step "设置环境"
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 激活虚拟环境
    log_info "激活虚拟环境..."
    source venv/bin/activate
    
    # 设置Python路径
    : "${PYTHONPATH:=}"
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    log_info "设置 Python 路径: $PYTHONPATH"
    
    # 加载环境变量
    if [[ -f ".env" ]]; then
        log_info "加载环境变量..."
        set -a
        source .env
        set +a
        log_success "环境变量加载成功"
    else
        log_warning ".env 文件不存在，使用默认配置"
        # 创建默认环境变量文件
        if [[ ! -f ".env" ]]; then
            log_info "创建默认 .env 文件..."
            cp env.example .env 2>/dev/null || {
                cat > .env << EOF
# AutoClip 环境配置
DATABASE_URL=sqlite:///./data/autoclip.db
REDIS_URL=redis://localhost:6379/0
API_DASHSCOPE_API_KEY=
API_MODEL_NAME=qwen-plus
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=true
EOF
                log_success "已创建默认 .env 文件"
            }
        fi
    fi
    
    # 检查Python依赖
    log_info "检查 Python 依赖..."
    if ! python -c "import fastapi, celery, sqlalchemy" 2>/dev/null; then
        log_warning "缺少依赖，正在安装..."
        pip install -r requirements.txt
    fi
    log_success "Python 依赖检查完成"
}

init_database() {
    log_step "初始化数据库"
    
    # 确保数据目录存在
    mkdir -p data
    
    # 初始化数据库
    log_info "创建数据库表..."
    if python -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import engine, Base
from backend.models import project, task, clip, collection, bilibili
try:
    Base.metadata.create_all(bind=engine)
    print('数据库表创建成功')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_success "数据库初始化成功"
    else
        log_error "数据库初始化失败"
        exit 1
    fi
}

start_celery() {
    log_step "启动 Celery Worker"
    
    # 停止现有的Celery进程
    pkill -f "celery.*worker" 2>/dev/null || true
    sleep 2
    
    log_info "启动 Celery Worker..."
    nohup celery -A backend.core.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        -Q processing,upload,notification,maintenance \
        --hostname=worker@%h \
        > "$CELERY_LOG" 2>&1 &
    
    local celery_pid=$!
    echo "$celery_pid" > "$CELERY_PID_FILE"
    
    # 等待Worker启动
    sleep 5
    
    if pgrep -f "celery.*worker" >/dev/null; then
        log_success "Celery Worker 已启动 (PID: $celery_pid)"
    else
        log_error "Celery Worker 启动失败"
        log_info "查看日志: tail -f $CELERY_LOG"
        exit 1
    fi
}

start_backend() {
    log_step "启动后端 API 服务"
    
    # 检查端口是否被占用
    if port_in_use "$BACKEND_PORT"; then
        log_warning "端口 $BACKEND_PORT 已被占用，尝试停止现有服务..."
        stop_process "$BACKEND_PID_FILE" "后端服务"
    fi
    
    log_info "启动后端服务 (端口: $BACKEND_PORT)..."
    nohup python -m uvicorn backend.main:app \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        --reload \
        --reload-dir backend \
        --reload-include '*.py' \
        --reload-exclude 'data/*' \
        --reload-exclude 'logs/*' \
        --reload-exclude 'uploads/*' \
        --reload-exclude '*.log' \
        > "$BACKEND_LOG" 2>&1 &
    
    local backend_pid=$!
    echo "$backend_pid" > "$BACKEND_PID_FILE"
    
    # 等待后端启动
    if wait_for_service "http://localhost:$BACKEND_PORT/api/v1/health/" "$BACKEND_STARTUP_TIMEOUT" "后端服务"; then
        log_success "后端服务已启动 (PID: $backend_pid)"
    else
        log_error "后端服务启动失败"
        log_info "查看日志: tail -f $BACKEND_LOG"
        exit 1
    fi
}

start_frontend() {
    log_step "启动前端服务"
    
    # 检查端口是否被占用
    if port_in_use "$FRONTEND_PORT"; then
        log_warning "端口 $FRONTEND_PORT 已被占用，尝试停止现有服务..."
        stop_process "$FRONTEND_PID_FILE" "前端服务"
    fi
    
    # 进入前端目录
    cd frontend || {
        log_error "无法进入前端目录"
        exit 1
    }
    
    # 检查前端依赖
    if [[ ! -d "node_modules" ]]; then
        log_info "安装前端依赖..."
        npm install
    fi
    
    log_info "启动前端服务 (端口: $FRONTEND_PORT)..."
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
        > "../$FRONTEND_LOG" 2>&1 &
    
    local frontend_pid=$!
    echo "$frontend_pid" > "../$FRONTEND_PID_FILE"
    
    # 返回项目根目录
    cd ..
    
    # 等待前端启动
    if wait_for_service "http://localhost:$FRONTEND_PORT/" "$FRONTEND_STARTUP_TIMEOUT" "前端服务"; then
        log_success "前端服务已启动 (PID: $frontend_pid)"
    else
        log_error "前端服务启动失败"
        log_info "查看日志: tail -f $FRONTEND_LOG"
        exit 1
    fi
}

# =============================================================================
# 健康检查函数
# =============================================================================

health_check() {
    log_header "系统健康检查"
    
    local all_healthy=true
    
    # 检查后端
    log_info "检查后端服务..."
    if curl -fsS "http://localhost:$BACKEND_PORT/api/v1/health/" >/dev/null 2>&1; then
        log_success "后端服务健康"
    else
        log_error "后端服务不健康"
        all_healthy=false
    fi
    
    # 检查前端
    log_info "检查前端服务..."
    if curl -fsS "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then
        log_success "前端服务健康"
    else
        log_error "前端服务不健康"
        all_healthy=false
    fi
    
    # 检查Redis
    log_info "检查 Redis 服务..."
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis 服务健康"
    else
        log_error "Redis 服务不健康"
        all_healthy=false
    fi
    
    # 检查Celery Worker
    log_info "检查 Celery Worker..."
    if pgrep -f "celery.*worker" >/dev/null; then
        log_success "Celery Worker 健康"
    else
        log_error "Celery Worker 不健康"
        all_healthy=false
    fi
    
    if [[ "$all_healthy" == true ]]; then
        log_success "所有服务健康检查通过"
        return 0
    else
        log_error "部分服务健康检查失败"
        return 1
    fi
}

# =============================================================================
# 清理函数
# =============================================================================

cleanup() {
    log_header "清理服务"
    
    stop_process "$BACKEND_PID_FILE" "后端服务"
    stop_process "$FRONTEND_PID_FILE" "前端服务"
    stop_process "$CELERY_PID_FILE" "Celery Worker"
    
    # 停止所有相关进程
    pkill -f "celery.*worker" 2>/dev/null || true
    pkill -f "uvicorn.*backend.main:app" 2>/dev/null || true
    pkill -f "npm.*dev" 2>/dev/null || true
    
    log_success "清理完成"
}

# =============================================================================
# 显示系统信息
# =============================================================================

show_system_info() {
    log_header "系统启动完成"
    
    echo -e "${WHITE}🎉 AutoClip 系统已成功启动！${NC}"
    echo ""
    echo -e "${CYAN}📊 服务状态:${NC}"
    echo -e "  ${ICON_WEB} 后端 API:     http://localhost:$BACKEND_PORT"
    echo -e "  ${ICON_WEB} 前端界面:     http://localhost:$FRONTEND_PORT"
    echo -e "  ${ICON_WEB} API 文档:     http://localhost:$BACKEND_PORT/docs"
    echo -e "  ${ICON_HEALTH} 健康检查:   http://localhost:$BACKEND_PORT/api/v1/health/"
    echo ""
    echo -e "${CYAN}📝 日志文件:${NC}"
    echo -e "  后端日志: tail -f $BACKEND_LOG"
    echo -e "  前端日志: tail -f $FRONTEND_LOG"
    echo -e "  Celery日志: tail -f $CELERY_LOG"
    echo ""
    echo -e "${CYAN}🛑 停止系统:${NC}"
    echo -e "  ./stop_autoclip.sh 或按 Ctrl+C"
    echo ""
    echo -e "${YELLOW}💡 使用说明:${NC}"
    echo -e "  1. 访问 http://localhost:$FRONTEND_PORT 使用前端界面"
    echo -e "  2. 上传视频文件或输入B站链接"
    echo -e "  3. 系统将自动启动AI处理流水线"
    echo -e "  4. 实时查看处理进度和结果"
    echo ""
}

# =============================================================================
# 信号处理
# =============================================================================

trap cleanup EXIT INT TERM

# =============================================================================
# 主函数
# =============================================================================

main() {
    log_header "AutoClip 系统启动器 v2.0"
    
    # 环境检查
    check_environment
    
    # 启动服务
    start_redis
    setup_environment
    init_database
    start_celery
    start_backend
    start_frontend
    
    # 健康检查
    if health_check; then
        show_system_info
        
        # 保持脚本运行（不进行循环检查）
        log_info "系统运行中... 按 Ctrl+C 停止"
        log_info "如需检查系统状态，请运行: ./status_autoclip.sh"
        while true; do
            sleep 3600  # 每小时检查一次，减少频率
        done
    else
        log_error "系统启动失败，请检查日志"
        exit 1
    fi
}

# 运行主函数
main "$@"
