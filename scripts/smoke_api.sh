#!/bin/bash

# API 烟雾测试脚本
# 用于验证后端 API 的关键端点是否正常工作

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认参数
BASE_URL=""
TIMEOUT=10
VERBOSE=false

# 帮助信息
show_help() {
    echo "用法: $0 [选项] <BASE_URL>"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示此帮助信息"
    echo "  -t, --timeout  设置超时时间（秒，默认: 10）"
    echo "  -v, --verbose  详细输出"
    echo ""
    echo "示例:"
    echo "  $0 http://127.0.0.1:8000"
    echo "  $0 http://localhost:8000"
    echo "  $0 -t 30 http://127.0.0.1:54321"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -*)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
        *)
            BASE_URL="$1"
            shift
            ;;
    esac
done

# 检查必需参数
if [[ -z "$BASE_URL" ]]; then
    echo -e "${RED}错误: 必须提供 BASE_URL${NC}"
    show_help
    exit 1
fi

# 移除末尾的斜杠
BASE_URL="${BASE_URL%/}"

echo -e "${YELLOW}🚀 开始 API 烟雾测试${NC}"
echo -e "${YELLOW}目标地址: $BASE_URL${NC}"
echo -e "${YELLOW}超时时间: ${TIMEOUT}秒${NC}"
echo ""

# 测试函数
test_endpoint() {
    local endpoint="$1"
    local expected_key="$2"
    local description="$3"
    
    local url="${BASE_URL}${endpoint}"
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${YELLOW}测试: $description${NC}"
        echo -e "${YELLOW}URL: $url${NC}"
    fi
    
    # 执行请求
    local response
    local status_code
    local response_body
    
    if response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null); then
        status_code=$(echo "$response" | tail -n1)
        response_body=$(echo "$response" | head -n -1)
        
        if [[ "$status_code" == "200" ]]; then
            if [[ -n "$expected_key" ]]; then
                if echo "$response_body" | grep -q "$expected_key"; then
                    echo -e "${GREEN}✅ $description${NC}"
                    if [[ "$VERBOSE" == "true" ]]; then
                        echo -e "${GREEN}响应: $response_body${NC}"
                    fi
                    return 0
                else
                    echo -e "${RED}❌ $description - 响应中缺少期望的键: $expected_key${NC}"
                    if [[ "$VERBOSE" == "true" ]]; then
                        echo -e "${RED}响应: $response_body${NC}"
                    fi
                    return 1
                fi
            else
                echo -e "${GREEN}✅ $description${NC}"
                if [[ "$VERBOSE" == "true" ]]; then
                    echo -e "${GREEN}响应: $response_body${NC}"
                fi
                return 0
            fi
        else
            echo -e "${RED}❌ $description - HTTP $status_code${NC}"
            if [[ "$VERBOSE" == "true" ]]; then
                echo -e "${RED}响应: $response_body${NC}"
            fi
            return 1
        fi
    else
        echo -e "${RED}❌ $description - 连接失败${NC}"
        return 1
    fi
}

# 测试计数器
total_tests=0
passed_tests=0

# 执行测试
echo -e "${YELLOW}📋 执行测试用例...${NC}"
echo ""

# 1. 根健康检查
((total_tests++))
if test_endpoint "/health" "status" "根健康检查"; then
    ((passed_tests++))
fi

# 2. API 健康检查
((total_tests++))
if test_endpoint "/api/health" "status" "API 健康检查"; then
    ((passed_tests++))
fi

# 3. 视频分类配置
((total_tests++))
if test_endpoint "/api/v1/video-categories" "categories" "视频分类配置"; then
    ((passed_tests++))
fi

# 4. 项目列表（可能为空，但端点应该存在）
((total_tests++))
if test_endpoint "/api/v1/projects" "data" "项目列表"; then
    ((passed_tests++))
fi

# 5. 设置信息
((total_tests++))
if test_endpoint "/api/v1/settings" "current_provider" "设置信息"; then
    ((passed_tests++))
fi

# 6. 桌面模式检查
((total_tests++))
if test_endpoint "/api/v1/settings/desktop-mode" "is_desktop_mode" "桌面模式检查"; then
    ((passed_tests++))
fi

echo ""
echo -e "${YELLOW}📊 测试结果${NC}"
echo -e "${YELLOW}总测试数: $total_tests${NC}"
echo -e "${GREEN}通过: $passed_tests${NC}"
echo -e "${RED}失败: $((total_tests - passed_tests))${NC}"

# 计算成功率
if [[ $total_tests -gt 0 ]]; then
    success_rate=$((passed_tests * 100 / total_tests))
    echo -e "${YELLOW}成功率: ${success_rate}%${NC}"
    
    if [[ $passed_tests -eq $total_tests ]]; then
        echo -e "${GREEN}🎉 所有测试通过！API 运行正常${NC}"
        exit 0
    elif [[ $success_rate -ge 80 ]]; then
        echo -e "${YELLOW}⚠️  大部分测试通过，但有一些问题${NC}"
        exit 1
    else
        echo -e "${RED}💥 测试失败率过高，API 可能存在问题${NC}"
        exit 2
    fi
else
    echo -e "${RED}❌ 没有执行任何测试${NC}"
    exit 3
fi
