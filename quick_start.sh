#!/bin/bash

# AutoClip 快速启动脚本
# 版本: 2.0
# 功能: 快速启动开发环境，跳过详细检查

set -euo pipefail

# =============================================================================
# 配置区域
# =============================================================================

BACKEND_PORT=8000
FRONTEND_PORT=3000

# =============================================================================
# 颜色定义
# =============================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# =============================================================================
# 工具函数
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    echo -e "${GREEN}🚀 AutoClip 快速启动${NC}"
    echo ""
    
    # 检查虚拟环境
    if [[ ! -d "venv" ]]; then
        log_warning "虚拟环境不存在，请先运行: python3 -m venv venv"
        exit 1
    fi
    
    # 激活虚拟环境
    log_info "激活虚拟环境..."
    source venv/bin/activate
    
    # 设置Python路径
    : "${PYTHONPATH:=}"
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    # 加载环境变量
    if [[ -f ".env" ]]; then
        set -a
        source .env
        set +a
    fi
    
    # 启动Redis（如果需要）
    if ! redis-cli ping >/dev/null 2>&1; then
        log_info "启动Redis..."
        if command -v brew >/dev/null; then
            brew services start redis
            sleep 2
        fi
    fi
    
    # 创建日志目录
    mkdir -p logs
    
    # 启动后端
    log_info "启动后端服务..."
    nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload > logs/backend.log 2>&1 &
    echo $! > backend.pid
    
    # 启动Celery Worker
    log_info "启动Celery Worker..."
    nohup celery -A backend.core.celery_app worker --loglevel=info --concurrency=2 -Q processing,upload,notification,maintenance > logs/celery.log 2>&1 &
    echo $! > celery.pid
    
    # 启动前端
    log_info "启动前端服务..."
    cd frontend
    nohup npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" > ../logs/frontend.log 2>&1 &
    echo $! > ../frontend.pid
    cd ..
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 检查服务状态
    if curl -fsS "http://localhost:$BACKEND_PORT/api/v1/health/" >/dev/null 2>&1; then
        log_success "后端服务已启动"
    else
        log_warning "后端服务启动可能有问题"
    fi
    
    if curl -fsS "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then
        log_success "前端服务已启动"
    else
        log_warning "前端服务启动可能有问题"
    fi
    
    echo ""
    log_success "快速启动完成！"
    echo ""
    echo "🌐 访问地址:"
    echo "  前端: http://localhost:$FRONTEND_PORT"
    echo "  后端: http://localhost:$BACKEND_PORT"
    echo "  API文档: http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo "📝 查看日志:"
    echo "  tail -f logs/backend.log"
    echo "  tail -f logs/frontend.log"
    echo "  tail -f logs/celery.log"
    echo ""
    echo "🛑 停止服务: ./stop_autoclip.sh"
}

# 运行主函数
main "$@"
