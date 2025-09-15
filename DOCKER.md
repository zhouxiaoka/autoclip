# Docker 部署指南

本文档介绍如何使用Docker部署AutoClip系统。

## 📋 目录

- [快速开始](#快速开始)
- [生产环境部署](#生产环境部署)
- [开发环境部署](#开发环境部署)
- [配置说明](#配置说明)
- [数据管理](#数据管理)
- [故障排除](#故障排除)

## 🚀 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

### 一键启动

```bash
# 克隆项目
git clone https://github.com/your-username/autoclip.git
cd autoclip

# 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入必要的配置

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 访问服务

- **前端界面**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Flower监控**: http://localhost:5555

## 🏭 生产环境部署

### 使用生产配置

```bash
# 使用生产环境配置
docker-compose -f docker-compose.yml up -d

# 后台运行
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f autoclip
```

### 生产环境优化

1. **资源限制**
```yaml
# 在docker-compose.yml中添加资源限制
services:
  autoclip:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

2. **数据持久化**
```bash
# 创建数据卷
docker volume create autoclip_data
docker volume create autoclip_logs

# 在docker-compose.yml中配置
volumes:
  - autoclip_data:/app/data
  - autoclip_logs:/app/logs
```

3. **网络配置**
```yaml
# 使用自定义网络
networks:
  autoclip-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## 🛠️ 开发环境部署

### 使用开发配置

```bash
# 使用开发环境配置
docker-compose -f docker-compose.dev.yml up -d

# 实时查看日志
docker-compose -f docker-compose.dev.yml logs -f

# 进入容器调试
docker-compose -f docker-compose.dev.yml exec autoclip-dev bash
```

### 开发环境特性

- 热重载支持
- 调试模式
- 详细日志
- 代码挂载

## ⚙️ 配置说明

### 环境变量

创建 `.env` 文件：

```bash
# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis配置
REDIS_URL=redis://redis:6379/0

# API配置
API_DASHSCOPE_API_KEY=your_dashscope_api_key
API_MODEL_NAME=qwen-plus

# 日志配置
LOG_LEVEL=INFO
ENVIRONMENT=production
DEBUG=false

# 文件存储
UPLOAD_DIR=./data/uploads
PROJECT_DIR=./data/projects
```

### 服务配置

#### 主应用服务
- **端口**: 8000 (后端), 3000 (前端)
- **健康检查**: `/api/v1/health/`
- **重启策略**: `unless-stopped`

#### Redis服务
- **端口**: 6379
- **持久化**: AOF模式
- **内存限制**: 可配置

#### Celery服务
- **Worker**: 处理异步任务
- **Beat**: 定时任务调度
- **并发数**: 可配置

## 💾 数据管理

### 数据持久化

```bash
# 查看数据卷
docker volume ls

# 备份数据
docker run --rm -v autoclip_data:/data -v $(pwd):/backup alpine tar czf /backup/autoclip-backup.tar.gz -C /data .

# 恢复数据
docker run --rm -v autoclip_data:/data -v $(pwd):/backup alpine tar xzf /backup/autoclip-backup.tar.gz -C /data
```

### 数据目录结构

```
data/
├── autoclip.db          # SQLite数据库
├── projects/            # 项目数据
├── uploads/             # 上传文件
├── temp/                # 临时文件
└── output/              # 输出文件
```

### 清理数据

```bash
# 清理临时文件
docker-compose exec autoclip find /app/data/temp -type f -mtime +7 -delete

# 清理日志
docker-compose exec autoclip find /app/logs -name "*.log" -mtime +30 -delete
```

## 🔧 故障排除

### 常见问题

#### 1. 服务启动失败

```bash
# 查看服务状态
docker-compose ps

# 查看详细日志
docker-compose logs autoclip

# 重启服务
docker-compose restart autoclip
```

#### 2. 端口冲突

```bash
# 检查端口占用
netstat -tulpn | grep :8000

# 修改端口映射
# 在docker-compose.yml中修改ports配置
ports:
  - "8001:8000"  # 将本地8001端口映射到容器8000端口
```

#### 3. 内存不足

```bash
# 查看容器资源使用
docker stats

# 限制资源使用
# 在docker-compose.yml中添加deploy配置
```

#### 4. 数据丢失

```bash
# 检查数据卷
docker volume inspect autoclip_data

# 恢复备份
# 使用上述备份恢复命令
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs autoclip
docker-compose logs celery-worker

# 实时查看日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100
```

### 性能监控

```bash
# 查看容器资源使用
docker stats

# 查看服务健康状态
docker-compose ps

# 进入容器调试
docker-compose exec autoclip bash
```

## 🔄 更新和维护

### 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### 备份策略

```bash
#!/bin/bash
# backup.sh - 自动备份脚本

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/autoclip"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据
docker run --rm -v autoclip_data:/data -v $BACKUP_DIR:/backup alpine \
    tar czf /backup/autoclip-data-$DATE.tar.gz -C /data .

# 备份配置
cp .env $BACKUP_DIR/autoclip-config-$DATE.env

# 清理旧备份（保留7天）
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.env" -mtime +7 -delete

echo "备份完成: $DATE"
```

### 监控脚本

```bash
#!/bin/bash
# monitor.sh - 服务监控脚本

# 检查服务状态
if ! docker-compose ps | grep -q "Up"; then
    echo "服务异常，尝试重启..."
    docker-compose restart
fi

# 检查健康状态
if ! curl -f http://localhost:8000/api/v1/health/ >/dev/null 2>&1; then
    echo "健康检查失败，发送告警..."
    # 这里可以添加告警逻辑
fi
```

## 📚 高级配置

### 使用外部数据库

```yaml
# 使用PostgreSQL
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: autoclip
      POSTGRES_USER: autoclip
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  autoclip:
    environment:
      - DATABASE_URL=postgresql://autoclip:password@postgres:5432/autoclip
    depends_on:
      - postgres
```

### 使用外部Redis

```yaml
# 使用外部Redis集群
services:
  autoclip:
    environment:
      - REDIS_URL=redis://redis-cluster:6379/0
    external_links:
      - redis-cluster:redis
```

### 负载均衡

```yaml
# 使用Nginx负载均衡
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - autoclip

  autoclip:
    # 可以启动多个实例
    scale: 3
```

## 🆘 获取帮助

如果遇到问题，请：

1. 查看本文档的故障排除部分
2. 检查GitHub Issues
3. 查看项目文档
4. 联系技术支持

---

**最后更新**: 2024-01-15
