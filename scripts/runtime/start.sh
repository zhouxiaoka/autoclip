#!/bin/bash

# AutoClip 一键启动脚本
# 版本: 2.0
# 功能: 启动完整的AutoClip系统（后端API + Celery Worker + 前端界面）

set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
STARTED_ROLES=()
DETACH=false
STARTUP_COMPLETE=false
case "${1:-}" in
    --detach) DETACH=true ;;
    --help|-h) echo 'Usage: ./start_autoclip.sh [--detach]'; exit 0 ;;
    '') ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac
manage_service() { bash "$ROOT/scripts/runtime/local.sh" "$@"; }
# Parse .env as dotenv data (env.example contains an unquoted logging format).
# Re-exec once so all child services inherit the same configuration.
if [[ "${_AUTOCLIP_ENV_LOADED:-}" != 1 && -x venv/bin/python ]]; then
    export _AUTOCLIP_ENV_LOADED=1
    exec venv/bin/python -c 'import os, sys; from dotenv import load_dotenv; load_dotenv(".env", override=False); os.execvpe("bash", ["bash", sys.argv[1], *sys.argv[2:]], os.environ)' "${BASH_SOURCE[0]}" "$@"
fi


# =============================================================================
# 配置区域
# =============================================================================

# 服务端口配置
BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

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
    
    # 检查必要的命令（在Docker环境中跳过node检查）
    if [[ "${ENVIRONMENT:-}" != "production" ]] || [[ ! -f "/.dockerenv" ]]; then
        local required_commands=("python3" "node" "npm" "curl" "lsof")
        for cmd in "${required_commands[@]}"; do
            if command_exists "$cmd"; then
                log_success "$cmd 已安装"
            else
                log_error "$cmd 未安装，请先安装"
                exit 1
            fi
        done
    else
        log_info "Docker环境检测到，跳过node环境检查"
        local required_commands=("python3" "curl" "lsof")
        for cmd in "${required_commands[@]}"; do
            if command_exists "$cmd"; then
                log_success "$cmd 已安装"
            else
                log_error "$cmd 未安装，请先安装"
                exit 1
            fi
        done
    fi
    
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
    mkdir -p data
    local required_dirs=("backend" "frontend")
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
    
    if manage_service redis >/dev/null 2>&1; then
        log_success "Redis 服务已运行"
        return 0
    fi
    
    if [[ "${REDIS_URL:-redis://localhost:6379/0}" != 'redis://localhost:6379/0' ]]; then
        log_error "配置的 Redis 不可用，请检查 REDIS_URL；不会启动本机 Redis 替代它"
        exit 1
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
    
    if manage_service redis >/dev/null 2>&1; then
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
    
    if [[ ! -f .env ]]; then
        cp env.example .env
        log_info "已创建 .env；请按需要编辑模型配置"
    fi

    # 检查Python依赖
    log_info "检查 Python 依赖..."
    if ! python -c "import fastapi, celery, sqlalchemy, psutil, dotenv, redis" 2>/dev/null; then
        log_error "缺少依赖，请先执行: python -m pip install -r requirements.txt"
        exit 1
    fi
    log_success "Python 依赖检查完成"
}

init_database() {
    log_step "初始化数据库"
    
    # 确保数据目录存在
    mkdir -p data
    
    python init_database.py
    log_success "数据库初始化成功"
}

start_celery() {
    log_step "启动 Celery Worker"
    
    log_info "启动 Celery Worker..."
    nohup celery -A backend.core.celery_app worker \
        --loglevel=info \
        --concurrency=1 \
        --prefetch-multiplier=1 \
        -Q celery,processing,video,notification,upload \
        --hostname=worker@%h \
        > "$CELERY_LOG" 2>&1 &
    
    local celery_pid=$!
    STARTED_ROLES+=(celery)
    manage_service record celery "$celery_pid"
    
    # 等待Worker启动
    sleep 5
    
    if manage_service check celery >/dev/null; then
        log_success "Celery Worker 已启动 (PID: $celery_pid)"
    else
        log_error "Celery Worker 启动失败"
        log_info "查看日志: tail -f $CELERY_LOG"
        exit 1
    fi
}

start_backend() {
    log_step "启动后端 API 服务"
    
    if port_in_use "$BACKEND_PORT"; then
        log_error "端口 $BACKEND_PORT 已占用；请先确认所属服务，不会终止其他进程"
        exit 1
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
    STARTED_ROLES+=(backend)
    manage_service record backend "$backend_pid"
    
    # 等待后端启动
    if wait_for_service "http://localhost:$BACKEND_PORT/api/v1/health/" "$BACKEND_STARTUP_TIMEOUT" "后端服务" && manage_service check backend; then
        log_success "后端服务已启动 (PID: $backend_pid)"
    else
        log_error "后端服务启动失败"
        log_info "查看日志: tail -f $BACKEND_LOG"
        exit 1
    fi
}

start_frontend() {
    log_step "启动前端服务"
    
    if port_in_use "$FRONTEND_PORT"; then
        log_error "端口 $FRONTEND_PORT 已占用；请先确认所属服务，不会终止其他进程"
        exit 1
    fi

    # 进入前端目录
    cd frontend || {
        log_error "无法进入前端目录"
        exit 1
    }
    
    # 检查前端依赖
    if [[ ! -d "node_modules" ]]; then
        log_info "安装前端依赖..."
        npm ci
    fi
    
    log_info "启动前端服务 (端口: $FRONTEND_PORT)..."
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort \
        > "../$FRONTEND_LOG" 2>&1 &
    
    local frontend_pid=$!
    STARTED_ROLES+=(frontend)
    cd "$ROOT"
    manage_service record frontend "$frontend_pid"
    
    # 已返回项目根目录用于记录进程归属。
    
    # 等待前端启动
    if wait_for_service "http://localhost:$FRONTEND_PORT/" "$FRONTEND_STARTUP_TIMEOUT" "前端服务" && manage_service check frontend; then
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
    if manage_service redis >/dev/null 2>&1; then
        log_success "Redis 服务健康"
    else
        log_error "Redis 服务不健康"
        all_healthy=false
    fi
    
    # 检查Celery Worker
    log_info "检查 Celery Worker..."
    if manage_service check celery >/dev/null; then
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
    if [[ "$DETACH" == true && "$STARTUP_COMPLETE" == true ]]; then return; fi
    cd "$ROOT"
    if [[ ${#STARTED_ROLES[@]} -gt 0 ]]; then
        for role in "${STARTED_ROLES[@]}"; do manage_service stop "$role" || true; done
    fi
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

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# =============================================================================
# 主函数
# =============================================================================

main() {
    log_header "AutoClip 系统启动器 v2.0"
    
    # 环境检查
    check_environment
    
    # 启动服务
    setup_environment
    # Refuse duplicate starts instead of overwriting PID records or killing other apps.
    for role in backend frontend celery; do
        if [[ -f "$role.pid" ]]; then
            if manage_service check "$role"; then
                log_error "$role 已运行，请先执行 ./stop_autoclip.sh"
                exit 1
            fi
            # A stale record is harmless; a live foreign PID is refused by stop.
            manage_service stop "$role"
        fi
    done
    start_redis
    init_database
    start_celery
    start_backend
    start_frontend
    
    # 健康检查
    if health_check; then
        STARTUP_COMPLETE=true
        show_system_info
        if [[ "$DETACH" == true ]]; then return; fi
        
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
