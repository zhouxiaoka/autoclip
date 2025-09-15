#!/bin/bash

# AutoClip Docker 状态检查脚本
# 版本: 1.0
# 功能: 检查AutoClip Docker服务状态

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
ICON_HEALTH="💚"
ICON_SICK="🤒"
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
    log_header "Docker环境检查"
    
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker未安装"
        return 1
    fi
    log_success "Docker已安装"
    
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose未安装"
        return 1
    fi
    log_success "Docker Compose已安装"
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker服务未运行"
        return 1
    fi
    log_success "Docker服务运行正常"
    
    return 0
}

check_containers() {
    log_header "容器状态检查"
    
    local containers=$(docker ps -a --filter "name=autoclip" --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true)
    
    if [[ -z "$containers" ]]; then
        log_warning "没有发现AutoClip容器"
        return 1
    fi
    
    echo -e "${CYAN}📊 容器状态:${NC}"
    echo "$containers" | while IFS=$'\t' read -r name status ports; do
        if [[ "$status" == *"Up"* ]]; then
            echo -e "  ${GREEN}${ICON_HEALTH} $name${NC} - $status"
        else
            echo -e "  ${RED}${ICON_SICK} $name${NC} - $status"
        fi
    done
    
    return 0
}

check_services() {
    log_header "服务健康检查"
    
    # 检查后端API
    if curl -fsS "http://localhost:8000/api/v1/health/" >/dev/null 2>&1; then
        log_success "后端API服务健康"
    else
        log_error "后端API服务不健康"
    fi
    
    # 检查前端服务
    if curl -fsS "http://localhost:3000/" >/dev/null 2>&1; then
        log_success "前端服务健康"
    else
        log_error "前端服务不健康"
    fi
    
    # 检查Redis
    if docker exec autoclip-redis redis-cli ping >/dev/null 2>&1; then
        log_success "Redis服务健康"
    else
        log_error "Redis服务不健康"
    fi
}

check_volumes() {
    log_header "数据卷检查"
    
    local volumes=$(docker volume ls --filter "name=autoclip" --format "{{.Name}}\t{{.Driver}}\t{{.Size}}" 2>/dev/null || true)
    
    if [[ -z "$volumes" ]]; then
        log_warning "没有发现AutoClip数据卷"
        return 1
    fi
    
    echo -e "${CYAN}💾 数据卷:${NC}"
    echo "$volumes" | while IFS=$'\t' read -r name driver size; do
        echo -e "  ${ICON_INFO} $name ($driver) - $size"
    done
    
    return 0
}

check_networks() {
    log_header "网络检查"
    
    local networks=$(docker network ls --filter "name=autoclip" --format "{{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null || true)
    
    if [[ -z "$networks" ]]; then
        log_warning "没有发现AutoClip网络"
        return 1
    fi
    
    echo -e "${CYAN}🌐 网络:${NC}"
    echo "$networks" | while IFS=$'\t' read -r name driver scope; do
        echo -e "  ${ICON_INFO} $name ($driver) - $scope"
    done
    
    return 0
}

check_resources() {
    log_header "资源使用情况"
    
    echo -e "${CYAN}📊 容器资源使用:${NC}"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" $(docker ps --filter "name=autoclip" --format "{{.Names}}" 2>/dev/null || true) 2>/dev/null || log_warning "无法获取资源使用情况"
}

show_access_info() {
    log_header "访问信息"
    
    echo -e "${CYAN}🌐 服务访问地址:${NC}"
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
    log_header "AutoClip Docker 状态检查 v1.0"
    
    local overall_status=0
    
    # 检查Docker环境
    if ! check_docker; then
        overall_status=1
    fi
    
    # 检查容器状态
    if ! check_containers; then
        overall_status=1
    fi
    
    # 检查服务健康状态
    check_services
    
    # 检查数据卷
    check_volumes
    
    # 检查网络
    check_networks
    
    # 检查资源使用
    check_resources
    
    # 显示访问信息
    show_access_info
    
    # 显示总体状态
    log_header "总体状态"
    
    if [[ $overall_status -eq 0 ]]; then
        log_success "AutoClip Docker服务运行正常"
        echo -e "\n${WHITE}🎉 所有服务健康！${NC}"
    else
        log_error "部分服务存在问题"
        echo -e "\n${YELLOW}💡 建议操作:${NC}"
        echo -e "  1. 查看详细日志: docker-compose logs"
        echo -e "  2. 重启服务: docker-compose restart"
        echo -e "  3. 重新启动: ./docker-start.sh"
    fi
}

# 显示帮助信息
show_help() {
    echo "AutoClip Docker 状态检查脚本"
    echo ""
    echo "用法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  help    显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0          # 检查服务状态"
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
