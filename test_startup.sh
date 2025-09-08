#!/bin/bash

# AutoClip 启动测试脚本
# 用于测试启动流程的各个组件

set -euo pipefail

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

main() {
    echo -e "${GREEN}🧪 AutoClip 启动测试${NC}"
    echo ""
    
    # 测试1: 环境检查
    log_info "测试1: 环境检查"
    
    if [[ -d "venv" ]]; then
        log_success "虚拟环境存在"
    else
        log_error "虚拟环境不存在"
        return 1
    fi
    
    if command -v python3 >/dev/null; then
        log_success "Python3 已安装"
    else
        log_error "Python3 未安装"
        return 1
    fi
    
    if command -v node >/dev/null; then
        log_success "Node.js 已安装"
    else
        log_error "Node.js 未安装"
        return 1
    fi
    
    if redis-cli ping >/dev/null 2>&1; then
        log_success "Redis 服务正常"
    else
        log_warning "Redis 服务未运行"
    fi
    
    # 测试2: 虚拟环境激活
    log_info "测试2: 虚拟环境激活"
    source venv/bin/activate
    export PYTHONPATH="${PWD}:${PYTHONPATH:-}"
    log_success "虚拟环境已激活"
    
    # 测试3: Python依赖检查
    log_info "测试3: Python依赖检查"
    if python -c "import fastapi, celery, sqlalchemy" 2>/dev/null; then
        log_success "Python依赖正常"
    else
        log_warning "Python依赖可能有问题"
    fi
    
    # 测试4: 前端依赖检查
    log_info "测试4: 前端依赖检查"
    if [[ -d "frontend/node_modules" ]]; then
        log_success "前端依赖已安装"
    else
        log_warning "前端依赖未安装，运行: cd frontend && npm install"
    fi
    
    # 测试5: 数据库连接
    log_info "测试5: 数据库连接"
    if python -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import test_connection
if test_connection():
    print('数据库连接正常')
else:
    print('数据库连接失败')
    sys.exit(1)
" 2>/dev/null; then
        log_success "数据库连接正常"
    else
        log_warning "数据库连接可能有问题"
    fi
    
    # 测试6: 配置文件检查
    log_info "测试6: 配置文件检查"
    if [[ -f ".env" ]]; then
        log_success ".env 文件存在"
    else
        log_warning ".env 文件不存在，将使用默认配置"
    fi
    
    echo ""
    log_success "启动测试完成！"
    echo ""
    echo "如果所有测试都通过，可以运行:"
    echo "  ./start_autoclip.sh    # 完整启动"
    echo "  ./quick_start.sh       # 快速启动"
}

main "$@"
