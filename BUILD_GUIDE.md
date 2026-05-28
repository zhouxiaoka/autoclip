# 🚀 AutoClip Desktop 构建指南

## 📋 概述

AutoClip Desktop支持跨平台构建，包括macOS (Intel/ARM)、Windows和Linux。由于架构限制，我们采用以下策略：

- **M芯片Mac**: 本地构建M芯片版本
- **其他平台**: 使用GitHub Actions CI/CD构建

## 🛠️ 本地构建 (M芯片Mac)

### 快速构建
```bash
# 使用专用脚本
./scripts/build_macos_arm.sh
```

### 手动构建
```bash
# 1. 激活虚拟环境
source venv/bin/activate

# 2. 构建前端
cd frontend
npm ci
npm run build
cd ..

# 3. 构建后端
export AUTOCLIP_DESKTOP_MODE=1
export AUTOCLIP_MODE=desktop
python -m PyInstaller --onefile --name autoclip-backend \
  --distpath src-tauri/resources \
  --workpath build/pyinstaller \
  --specpath build/specs \
  --clean --noconfirm \
  backend/desktop_main.py

# 4. 准备FFmpeg
mkdir -p src-tauri/resources/ffmpeg-unified
cp $(which ffmpeg) src-tauri/resources/ffmpeg-unified/ffmpeg-macos
chmod +x src-tauri/resources/ffmpeg-unified/ffmpeg-macos

# 5. 构建Tauri应用
cd src-tauri
tauri build
cd ..
```

## 🌐 跨平台构建 (GitHub Actions)

### 触发构建
```bash
# 创建标签触发构建
git tag v1.0.0
git push origin v1.0.0

# 或手动触发
# 在GitHub仓库页面 -> Actions -> 跨平台构建 -> Run workflow
```

### 构建平台
- **macOS Intel**: x86_64-apple-darwin
- **Windows**: x86_64-pc-windows-msvc  
- **Linux**: x86_64-unknown-linux-gnu

## 📦 构建产物

### 本地构建 (M芯片Mac)
```
src-tauri/target/release/bundle/
├── macos/
│   └── AutoClip Desktop.app          # macOS应用包
└── dmg/
    └── AutoClip Desktop_1.0.0_aarch64.dmg  # DMG安装包
```

### GitHub Actions构建
```
artifacts/
├── autoclip-macos-intel/
│   └── AutoClip Desktop_1.0.0_x64.dmg
├── autoclip-windows/
│   └── AutoClip Desktop_1.0.0_x64.exe
└── autoclip-linux/
    └── AutoClip Desktop_1.0.0_x86_64.AppImage
```

## 🔧 依赖要求

### 本地构建
- **Node.js**: 18+
- **Python**: 3.11+
- **Rust**: 1.70+
- **Tauri CLI**: 2.0+
- **FFmpeg**: 系统安装

### GitHub Actions
- 自动安装所有依赖
- 支持所有目标平台
- 自动生成发布包

## 🚀 快速开始

### 1. 本地测试 (M芯片Mac)
```bash
# 克隆项目
git clone <repository-url>
cd autoclip

# 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 构建
./scripts/build_macos_arm.sh
```

### 2. 跨平台发布
```bash
# 提交代码
git add .
git commit -m "Release v1.0.0"
git push

# 创建标签
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions会自动构建所有平台
```

## 📋 构建检查清单

### 构建前检查
- [ ] 代码已提交
- [ ] 依赖已安装
- [ ] 环境变量已设置
- [ ] FFmpeg已安装

### 构建后验证
- [ ] 应用包存在
- [ ] 安装包存在
- [ ] 文件大小合理
- [ ] 可以正常安装
- [ ] 应用可以启动

## 🐛 故障排除

### 常见问题

#### 1. PyInstaller未找到
```bash
# 激活虚拟环境
source venv/bin/activate
pip install pyinstaller
```

#### 2. Tauri CLI未找到
```bash
# 安装Tauri CLI
cargo install tauri-cli
```

#### 3. FFmpeg未找到
```bash
# macOS
brew install ffmpeg

# 或使用conda
conda install ffmpeg
```

#### 4. 构建失败
```bash
# 清理构建缓存
rm -rf build/
rm -rf src-tauri/target/

# 重新构建
./scripts/build_macos_arm.sh
```

### 日志查看
```bash
# 查看构建日志
tail -f logs/backend.log
tail -f logs/frontend.log
```

## 📞 支持

如果遇到构建问题，请：

1. 查看构建日志
2. 检查依赖版本
3. 提交Issue到GitHub
4. 提供详细的错误信息

## 🔄 更新说明

- **v1.0.0**: 初始版本，支持M芯片Mac
- **v1.1.0**: 添加跨平台构建支持
- **v1.2.0**: 优化构建流程和错误处理
