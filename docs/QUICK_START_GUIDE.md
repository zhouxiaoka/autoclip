# 🚀 AI切片项目重构 - 快速开始指南

## 📋 项目简介

AI切片工具是一个基于AI的视频自动切片工具，能够将长视频自动切分为多个精彩片段。本项目正在进行重构，目标是建立现代化的后端架构。

## 🎯 重构目标

1. **数据持久化**: 引入SQLite + SQLAlchemy管理数据
2. **服务模块化**: 重构FastAPI，实现服务模块化管理
3. **任务调度**: 前后端打通任务调度系统

## 🏗️ 项目结构

```
autoclip/
├── backend/                    # 后端服务
│   ├── app/                   # FastAPI应用
│   ├── api/                   # API路由
│   ├── core/                  # 核心模块
│   ├── models/                # 数据模型
│   ├── services/              # 业务服务
│   └── tasks/                 # 任务队列
├── frontend/                   # 前端应用
├── shared/                     # 共享代码
├── docs/                       # 文档
└── data/                       # 数据文件
```

## 🛠️ 开发环境准备

### 必需工具
- Python 3.9+
- Node.js 16+
- Redis
- Git

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd autoclip
```

2. **后端环境设置**
```bash
cd backend
# 安装Poetry (如果未安装)
curl -sSL https://install.python-poetry.org | python3 -

# 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

3. **前端环境设置**
```bash
cd frontend
npm install
```

4. **启动Redis**
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt-get install redis-server
sudo systemctl start redis
```

## 🚀 快速开始

### 1. 启动后端服务
```bash
cd backend
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端服务
```bash
cd frontend
npm run dev
```

### 3. 访问应用
- 前端: http://localhost:3000
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 📚 开发指南

### 后端开发

#### 添加新的API路由
1. 在 `backend/api/v1/` 下创建新的路由文件
2. 在 `backend/app/main.py` 中注册路由
3. 在 `backend/services/` 下实现对应的服务逻辑

```python
# backend/api/v1/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.services.example_service import ExampleService

router = APIRouter()

@router.get("/example")
async def get_example(db: Session = Depends(get_db)):
    service = ExampleService(db)
    return service.get_examples()
```

#### 添加新的数据模型
1. 在 `backend/models/` 下创建新的模型文件
2. 继承 `Base` 类并添加必要的字段
3. 运行数据库迁移

```python
# backend/models/example.py
from sqlalchemy import Column, String, DateTime
from backend.models.base import Base, TimestampMixin

class Example(Base, TimestampMixin):
    __tablename__ = "examples"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
```

#### 添加新的服务
1. 在 `backend/services/` 下创建新的服务文件
2. 实现业务逻辑
3. 添加错误处理和日志记录

```python
# backend/services/example_service.py
from sqlalchemy.orm import Session
from backend.models.example import Example
from backend.schemas.example import ExampleCreate

class ExampleService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_example(self, example_data: ExampleCreate) -> Example:
        example = Example(**example_data.dict())
        self.db.add(example)
        self.db.commit()
        self.db.refresh(example)
        return example
```

### 前端开发

#### 添加新的页面
1. 在 `frontend/src/pages/` 下创建新的页面组件
2. 在路由配置中添加新页面
3. 在导航菜单中添加链接

```typescript
// frontend/src/pages/ExamplePage.tsx
import React from 'react';
import { Card, Table } from 'antd';

const ExamplePage: React.FC = () => {
  return (
    <Card title="示例页面">
      <Table />
    </Card>
  );
};

export default ExamplePage;
```

#### 添加新的API调用
1. 在 `frontend/src/services/` 下添加API方法
2. 在组件中使用API调用
3. 添加错误处理和加载状态

```typescript
// frontend/src/services/api.ts
export const exampleApi = {
  getExamples: async (): Promise<Example[]> => {
    const response = await apiService.get('/examples');
    return response.data;
  },
  
  createExample: async (data: ExampleCreate): Promise<Example> => {
    const response = await apiService.post('/examples', data);
    return response.data;
  }
};
```

## 🧪 测试指南

### 运行后端测试
```bash
cd backend
poetry run pytest
```

### 运行前端测试
```bash
cd frontend
npm test
```

### 运行端到端测试
```bash
# 启动所有服务
npm run test:e2e
```

## 📊 数据库操作

### 创建迁移
```bash
cd backend
alembic revision --autogenerate -m "描述变更"
```

### 应用迁移
```bash
alembic upgrade head
```

### 回滚迁移
```bash
alembic downgrade -1
```

## 🔧 常用命令

### 开发命令
```bash
# 启动后端开发服务器
poetry run uvicorn app.main:app --reload

# 启动前端开发服务器
npm run dev

# 构建前端
npm run build

# 运行测试
poetry run pytest
npm test
```

### 数据库命令
```bash
# 创建迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 查看迁移历史
alembic history
```

### 部署命令
```bash
# 构建Docker镜像
docker build -t autoclip .

# 运行Docker容器
docker run -p 8000:8000 autoclip
```

## 🐛 常见问题

### 1. 数据库连接失败
**问题**: 无法连接到数据库
**解决方案**:
- 检查数据库文件是否存在
- 确认数据库权限设置
- 检查数据库连接字符串

### 2. Redis连接失败
**问题**: Celery无法连接到Redis
**解决方案**:
- 确认Redis服务正在运行
- 检查Redis连接配置
- 确认Redis端口未被占用

### 3. 前端构建失败
**问题**: npm run build 失败
**解决方案**:
- 清除node_modules并重新安装
- 检查TypeScript类型错误
- 确认所有依赖都已安装

### 4. API调用失败
**问题**: 前端无法调用后端API
**解决方案**:
- 确认后端服务正在运行
- 检查CORS配置
- 验证API端点路径

## 📞 获取帮助

### 文档资源
- [重构实施规划](./REFACTOR_IMPLEMENTATION_PLAN.md)
- [工作项拆解](./WORK_ITEMS_BREAKDOWN.md)
- [项目管理](./PROJECT_MANAGEMENT.md)

### 技术栈文档
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [Celery文档](https://docs.celeryproject.org/)
- [React文档](https://reactjs.org/docs/)

### 问题反馈
- 创建GitHub Issue
- 联系项目维护者
- 查看项目Wiki

## 🎉 下一步

1. **熟悉项目结构**: 阅读代码和文档
2. **设置开发环境**: 按照上述步骤配置环境
3. **运行示例**: 启动服务并测试功能
4. **开始开发**: 选择工作项开始开发
5. **提交代码**: 遵循项目的代码规范

---

**文档版本**: 1.0  
**创建日期**: 2024年12月  
**最后更新**: 2024年12月 