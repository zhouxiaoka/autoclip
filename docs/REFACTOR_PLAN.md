# 🔄 AI自动切片工具 - 项目重构计划

## 🎯 重构策略：渐进式重构

### 为什么选择渐进式重构？

**优势：**
- ✅ **风险可控** - 逐步改造，避免一次性大改动
- ✅ **功能保持** - 现有功能不会中断
- ✅ **学习成本低** - 团队可以逐步适应新架构
- ✅ **快速验证** - 每个阶段都能看到效果
- ✅ **回滚容易** - 如果出现问题可以快速回滚

## 📋 重构实施计划

### 第一阶段：项目结构重组 (1周)

#### 目标
重新组织项目结构，为后续重构打下基础。

#### 具体操作

**1. 创建新的项目结构**
```bash
# 在项目根目录执行
mkdir -p refactor-backup
cp -r * refactor-backup/  # 备份当前项目

# 创建新的目录结构
mkdir -p {backend,frontend,shared,docs,scripts,tests}
```

**2. 新的项目结构**
```
autoclips-refactored/
├── backend/                    # 后端服务
│   ├── app/                   # FastAPI应用
│   ├── core/                  # 核心模块
│   ├── services/              # 业务服务
│   ├── models/                # 数据模型
│   ├── api/                   # API路由
│   └── utils/                 # 工具函数
├── frontend/                   # 前端应用
│   ├── src/                   # React源码
│   ├── public/                # 静态资源
│   └── dist/                  # 构建输出
├── shared/                     # 共享代码
│   ├── types/                 # 类型定义
│   ├── constants/             # 常量定义
│   └── utils/                 # 共享工具
├── docs/                       # 文档
├── scripts/                    # 脚本工具
├── tests/                      # 测试文件
├── data/                       # 数据文件
├── logs/                       # 日志文件
└── requirements/               # 依赖管理
```

**3. 迁移现有代码**
```bash
# 迁移后端代码
cp -r src/* backend/
cp -r pipeline backend/
cp -r utils backend/

# 迁移前端代码
cp -r frontend/* frontend/

# 迁移配置文件
cp requirements.txt requirements/
cp backend_requirements.txt requirements/
```

**4. 清理冗余文件**
```bash
# 删除重复的API文件
rm -f src/api.py simple_api.py

# 删除实验性文件
rm -f test_*.py
rm -f basic_bilibili_downloader.py
```

### 第二阶段：依赖管理统一 (3-5天)

#### 目标
统一依赖管理，使用现代化的包管理工具。

#### 具体操作

**1. 创建pyproject.toml**
```toml
[tool.poetry]
name = "auto-clips"
version = "1.0.0"
description = "AI自动切片工具"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.9"
fastapi = "^0.104.1"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pydantic = "^2.11.7"
dashscope = "^1.23.5"
pydub = "^0.25.1"
pysrt = "^1.1.2"
aiofiles = "^23.2.1"
python-multipart = "^0.0.6"
cryptography = "^42.0.5"
redis = "^5.0.1"
celery = "^5.3.4"
sqlalchemy = "^2.0.23"
psycopg2-binary = "^2.9.9"

[tool.poetry.dev-dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.21.1"
black = "^23.12.1"
isort = "^5.13.2"
mypy = "^1.8.0"
pre-commit = "^3.6.0"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

**2. 创建package.json (前端)**
```json
{
  "name": "auto-clips-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "antd": "^5.12.8",
    "axios": "^1.6.2",
    "zustand": "^4.4.7",
    "react-router-dom": "^6.20.1"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

**3. 安装依赖**
```bash
# 后端依赖
cd backend
poetry install

# 前端依赖
cd ../frontend
npm install
```

### 第三阶段：后端架构重构 (2-3周)

#### 目标
重构后端架构，采用现代化的设计模式。

#### 具体操作

**1. 创建新的后端结构**
```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import projects, processing, files, settings
from app.core.config import settings as app_settings

app = FastAPI(
    title="AutoClips API",
    description="AI自动切片工具后端API",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(processing.router, prefix="/api/v1/processing", tags=["processing"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])

@app.get("/")
async def root():
    return {"message": "AutoClips API", "version": "1.0.0"}
```

**2. 重构核心模块**
```python
# backend/core/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AutoClips"
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./autoclips.db"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379"
    
    # 文件存储配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 1024 * 1024 * 100  # 100MB
    
    class Config:
        env_file = ".env"

settings = Settings()
```

**3. 重构服务层**
```python
# backend/services/project_service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.core.exceptions import ProjectNotFoundError

class ProjectService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_project(self, project_data: ProjectCreate) -> Project:
        project = Project(**project_data.dict())
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()
    
    def get_projects(self, skip: int = 0, limit: int = 100) -> List[Project]:
        return self.db.query(Project).offset(skip).limit(limit).all()
    
    def update_project(self, project_id: str, project_data: ProjectUpdate) -> Project:
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        
        for field, value in project_data.dict(exclude_unset=True).items():
            setattr(project, field, value)
        
        self.db.commit()
        self.db.refresh(project)
        return project
    
    def delete_project(self, project_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(project_id)
        
        self.db.delete(project)
        self.db.commit()
        return True
```

### 第四阶段：前端架构重构 (2-3周)

#### 目标
重构前端架构，采用现代化的React开发模式。

#### 具体操作

**1. 重构组件结构**
```typescript
// frontend/src/components/layout/AppLayout.tsx
import React from 'react';
import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  HomeOutlined, 
  ProjectOutlined, 
  SettingOutlined,
  HistoryOutlined 
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: '首页',
    },
    {
      key: '/projects',
      icon: <ProjectOutlined />,
      label: '项目管理',
    },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: '处理历史',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  return (
    <Layout style={{ height: '100vh' }}>
      <Header className="app-header">
        <div className="logo">🎬 AutoClips</div>
      </Header>
      
      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={handleMenuClick}
            style={{ height: '100%', borderRight: 0 }}
          />
        </Sider>
        
        <Layout style={{ padding: '24px' }}>
          <Content className="app-content">
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};
```

**2. 重构状态管理**
```typescript
// frontend/src/store/projectStore.ts
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { Project, ProjectStatus } from '../types/project';
import { projectApi } from '../services/api';

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchProjects: () => Promise<void>;
  createProject: (projectData: Partial<Project>) => Promise<Project>;
  updateProject: (id: string, updates: Partial<Project>) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  setCurrentProject: (project: Project | null) => void;
  startProcessing: (projectId: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>()(
  devtools(
    (set, get) => ({
      projects: [],
      currentProject: null,
      loading: false,
      error: null,

      fetchProjects: async () => {
        set({ loading: true, error: null });
        try {
          const projects = await projectApi.getProjects();
          set({ projects, loading: false });
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '获取项目失败',
            loading: false 
          });
        }
      },

      createProject: async (projectData) => {
        set({ loading: true, error: null });
        try {
          const project = await projectApi.createProject(projectData);
          set(state => ({
            projects: [...state.projects, project],
            loading: false
          }));
          return project;
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '创建项目失败',
            loading: false 
          });
          throw error;
        }
      },

      updateProject: async (id, updates) => {
        set({ loading: true, error: null });
        try {
          await projectApi.updateProject(id, updates);
          set(state => ({
            projects: state.projects.map(p => 
              p.id === id ? { ...p, ...updates } : p
            ),
            loading: false
          }));
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '更新项目失败',
            loading: false 
          });
        }
      },

      deleteProject: async (id) => {
        set({ loading: true, error: null });
        try {
          await projectApi.deleteProject(id);
          set(state => ({
            projects: state.projects.filter(p => p.id !== id),
            loading: false
          }));
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '删除项目失败',
            loading: false 
          });
        }
      },

      setCurrentProject: (project) => {
        set({ currentProject: project });
      },

      startProcessing: async (projectId) => {
        set({ loading: true, error: null });
        try {
          await projectApi.startProcessing(projectId);
          set({ loading: false });
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : '开始处理失败',
            loading: false 
          });
        }
      },
    }),
    {
      name: 'project-store',
    }
  )
);
```

**3. 重构API服务**
```typescript
// frontend/src/services/api.ts
import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { Project, ProcessingStatus } from '../types';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1',
      timeout: 300000, // 5分钟超时
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // 请求拦截器
    this.api.interceptors.request.use(
      (config) => {
        // 添加认证token
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // 响应拦截器
    this.api.interceptors.response.use(
      (response: AxiosResponse) => {
        return response.data;
      },
      (error) => {
        // 统一错误处理
        if (error.response?.status === 401) {
          // 处理认证错误
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // 项目相关API
  async getProjects(): Promise<Project[]> {
    return this.api.get('/projects');
  }

  async getProject(id: string): Promise<Project> {
    return this.api.get(`/projects/${id}`);
  }

  async createProject(projectData: Partial<Project>): Promise<Project> {
    return this.api.post('/projects', projectData);
  }

  async updateProject(id: string, updates: Partial<Project>): Promise<Project> {
    return this.api.put(`/projects/${id}`, updates);
  }

  async deleteProject(id: string): Promise<void> {
    return this.api.delete(`/projects/${id}`);
  }

  // 处理相关API
  async startProcessing(projectId: string): Promise<void> {
    return this.api.post(`/projects/${projectId}/process`);
  }

  async getProcessingStatus(projectId: string): Promise<ProcessingStatus> {
    return this.api.get(`/projects/${projectId}/status`);
  }

  // 文件上传API
  async uploadFiles(files: File[], projectId: string): Promise<void> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    formData.append('project_id', projectId);

    return this.api.post('/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  }
}

export const apiService = new ApiService();
```

### 第五阶段：数据库集成 (1-2周)

#### 目标
集成数据库，实现数据持久化。

#### 具体操作

**1. 数据库模型设计**
```python
# backend/models/base.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

```python
# backend/models/project.py
from sqlalchemy import Column, String, Text, JSON, Enum
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin
import enum

class ProjectStatus(str, enum.Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.CREATED)
    video_category = Column(String(50), default="default")
    metadata = Column(JSON)
    
    # 关联关系
    clips = relationship("Clip", back_populates="project")
    collections = relationship("Collection", back_populates="project")
```

**2. 数据库配置**
```python
# backend/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 第六阶段：测试和优化 (1-2周)

#### 目标
完善测试覆盖，优化性能。

#### 具体操作

**1. 单元测试**
```python
# tests/test_project_service.py
import pytest
from unittest.mock import Mock
from app.services.project_service import ProjectService
from app.models.project import Project
from app.schemas.project import ProjectCreate

class TestProjectService:
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def project_service(self, mock_db):
        return ProjectService(mock_db)
    
    def test_create_project(self, project_service, mock_db):
        # Arrange
        project_data = ProjectCreate(
            name="测试项目",
            description="这是一个测试项目"
        )
        mock_project = Project(
            id="test-id",
            name=project_data.name,
            description=project_data.description
        )
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Act
        result = project_service.create_project(project_data)
        
        # Assert
        assert result.name == project_data.name
        assert result.description == project_data.description
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
```

**2. 集成测试**
```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_project():
    response = client.post(
        "/api/v1/projects/",
        json={
            "name": "测试项目",
            "description": "这是一个测试项目"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "测试项目"
```

## 🔧 重构工具和脚本

### 1. 重构辅助脚本
```bash
#!/bin/bash
# scripts/refactor.sh

echo "🔄 开始项目重构..."

# 备份当前项目
echo "📦 备份当前项目..."
mkdir -p backup/$(date +%Y%m%d_%H%M%S)
cp -r * backup/$(date +%Y%m%d_%H%M%S)/

# 创建新目录结构
echo "📁 创建新目录结构..."
mkdir -p {backend,frontend,shared,docs,scripts,tests}

# 迁移代码
echo "📋 迁移现有代码..."
cp -r src/* backend/
cp -r pipeline backend/
cp -r utils backend/
cp -r frontend/* frontend/

# 清理冗余文件
echo "🧹 清理冗余文件..."
rm -f src/api.py simple_api.py
rm -f test_*.py
rm -f basic_bilibili_downloader.py

echo "✅ 重构完成！"
```

### 2. 开发环境脚本
```bash
#!/bin/bash
# scripts/dev.sh

echo "🚀 启动开发环境..."

# 检查依赖
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry未安装，请先安装Poetry"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js未安装，请先安装Node.js"
    exit 1
fi

# 安装后端依赖
echo "📦 安装后端依赖..."
cd backend
poetry install
cd ..

# 安装前端依赖
echo "📦 安装前端依赖..."
cd frontend
npm install
cd ..

# 启动后端服务
echo "🔧 启动后端服务..."
cd backend
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 启动前端服务
echo "🎨 启动前端服务..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "✅ 开发环境启动完成！"
echo "📱 前端地址: http://localhost:3000"
echo "🔌 后端API: http://localhost:8000"
echo "📚 API文档: http://localhost:8000/docs"

# 等待用户中断
trap 'echo "\n🛑 正在停止服务..."; kill $BACKEND_PID $FRONTEND_PID; exit' INT
wait
```

## 📊 重构检查清单

### 第一阶段检查清单
- [ ] 项目结构重组完成
- [ ] 冗余文件清理完成
- [ ] 代码迁移完成
- [ ] 基础功能测试通过

### 第二阶段检查清单
- [ ] Poetry配置完成
- [ ] 依赖安装成功
- [ ] 包管理工具统一
- [ ] 开发环境正常

### 第三阶段检查清单
- [ ] 后端架构重构完成
- [ ] API接口重新设计
- [ ] 服务层重构完成
- [ ] 错误处理完善

### 第四阶段检查清单
- [ ] 前端架构重构完成
- [ ] 组件重新设计
- [ ] 状态管理优化
- [ ] API服务重构

### 第五阶段检查清单
- [ ] 数据库模型设计完成
- [ ] 数据库迁移完成
- [ ] 数据持久化正常
- [ ] 性能优化完成

### 第六阶段检查清单
- [ ] 单元测试覆盖
- [ ] 集成测试完成
- [ ] 性能测试通过
- [ ] 文档更新完成

## 🎯 重构收益

### 技术收益
1. **架构清晰** - 模块化设计，职责分离
2. **代码质量** - 现代化开发实践
3. **可维护性** - 易于理解和修改
4. **可扩展性** - 支持功能扩展

### 开发收益
1. **开发效率** - 更好的开发体验
2. **调试便利** - 清晰的错误信息
3. **测试覆盖** - 完善的测试体系
4. **部署简单** - 标准化的部署流程

### 用户体验收益
1. **响应速度** - 优化的性能表现
2. **稳定性** - 更可靠的系统
3. **功能完整** - 更好的功能体验
4. **错误处理** - 友好的错误提示

---

## 🚀 开始重构

1. **备份项目** - 确保当前代码安全
2. **创建分支** - 在Git中创建重构分支
3. **按阶段执行** - 按照计划逐步执行
4. **持续测试** - 每个阶段都要测试
5. **及时提交** - 定期提交代码

这个渐进式重构方案能够确保项目在重构过程中保持稳定，同时逐步提升代码质量和架构水平。 