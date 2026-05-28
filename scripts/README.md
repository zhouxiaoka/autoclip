# AutoClip 桌面客户端开发脚本

本目录包含了AutoClip桌面客户端的开发、构建和测试脚本。

## 📁 脚本说明

### 🔧 构建脚本

#### `build_backend.py`
构建后端二进制文件，使用PyInstaller打包Python代码。

```bash
python scripts/build_backend.py
```

**功能:**
- 安装Python依赖
- 安装PyInstaller
- 创建PyInstaller规格文件
- 构建单文件可执行程序
- 将构建结果复制到Tauri资源目录

#### `build_desktop.py`
构建完整的桌面应用，包括前端、后端和Tauri应用。

```bash
python scripts/build_desktop.py
```

**功能:**
- 检查构建环境（Node.js、npm、Rust、Tauri CLI）
- 构建后端二进制
- 安装前端依赖
- 构建前端
- 构建Tauri应用
- 显示构建结果

### 🚀 开发脚本

#### `dev_desktop.py`
管理桌面应用的开发环境。

```bash
# 启动开发环境
python scripts/dev_desktop.py start

# 停止开发环境
python scripts/dev_desktop.py stop

# 重启开发环境
python scripts/dev_desktop.py restart

# 查看状态
python scripts/dev_desktop.py status

# 安装依赖
python scripts/dev_desktop.py install
```

**功能:**
- 自动安装依赖
- 启动后端服务
- 启动前端开发服务器
- 启动Tauri开发模式
- 进程管理和监控
- 服务健康检查

### 🧪 测试脚本

#### `test_desktop.py`
运行桌面应用的功能测试。

```bash
python scripts/test_desktop.py
```

**测试项目:**
- 文件结构完整性
- Python依赖检查
- Node.js依赖检查
- Rust环境检查
- Tauri配置验证
- Cargo配置验证
- 前端构建测试
- 后端API测试（需要服务运行）

## 🛠️ 环境要求

### 必需工具
- **Python 3.11+** - 后端开发
- **Node.js 18+** - 前端开发
- **Rust 1.70+** - Tauri应用开发
- **Tauri CLI** - 桌面应用构建

### 安装Tauri CLI
```bash
npm install -g @tauri-apps/cli
```

## 🚀 快速开始

### 1. 开发环境
```bash
# 启动开发环境
python scripts/dev_desktop.py start

# 查看状态
python scripts/dev_desktop.py status

# 停止开发环境
python scripts/dev_desktop.py stop
```

### 2. 功能测试
```bash
# 运行所有测试
python scripts/test_desktop.py

# 查看帮助
python scripts/test_desktop.py --help
```

### 3. 构建发布版本
```bash
# 构建完整桌面应用
python scripts/build_desktop.py
```

## 📊 项目结构

```
autoclip/
├── backend/                    # 后端代码
│   ├── desktop_main.py        # 桌面模式主启动文件
│   ├── desktop_celery.py      # 桌面模式Celery配置
│   ├── core/desktop_config.py # 桌面配置管理
│   └── api/v1/desktop.py      # 桌面专用API
├── src-tauri/                 # Tauri桌面应用
│   ├── src/
│   │   ├── lib.rs            # 主入口
│   │   ├── backend_manager.rs # 后端管理器
│   │   ├── commands.rs       # Tauri命令
│   │   └── tray.rs          # 系统托盘
│   ├── tauri.conf.json       # Tauri配置
│   └── Cargo.toml           # Rust依赖
├── frontend/src/components/   # 前端组件
│   ├── DesktopSettings.tsx   # 桌面设置界面
│   └── OfflineModeIndicator.tsx # 离线模式指示器
└── scripts/                  # 开发脚本
    ├── build_backend.py      # 后端构建脚本
    ├── build_desktop.py      # 完整构建脚本
    ├── dev_desktop.py        # 开发环境管理
    ├── test_desktop.py       # 功能测试脚本
    └── README.md            # 本文档
```

## 🔧 配置说明

### 桌面模式配置
桌面应用使用专门的配置系统，配置文件位置：
- **macOS**: `~/Library/Application Support/AutoClip/config.json`
- **Windows**: `%LOCALAPPDATA%/AutoClip/config.json`

### 环境变量
开发模式下会自动设置以下环境变量：
- `AUTOCLIP_DESKTOP_MODE=true`
- `AUTOCLIP_MODE=desktop`

## 🐛 故障排除

### 常见问题

#### 1. 后端服务启动失败
```bash
# 检查端口是否被占用
lsof -i :8000

# 检查Python依赖
python -c "import fastapi, uvicorn, celery"
```

#### 2. 前端构建失败
```bash
# 清理node_modules并重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install
```

#### 3. Tauri构建失败
```bash
# 检查Rust环境
rustc --version
cargo --version

# 检查Tauri CLI
tauri --version
```

#### 4. 权限问题
```bash
# 给脚本执行权限
chmod +x scripts/*.py
```

### 日志查看
- **后端日志**: `data/logs/autoclip.log`
- **开发进程**: `dev_processes.json`

## 📝 开发说明

### 代码结构
- **后端**: 使用FastAPI + Celery + SQLite
- **前端**: 使用React + TypeScript + Ant Design
- **桌面**: 使用Tauri + Rust

### 开发流程
1. 使用 `dev_desktop.py start` 启动开发环境
2. 修改代码，自动热重载
3. 使用 `test_desktop.py` 运行测试
4. 使用 `build_desktop.py` 构建发布版本

### 贡献指南
1. Fork项目
2. 创建功能分支
3. 运行测试确保通过
4. 提交Pull Request

## 📞 支持

如果遇到问题，请：
1. 查看本文档的故障排除部分
2. 运行 `test_desktop.py` 检查环境
3. 查看日志文件
4. 提交Issue到项目仓库

---

**最后更新**: 2024年12月
**版本**: 1.0.0
