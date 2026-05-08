#!/bin/bash
set -e

echo "🚀 AutoClip 快速构建自检脚本"
echo "================================"

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📁 项目根目录: $PROJECT_ROOT"

# 1) 清理构建产物
echo "🧹 清理构建产物..."
rm -rf frontend/dist
rm -rf frontend/node_modules/.vite
rm -rf src-tauri/target
rm -rf src-tauri/resources

echo "✓ 清理完成"

# 2) 前端重装 + 生产构建
echo "📦 前端依赖安装..."
cd frontend
npm install
echo "✓ 前端依赖安装完成"

echo "🔨 前端生产构建..."
npm run build
echo "✓ 前端构建完成"

# 检查 dist 目录
if [ -d "dist" ]; then
    DIST_SIZE=$(du -sh dist | cut -f1)
    echo "📊 前端产物大小: $DIST_SIZE"
else
    echo "❌ 前端构建失败，dist 目录不存在"
    exit 1
fi

cd "$PROJECT_ROOT"

# 3) 准备资源文件
echo "📋 准备资源文件..."
python scripts/prepare_resources.py
echo "✓ 资源准备完成"

# 4) 检查 .taurignore
echo "📝 检查 .taurignore..."
if [ -f ".taurignore" ]; then
    echo "✓ .taurignore 文件存在"
    echo "排除的文件类型:"
    grep -E "^[^#]" .taurignore | head -10
else
    echo "⚠ .taurignore 文件不存在"
fi

# 5) 检查资源目录大小
echo "📊 资源目录分析..."
if [ -d "src-tauri/resources" ]; then
    RESOURCES_SIZE=$(du -sh src-tauri/resources | cut -f1)
    echo "📦 资源目录大小: $RESOURCES_SIZE"
    
    echo "资源文件列表:"
    find src-tauri/resources -type f -exec ls -lh {} \; | awk '{print $5, $9}' | head -10
else
    echo "❌ 资源目录不存在"
    exit 1
fi

# 6) Release 打包
echo "🔨 开始 Release 打包..."
cd src-tauri

# 设置环境变量关闭调试符号
export RUSTFLAGS="-C debuginfo=0"

# 执行 Tauri 构建
echo "执行: cargo tauri build"
cargo tauri build

echo "✅ 构建完成！"

# 7) 查看最终安装包体积
echo "📊 最终安装包分析..."
if [ -d "target/release/bundle" ]; then
    echo "安装包文件:"
    find target/release/bundle -name "*.dmg" -o -name "*.app" -o -name "*.exe" -o -name "*.deb" -o -name "*.rpm" | while read file; do
        if [ -f "$file" ]; then
            size=$(du -sh "$file" | cut -f1)
            echo "  📦 $file: $size"
        fi
    done
    
    echo ""
    echo "🎉 构建成功！安装包已生成在 target/release/bundle/ 目录"
else
    echo "❌ 构建失败，bundle 目录不存在"
    exit 1
fi

echo ""
echo "✨ 快速自检完成！"
echo "如果安装包体积仍然很大，请检查："
echo "1. 是否还有大文件被打包进去"
echo "2. .taurignore 是否生效"
echo "3. 资源准备脚本是否正确过滤了文件"
