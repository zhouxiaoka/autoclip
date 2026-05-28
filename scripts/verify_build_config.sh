#!/bin/bash
set -e

echo "🔍 AutoClip 构建配置验证脚本"
echo "================================"

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 项目根目录: $PROJECT_ROOT"

# 1. 检查前端构建产物
echo "🔍 检查前端构建产物..."
if [ -d "frontend/dist" ]; then
    FRONTEND_SIZE=$(du -sh frontend/dist | cut -f1)
    echo "✓ 前端产物存在，大小: $FRONTEND_SIZE"
    
    # 检查关键文件
    if [ -f "frontend/dist/index.html" ]; then
        echo "✓ index.html 存在"
    else
        echo "❌ index.html 不存在"
    fi
    
    # 检查是否有 sourcemap
    SOURCEMAP_COUNT=$(find frontend/dist -name "*.map" | wc -l)
    if [ "$SOURCEMAP_COUNT" -eq 0 ]; then
        echo "✓ 没有 sourcemap 文件（符合预期）"
    else
        echo "⚠ 发现 $SOURCEMAP_COUNT 个 sourcemap 文件"
    fi
else
    echo "❌ 前端产物不存在，请先运行: cd frontend && npm run build"
    exit 1
fi

# 2. 检查 Tauri 配置
echo ""
echo "🔍 检查 Tauri 配置..."
TAURI_CONFIG="src-tauri/tauri.conf.json"

if [ -f "$TAURI_CONFIG" ]; then
    echo "✓ tauri.conf.json 存在"
    
    # 检查 beforeBuildCommand
    if grep -q "beforeBuildCommand" "$TAURI_CONFIG"; then
        echo "✓ beforeBuildCommand 已配置"
    else
        echo "❌ beforeBuildCommand 未配置"
    fi
    
    # 检查 frontendDist
    if grep -q "frontendDist" "$TAURI_CONFIG"; then
        echo "✓ frontendDist 已配置"
    else
        echo "❌ frontendDist 未配置"
    fi
    
    # 检查资源配置
    if grep -q "resources" "$TAURI_CONFIG"; then
        echo "✓ resources 已配置"
        echo "资源配置:"
        grep -A 10 '"resources"' "$TAURI_CONFIG" | grep -E '^\s*"[^"]*"' | sed 's/^/  /'
    else
        echo "❌ resources 未配置"
    fi
else
    echo "❌ tauri.conf.json 不存在"
    exit 1
fi

# 3. 检查 .taurignore
echo ""
echo "🔍 检查 .taurignore..."
if [ -f ".taurignore" ]; then
    echo "✓ .taurignore 存在"
    echo "排除的主要文件类型:"
    grep -E "^[^#]" .taurignore | head -5 | sed 's/^/  /'
else
    echo "❌ .taurignore 不存在"
fi

# 4. 检查资源准备脚本
echo ""
echo "🔍 检查资源准备脚本..."
if [ -f "scripts/prepare_resources.py" ]; then
    echo "✓ prepare_resources.py 存在"
    if [ -x "scripts/prepare_resources.py" ]; then
        echo "✓ 脚本有执行权限"
    else
        echo "⚠ 脚本没有执行权限"
    fi
else
    echo "❌ prepare_resources.py 不存在"
fi

# 5. 检查当前资源目录
echo ""
echo "🔍 检查当前资源目录..."
if [ -d "src-tauri/resources" ]; then
    RESOURCES_SIZE=$(du -sh src-tauri/resources | cut -f1)
    echo "✓ 资源目录存在，大小: $RESOURCES_SIZE"
    
    # 检查是否包含三平台 ffmpeg
    FFMPEG_PLATFORMS=$(find src-tauri/resources -name "ffmpeg*" -type d | wc -l)
    if [ "$FFMPEG_PLATFORMS" -le 1 ]; then
        echo "✓ ffmpeg 平台文件数量合理"
    else
        echo "⚠ 发现多个 ffmpeg 平台目录，可能包含三平台文件"
    fi
    
    # 检查是否包含不必要的大文件
    LARGE_FILES=$(find src-tauri/resources -type f -size +10M | wc -l)
    if [ "$LARGE_FILES" -eq 0 ]; then
        echo "✓ 没有发现大于 10MB 的文件"
    else
        echo "⚠ 发现 $LARGE_FILES 个大于 10MB 的文件:"
        find src-tauri/resources -type f -size +10M -exec ls -lh {} \;
    fi
else
    echo "⚠ 资源目录不存在，运行构建时会自动创建"
fi

# 6. 检查 Vite 配置
echo ""
echo "🔍 检查 Vite 配置..."
VITE_CONFIG="frontend/vite.config.ts"
if [ -f "$VITE_CONFIG" ]; then
    echo "✓ vite.config.ts 存在"
    
    if grep -q "sourcemap: false" "$VITE_CONFIG"; then
        echo "✓ sourcemap 已禁用"
    else
        echo "⚠ sourcemap 可能未禁用"
    fi
    
    if grep -q "assetsInlineLimit" "$VITE_CONFIG"; then
        echo "✓ assetsInlineLimit 已配置"
    else
        echo "⚠ assetsInlineLimit 未配置"
    fi
else
    echo "❌ vite.config.ts 不存在"
fi

echo ""
echo "🎯 配置验证总结:"
echo "=================="

# 计算预期安装包大小
FRONTEND_SIZE_MB=$(du -sm frontend/dist | cut -f1)
RESOURCES_SIZE_MB=$(du -sm src-tauri/resources 2>/dev/null | cut -f1 || echo "0")

echo "📊 预期安装包组成:"
echo "  - 前端产物: ${FRONTEND_SIZE_MB}MB"
echo "  - 后端资源: ${RESOURCES_SIZE_MB}MB"
echo "  - Tauri 运行时: ~50MB"
echo "  - 总计预期: ~$((FRONTEND_SIZE_MB + RESOURCES_SIZE_MB + 50))MB"

if [ $((FRONTEND_SIZE_MB + RESOURCES_SIZE_MB + 50)) -lt 200 ]; then
    echo "✅ 预期安装包大小合理（< 200MB）"
else
    echo "⚠ 预期安装包可能仍然较大（> 200MB）"
fi

echo ""
echo "✨ 配置验证完成！"
echo "如果所有检查都通过，可以运行: ./scripts/quick_build_check.sh 进行完整构建"
