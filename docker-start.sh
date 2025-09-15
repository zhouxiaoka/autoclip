#!/bin/bash

# AutoClip Docker 启动脚本
# 版本: 1.0
# 功能: 使用Docker快速启动AutoClip系统

set -euo pipefail

# =============================================================================
# 配置区域
# =============================================================================

# 颜色定义
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
ICON_DOCKER="🐳"

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

# =============================================================================
# 检查函数
# =============================================================================

check_docker() {
    log_header "检查Docker环境"
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    log_success "Docker已安装"
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    log_success "Docker Compose已安装"
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker服务未运行，请启动Docker服务"
        exit 1
    fi
    log_success "Docker服务运行正常"
}

check_environment() {
    log_header "检查环境配置"
    
    if [[ ! -f ".env" ]]; then
        log_warning ".env文件不存在，创建默认配置..."
        if [[ -f "env.example" ]]; then
            cp env.example .env
            log_success "已创建默认.env文件"
            log_warning "请编辑.env文件，填入必要的配置（特别是API密钥）"
        else
            log_error "env.example文件不存在"
            exit 1
        fi
    else
        log_success ".env文件存在"
    fi
    
    # 检查必要的配置
    if ! grep -q "API_DASHSCOPE_API_KEY" .env || grep -q "API_DASHSCOPE_API_KEY=$" .env; then
        log_warning "API_DASHSCOPE_API_KEY未配置，AI功能将不可用"
    fi
}

check_ports() {
    log_header "检查端口占用"
    
    local ports=(8000 3000 6379 5555)
    local occupied_ports=()
    
    for port in "${ports[@]}"; do
        if lsof -i ":$port" >/dev/null 2>&1; then
            occupied_ports+=("$port")
        fi
    done
    
    if [[ ${#occupied_ports[@]} -gt 0 ]]; then
        log_warning "以下端口被占用: ${occupied_ports[*]}"
        log_info "Docker会自动处理端口冲突，但建议先停止占用这些端口的服务"
    else
        log_success "所有端口可用"
    fi
}

# =============================================================================
# 启动函数
# =============================================================================

start_services() {
    log_header "启动AutoClip服务"
    
    # 选择启动模式
    if [[ "${1:-}" == "dev" ]]; then
        log_info "启动开发环境..."
        docker-compose -f docker-compose.dev.yml up -d
        COMPOSE_FILE="docker-compose.dev.yml"
    else
        log_info "启动生产环境..."
        docker-compose up -d
        COMPOSE_FILE="docker-compose.yml"
    fi
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查服务状态
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_success "服务启动成功"
    else
        log_error "服务启动失败"
        log_info "查看日志: docker-compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

show_status() {
    log_header "服务状态"
    
    echo -e "${CYAN}📊 容器状态:${NC}"
    docker-compose ps
    
    echo -e "\n${CYAN}🌐 访问地址:${NC}"
    echo -e "  前端界面: http://localhost:3000"
    echo -e "  后端API:  http://localhost:8000"
    echo -e "  API文档:  http://localhost:8000/docs"
    echo -e "  Flower监控: http://localhost:5555"
    
    echo -e "\n${CYAN}📝 常用命令:${NC}"
    echo -e "  查看日志: docker-compose logs -f"
    echo -e "  停止服务: docker-compose down"
    echo -e "  重启服务: docker-compose restart"
    echo -e "  进入容器: docker-compose exec autoclip bash"
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    log_header "AutoClip Docker 启动器 v1.0"
    
    # 解析参数
    local mode="production"
    if [[ "${1:-}" == "dev" ]]; then
        mode="development"
    fi
    
    log_info "启动模式: $mode"
    
    # 执行检查
    check_docker
    check_environment
    check_ports
    
    # 启动服务
    start_services "$mode"
    
    # 显示状态
    show_status
    
    echo -e "\n${WHITE}🎉 AutoClip Docker 部署完成！${NC}"
    echo -e "${YELLOW}💡 提示: 首次启动可能需要几分钟来下载和构建镜像${NC}"
}

# 显示帮助信息
show_help() {
    echo "AutoClip Docker 启动脚本"
    echo ""
    echo "用法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  dev     启动开发环境"
    echo "  help    显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0          # 启动生产环境"
    echo "  $0 dev      # 启动开发环境"
    echo "  $0 help     # 显示帮助"
}

# 处理参数
case "${1:-}" in
    "help"|"-h"|"--help")
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
