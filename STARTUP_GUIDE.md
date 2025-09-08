# AutoClip 系统启动指南

## 📋 概述

AutoClip 是一个基于AI的视频切片处理系统，采用前后端分离架构。本指南将帮助您快速启动和运行整个系统。

## 🚀 快速开始

### 1. 一键启动（推荐）

```bash
# 完整启动（包含详细检查和健康监控）
./start_autoclip.sh

# 快速启动（开发环境，跳过详细检查）
./quick_start.sh
```

### 2. 系统管理

```bash
# 检查系统状态
./status_autoclip.sh

# 停止所有服务
./stop_autoclip.sh
```

## 📊 系统架构

### 后端服务
- **FastAPI**: RESTful API 和 WebSocket 支持
- **Celery**: 异步任务队列
- **Redis**: 消息代理和缓存
- **SQLite**: 数据存储

### 前端服务
- **React**: 用户界面
- **Vite**: 开发服务器
- **TypeScript**: 类型安全

## 🔧 环境要求

### 系统要求
- macOS 或 Linux
- Python 3.8+
- Node.js 16+
- Redis 服务器

### 依赖安装

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装Python依赖
pip install -r requirements.txt

# 3. 安装前端依赖
cd frontend
npm install
cd ..

# 4. 安装Redis（macOS）
brew install redis
brew services start redis

# 5. 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入必要的配置
```

## 📝 配置文件

### 环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis配置
REDIS_URL=redis://localhost:6379/0

# API配置
API_DASHSCOPE_API_KEY=your_api_key_here
API_MODEL_NAME=qwen-plus

# 日志配置
LOG_LEVEL=INFO
ENVIRONMENT=development
DEBUG=true
```

## 🌐 服务端口

| 服务 | 端口 | 描述 |
|------|------|------|
| 前端界面 | 3000 | React 开发服务器 |
| 后端API | 8000 | FastAPI 服务器 |
| Redis | 6379 | 消息代理 |
| API文档 | 8000/docs | Swagger UI |

## 📁 目录结构

```
autoclip/
├── backend/                 # 后端代码
│   ├── api/                # API路由
│   ├── core/               # 核心配置
│   ├── models/             # 数据模型
│   ├── services/           # 业务逻辑
│   └── tasks/              # Celery任务
├── frontend/               # 前端代码
│   ├── src/                # 源代码
│   └── public/             # 静态资源
├── data/                   # 数据存储
│   ├── projects/           # 项目数据
│   └── uploads/            # 上传文件
├── logs/                   # 日志文件
├── scripts/                # 工具脚本
└── *.sh                    # 启动脚本
```

## 🔍 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   # 检查端口占用
   lsof -i :8000
   lsof -i :3000
   
   # 停止占用进程
   kill -9 <PID>
   ```

2. **Redis连接失败**
   ```bash
   # 检查Redis状态
   redis-cli ping
   
   # 启动Redis
   brew services start redis  # macOS
   systemctl start redis      # Linux
   ```

3. **Python依赖问题**
   ```bash
   # 重新安装依赖
   pip install -r requirements.txt --force-reinstall
   ```

4. **前端依赖问题**
   ```bash
   # 清理并重新安装
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   ```

### 日志查看

```bash
# 查看所有日志
tail -f logs/*.log

# 查看特定服务日志
tail -f logs/backend.log
tail -f logs/frontend.log
tail -f logs/celery.log
```

### 系统状态检查

```bash
# 详细状态检查
./status_autoclip.sh

# 手动检查服务
curl http://localhost:8000/api/v1/health/
curl http://localhost:3000/
redis-cli ping
```

## 🛠️ 开发模式

### 后端开发

```bash
# 激活虚拟环境
source venv/bin/activate

# 设置Python路径
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# 启动后端（开发模式）
python -m uvicorn backend.main:app --reload --port 8000
```

### 前端开发

```bash
# 进入前端目录
cd frontend

# 启动开发服务器
npm run dev
```

### Celery Worker

```bash
# 启动Worker
celery -A backend.core.celery_app worker --loglevel=info

# 启动Beat调度器
celery -A backend.core.celery_app beat --loglevel=info

# 启动Flower监控
celery -A backend.core.celery_app flower --port=5555
```

## 📈 性能优化

### 生产环境配置

1. **数据库优化**
   - 使用PostgreSQL替代SQLite
   - 配置连接池
   - 启用查询缓存

2. **Redis优化**
   - 配置内存限制
   - 启用持久化
   - 设置过期策略

3. **Celery优化**
   - 调整并发数
   - 配置任务路由
   - 启用结果后端

## 🔒 安全配置

### 生产环境安全

1. **环境变量**
   - 使用强密码
   - 定期轮换密钥
   - 限制API访问

2. **网络安全**
   - 配置防火墙
   - 使用HTTPS
   - 限制CORS

3. **数据安全**
   - 定期备份
   - 加密敏感数据
   - 访问控制

## 📞 支持

如果遇到问题，请：

1. 查看日志文件
2. 运行状态检查脚本
3. 检查环境配置
4. 参考故障排除部分

## 📄 许可证

本项目采用 MIT 许可证。
