#!/bin/bash
# M芯片Mac专用构建脚本

set -e

echo "🚀 开始构建AutoClip Desktop (M芯片Mac版本)"

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查环境
echo "📋 检查构建环境..."

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    exit 1
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查Rust
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo 未安装"
    exit 1
fi

# 检查Tauri CLI
if ! command -v tauri &> /dev/null; then
    echo "❌ Tauri CLI 未安装"
    exit 1
fi

echo "✅ 环境检查通过"

# 激活虚拟环境
echo "🐍 激活Python虚拟环境..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
else
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv"
    exit 1
fi

# 构建前端
echo "🎨 构建前端..."
cd frontend
npm ci
npm run build
cd ..
echo "✅ 前端构建完成"

# 构建后端
echo "⚙️ 构建后端..."
export AUTOCLIP_DESKTOP_MODE=1
export AUTOCLIP_MODE=desktop

python -m PyInstaller \
    --onefile \
    --name autoclip-backend \
    --distpath src-tauri/resources \
    --workpath build/pyinstaller \
    --specpath build/specs \
    --clean \
    --noconfirm \
    backend/desktop_main.py

# 重命名后端二进制文件
mv src-tauri/resources/autoclip-backend src-tauri/resources/autoclip-backend-macos-arm64
chmod +x src-tauri/resources/autoclip-backend-macos-arm64
echo "✅ 后端构建完成"

# 准备FFmpeg
echo "🎬 准备FFmpeg..."
mkdir -p src-tauri/resources/ffmpeg-unified

if command -v ffmpeg &> /dev/null; then
    cp $(which ffmpeg) src-tauri/resources/ffmpeg-unified/ffmpeg-macos
    chmod +x src-tauri/resources/ffmpeg-unified/ffmpeg-macos
    echo "✅ FFmpeg准备完成"
else
    echo "⚠️ 系统未安装FFmpeg，创建占位符文件"
    touch src-tauri/resources/ffmpeg-unified/ffmpeg-macos
fi

# 构建Tauri应用
echo "🦀 构建Tauri应用..."
cd src-tauri
tauri build
cd ..

# 检查构建结果
echo "📦 检查构建结果..."
if [ -f "src-tauri/target/release/bundle/macos/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop" ]; then
    echo "✅ macOS应用包构建成功"
else
    echo "❌ macOS应用包构建失败"
    exit 1
fi

if [ -f "src-tauri/target/release/bundle/dmg/AutoClip Desktop_1.0.0_aarch64.dmg" ]; then
    echo "✅ DMG安装包构建成功"
else
    echo "❌ DMG安装包构建失败"
    exit 1
fi

# 显示构建结果
echo ""
echo "🎉 构建完成！"
echo ""
echo "📁 构建产物："
echo "   - 应用包: src-tauri/target/release/bundle/macos/AutoClip Desktop.app"
echo "   - 安装包: src-tauri/target/release/bundle/dmg/AutoClip Desktop_1.0.0_aarch64.dmg"
echo ""
echo "📊 文件大小："
ls -lh "src-tauri/target/release/bundle/dmg/AutoClip Desktop_1.0.0_aarch64.dmg"
echo ""
echo "🚀 可以双击DMG文件进行安装测试！"
