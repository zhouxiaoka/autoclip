# 👨‍💻 AutoClip Desktop 开发者指南

## 📋 目录

- [项目架构](#项目架构)
- [开发环境设置](#开发环境设置)
- [代码结构](#代码结构)
- [核心模块](#核心模块)
- [API接口](#api接口)
- [前端开发](#前端开发)
- [后端开发](#后端开发)
- [Tauri集成](#tauri集成)
- [构建和部署](#构建和部署)
- [测试](#测试)
- [贡献指南](#贡献指南)

## 🏗️ 项目架构

### 整体架构

```
AutoClip Desktop
├── Frontend (React + TypeScript + Ant Design)
├── Backend (Python + FastAPI + Celery)
├── Tauri (Rust + WebView)
└── Resources (FFmpeg + 模型文件)
```

### 技术栈

- **前端**: React 18, TypeScript, Ant Design, Vite
- **后端**: Python 3.9+, FastAPI, Celery, SQLAlchemy
- **桌面**: Tauri 2.0, Rust
- **数据库**: SQLite (桌面模式)
- **任务队列**: Celery with SQLite transport
- **AI服务**: OpenAI, DashScope, Google Gemini
- **语音识别**: Whisper, 云端API

## 🛠️ 开发环境设置

### 系统要求

- **Node.js**: 18.0+
- **Python**: 3.9+
- **Rust**: 1.70+
- **Git**: 2.0+

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-org/autoclip-desktop.git
cd autoclip-desktop
```

2. **安装前端依赖**
```bash
cd frontend
npm install
```

3. **安装后端依赖**
```bash
cd ../backend
pip install -r requirements.txt
```

4. **安装Tauri依赖**
```bash
cd ../src-tauri
cargo install tauri-cli
```

5. **设置环境变量**
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
nano .env
```

### 开发环境配置

```bash
# 启动开发环境
npm run dev

# 启动后端服务
python backend/desktop_main.py

# 构建Tauri应用
npm run tauri build
```

## 📁 代码结构

### 前端结构

```
frontend/
├── src/
│   ├── components/          # 通用组件
│   │   ├── ErrorBoundary.tsx
│   │   ├── OfflineIndicator.tsx
│   │   └── ...
│   ├── pages/              # 页面组件
│   │   ├── HomePage.tsx
│   │   ├── SettingsPage.tsx
│   │   ├── OnboardingPage.tsx
│   │   └── ...
│   ├── hooks/              # 自定义Hooks
│   │   ├── useFirstRun.ts
│   │   ├── useDesktopConfig.ts
│   │   └── ...
│   ├── services/           # API服务
│   │   ├── api.ts
│   │   ├── projectApi.ts
│   │   └── ...
│   ├── store/              # 状态管理
│   │   ├── useProjectStore.ts
│   │   ├── useConfigStore.ts
│   │   └── ...
│   ├── utils/              # 工具函数
│   │   ├── apiUtils.ts
│   │   ├── errorHandler.ts
│   │   └── ...
│   └── types/              # 类型定义
│       ├── api.ts
│       ├── project.ts
│       └── ...
├── public/                 # 静态资源
└── package.json
```

### 后端结构

```
backend/
├── api/                    # API路由
│   └── v1/
│       ├── projects.py
│       ├── settings.py
│       ├── health.py
│       └── ...
├── core/                   # 核心模块
│   ├── desktop_config.py
│   ├── llm_providers.py
│   ├── speech_recognition.py
│   └── ...
├── services/               # 业务服务
│   ├── project_service.py
│   ├── video_service.py
│   ├── ai_service.py
│   └── ...
├── models/                 # 数据模型
│   ├── project.py
│   ├── clip.py
│   └── ...
├── utils/                  # 工具模块
│   ├── error_handler.py
│   ├── performance_config.py
│   ├── chunked_upload.py
│   └── ...
├── tasks/                  # Celery任务
│   ├── __init__.py
│   ├── video_tasks.py
│   └── ...
├── desktop_main.py         # 桌面应用入口
├── desktop_celery.py       # 桌面Celery配置
└── requirements.txt
```

### Tauri结构

```
src-tauri/
├── src/
│   ├── lib.rs              # 主入口
│   ├── commands.rs         # Tauri命令
│   ├── backend_manager.rs  # 后端管理
│   └── tray.rs             # 系统托盘
├── Cargo.toml              # Rust依赖
├── tauri.conf.json         # Tauri配置
└── resources/              # 资源文件
    └── ffmpeg/             # FFmpeg二进制
```

## 🔧 核心模块

### 1. 桌面配置管理

**文件**: `backend/core/desktop_config.py`

```python
class DesktopConfig:
    """桌面应用配置管理"""
    
    def __init__(self):
        self.data_dir = self._get_desktop_data_dir()
        self.config_file = self.data_dir / "config.json"
        self.settings_file = self.data_dir / "settings.json"
    
    def save_desktop_config(self, config: 'DesktopConfig') -> bool:
        """保存桌面配置"""
        try:
            config_dict = config.dict()
            # 递归转换Path对象为字符串
            config_dict = self._convert_paths_to_strings(config_dict)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存桌面配置失败: {e}")
            return False
```

### 2. 语音识别服务

**文件**: `backend/core/speech_recognition.py`

```python
class SpeechRecognizer:
    """语音识别服务"""
    
    def __init__(self, config: SpeechRecognitionConfig):
        self.config = config
        self.recognizer = self._create_recognizer()
    
    def transcribe_audio(self, audio_path: str) -> str:
        """转写音频文件"""
        if self.config.provider == "whisper_local":
            return self._transcribe_with_whisper(audio_path)
        elif self.config.provider == "openai":
            return self._transcribe_with_openai(audio_path)
        # ... 其他服务
```

### 3. 性能优化

**文件**: `backend/utils/performance_config.py`

```python
class PerformanceConfig:
    """性能配置管理"""
    
    def __init__(self, level: str = "medium"):
        self.level = level
        self.settings = self._get_settings_for_level(level)
    
    def _get_settings_for_level(self, level: str) -> PerformanceSettings:
        """根据级别获取性能设置"""
        levels = {
            "low": PerformanceSettings(
                max_concurrent_tasks=1,
                chunk_size_mb=5,
                upload_timeout_seconds=300
            ),
            "medium": PerformanceSettings(
                max_concurrent_tasks=2,
                chunk_size_mb=10,
                upload_timeout_seconds=600
            ),
            "high": PerformanceSettings(
                max_concurrent_tasks=4,
                chunk_size_mb=20,
                upload_timeout_seconds=1200
            )
        }
        return levels.get(level, levels["medium"])
```

## 🔌 API接口

### 项目管理API

```python
# 创建项目
@router.post("/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    """创建新项目"""
    return await project_service.create_project(project)

# 获取项目列表
@router.get("/projects", response_model=List[ProjectResponse])
async def get_projects():
    """获取项目列表"""
    return await project_service.get_projects()

# 获取项目详情
@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: int):
    """获取项目详情"""
    return await project_service.get_project(project_id)
```

### 设置管理API

```python
# 更新设置
@router.put("/settings", response_model=SettingsResponse)
async def update_settings(settings: DesktopSettings):
    """更新应用设置"""
    config = get_desktop_config()
    config.settings = settings
    save_desktop_config(config)
    return SettingsResponse(success=True)

# 测试API连接
@router.post("/settings/test-api", response_model=ApiTestResponse)
async def test_api_connection(request: TestApiRequest):
    """测试API连接"""
    provider = create_llm_provider(request.provider, request.api_key)
    success = provider.test_connection()
    return ApiTestResponse(success=success)
```

## 🎨 前端开发

### 状态管理

**文件**: `frontend/src/store/useProjectStore.ts`

```typescript
interface ProjectStore {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  error: string | null
  
  // Actions
  fetchProjects: () => Promise<void>
  createProject: (project: ProjectCreate) => Promise<void>
  updateProject: (id: number, updates: Partial<Project>) => Promise<void>
  deleteProject: (id: number) => Promise<void>
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,
  
  fetchProjects: async () => {
    set({ loading: true, error: null })
    try {
      const projects = await projectApi.getProjects()
      set({ projects, loading: false })
    } catch (error) {
      set({ error: error.message, loading: false })
    }
  },
  
  // ... 其他actions
}))
```

### 自定义Hooks

**文件**: `frontend/src/hooks/useFirstRun.ts`

```typescript
export const useFirstRun = () => {
  const [isFirstRun, setIsFirstRun] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  
  const checkFirstRun = async () => {
    try {
      const config = await configApi.getConfig()
      const hasApiKey = !!(config.settings?.llm?.api_key)
      setIsFirstRun(!hasApiKey)
    } catch (error) {
      console.error('检查首次运行状态失败:', error)
      setIsFirstRun(true)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    checkFirstRun()
  }, [])
  
  return { isFirstRun, loading, refresh: checkFirstRun }
}
```

### 错误处理

**文件**: `frontend/src/utils/errorHandler.ts`

```typescript
class ErrorHandler {
  private static instance: ErrorHandler
  
  public static getInstance(): ErrorHandler {
    if (!ErrorHandler.instance) {
      ErrorHandler.instance = new ErrorHandler()
    }
    return ErrorHandler.instance
  }
  
  public handleError(error: any, category: ErrorCategory = 'SYSTEM', context?: string) {
    let errorMessage = '发生未知错误，请重试'
    let errorLevel: 'error' | 'warning' | 'info' = 'error'
    
    if (error.response) {
      // 处理HTTP错误
      errorMessage = error.response.data?.message || `服务器错误: ${error.response.status}`
      if (error.response.status === 429) {
        errorMessage = '系统正在处理其他项目，请稍后再试'
        errorLevel = 'warning'
      }
    } else if (error.request) {
      // 处理网络错误
      errorMessage = '网络连接失败，请检查网络或后端服务是否运行'
    } else if (error.message) {
      // 处理其他错误
      errorMessage = error.message
    }
    
    const finalMessage = context ? `[${context}] ${errorMessage}` : errorMessage
    console.error(`[${category} Error] ${finalMessage}`, error)
    
    if (errorLevel === 'warning') {
      message.warning(finalMessage)
    } else {
      message.error(finalMessage)
    }
  }
}
```

## 🐍 后端开发

### 服务管理

**文件**: `backend/desktop_main.py`

```python
class DesktopServiceManager:
    """桌面服务管理器"""
    
    def __init__(self, config: DesktopConfig):
        self.config = config
        self.is_running = False
        self.server_thread = None
        self.celery_worker_process = None
    
    def start(self):
        """启动所有服务"""
        if self.is_running:
            return
        
        try:
            # 启动FastAPI服务器
            self._start_fastapi_server()
            
            # 启动Celery Worker
            self._start_celery_worker()
            
            self.is_running = True
            self.start_time = time.time()
            logger.info("✅ 所有服务启动成功")
            
        except Exception as e:
            logger.error(f"❌ 服务启动失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止所有服务"""
        if not self.is_running:
            return
        
        try:
            # 停止Celery Worker进程
            if hasattr(self, 'celery_worker_process') and self.celery_worker_process:
                self.celery_worker_process.terminate()
                self.celery_worker_process.wait(timeout=5)
            
            # 停止FastAPI服务器
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
            
            self.is_running = False
            logger.info("✅ 服务已停止")
            
        except Exception as e:
            logger.error(f"❌ 停止服务失败: {e}")
```

### 任务处理

**文件**: `backend/tasks/video_tasks.py`

```python
@celery_app.task(bind=True)
def process_video_task(self, project_id: int, video_path: str):
    """处理视频任务"""
    try:
        # 更新任务状态
        self.update_state(state='PROGRESS', meta={'status': '开始处理视频'})
        
        # 提取音频
        audio_path = extract_audio(video_path)
        self.update_state(state='PROGRESS', meta={'status': '音频提取完成'})
        
        # 语音识别
        transcript = transcribe_audio(audio_path)
        self.update_state(state='PROGRESS', meta={'status': '语音识别完成'})
        
        # 生成切片
        clips = generate_clips(transcript, video_path)
        self.update_state(state='PROGRESS', meta={'status': '切片生成完成'})
        
        # 保存结果
        save_project_results(project_id, clips)
        
        return {'status': '处理完成', 'clips_count': len(clips)}
        
    except Exception as e:
        logger.error(f"视频处理失败: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
```

### 错误处理

**文件**: `backend/utils/error_handler.py`

```python
class AutoClipsException(Exception):
    """AutoClip自定义异常"""
    
    def __init__(self, 
                 message: str, 
                 category: ErrorCategory = ErrorCategory.SYSTEM,
                 error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
                 details: dict = None):
        self.message = message
        self.category = category
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

def handle_autoclips_exception(exc: AutoClipsException, request_id: str = None) -> JSONResponse:
    """处理AutoClip异常"""
    status_code = 500
    if exc.category == ErrorCategory.VALIDATION:
        status_code = 422
    elif exc.category == ErrorCategory.CONFIGURATION:
        status_code = 400
    elif exc.category == ErrorCategory.NETWORK:
        status_code = 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": exc.error_code.value,
            "message": exc.message,
            "details": exc.details,
            "request_id": request_id,
            "timestamp": time.time()
        }
    )
```

## 🦀 Tauri集成

### 命令定义

**文件**: `src-tauri/src/commands.rs`

```rust
#[tauri::command]
pub async fn start_backend_service(
    manager: State<'_, BackendManager>
) -> Result<BackendStatus, String> {
    match manager.start().await {
        Ok(_) => Ok(BackendStatus::Running),
        Err(e) => Err(format!("启动后端服务失败: {}", e)),
    }
}

#[tauri::command]
pub async fn stop_backend_service(
    manager: State<'_, BackendManager>
) -> Result<BackendStatus, String> {
    match manager.stop().await {
        Ok(_) => Ok(BackendStatus::Stopped),
        Err(e) => Err(format!("停止后端服务失败: {}", e)),
    }
}

#[tauri::command]
pub async fn get_service_status(
    manager: State<'_, BackendManager>
) -> Result<BackendStatus, String> {
    Ok(manager.get_status().await)
}
```

### 后端管理

**文件**: `src-tauri/src/backend_manager.rs`

```rust
pub struct BackendManager {
    status: BackendStatus,
    process: Option<Child>,
}

impl BackendManager {
    pub fn new() -> Self {
        Self {
            status: BackendStatus::Stopped,
            process: None,
        }
    }
    
    pub async fn start(&mut self) -> Result<(), String> {
        if self.status == BackendStatus::Running {
            return Ok(());
        }
        
        // 启动后端进程
        let mut cmd = Command::new("python")
            .arg("backend/desktop_main.py")
            .current_dir(std::env::current_dir().unwrap())
            .spawn()
            .map_err(|e| format!("启动后端进程失败: {}", e))?;
        
        self.process = Some(cmd);
        self.status = BackendStatus::Running;
        
        Ok(())
    }
    
    pub async fn stop(&mut self) -> Result<(), String> {
        if let Some(mut process) = self.process.take() {
            process.kill().map_err(|e| format!("停止后端进程失败: {}", e))?;
        }
        
        self.status = BackendStatus::Stopped;
        Ok(())
    }
}
```

### 系统托盘

**文件**: `src-tauri/src/tray.rs`

```rust
pub fn setup_system_tray(app_handle: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let tray_menu = MenuBuilder::new()
        .item(&MenuItem::new("显示主窗口", "show_main_window"))
        .separator()
        .item(&MenuItem::new("启动服务", "start_service"))
        .item(&MenuItem::new("停止服务", "stop_service"))
        .separator()
        .item(&MenuItem::new("退出", "quit_app"))
        .build()?;
    
    let _tray = TrayIconBuilder::new()
        .icon(app_handle.default_window_icon().unwrap().clone())
        .menu(&tray_menu)
        .on_menu_event(move |app, event| {
            match event.id.as_ref() {
                "show_main_window" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "start_service" => {
                    // 启动服务逻辑
                }
                "stop_service" => {
                    // 停止服务逻辑
                }
                "quit_app" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .build(app_handle)?;
    
    Ok(())
}
```

## 🏗️ 构建和部署

### 前端构建

```bash
# 开发环境
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview
```

### 后端构建

```bash
# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest

# 代码检查
flake8 backend/
black backend/
```

### Tauri构建

```bash
# 开发模式
npm run tauri dev

# 生产构建
npm run tauri build

# 构建特定平台
npm run tauri build -- --target x86_64-apple-darwin  # macOS Intel
npm run tauri build -- --target aarch64-apple-darwin # macOS ARM
npm run tauri build -- --target x86_64-pc-windows-msvc # Windows
npm run tauri build -- --target x86_64-unknown-linux-gnu # Linux
```

### 跨平台构建

```bash
# 构建所有平台
npm run build:all

# 构建特定平台
npm run build:macos
npm run build:windows
npm run build:linux
```

## 🧪 测试

### 前端测试

```bash
# 运行测试
npm test

# 运行测试并生成覆盖率报告
npm run test:coverage

# 运行E2E测试
npm run test:e2e
```

### 后端测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_project_service.py

# 运行测试并生成覆盖率报告
pytest --cov=backend tests/

# 运行性能测试
pytest tests/performance/
```

### 集成测试

```bash
# 启动测试环境
docker-compose -f docker-compose.test.yml up -d

# 运行集成测试
pytest tests/integration/

# 清理测试环境
docker-compose -f docker-compose.test.yml down
```

## 🤝 贡献指南

### 开发流程

1. **Fork项目**
   ```bash
   git clone https://github.com/your-username/autoclip-desktop.git
   cd autoclip-desktop
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **开发功能**
   - 编写代码
   - 添加测试
   - 更新文档

4. **提交代码**
   ```bash
   git add .
   git commit -m "feat: add your feature"
   git push origin feature/your-feature-name
   ```

5. **创建Pull Request**
   - 在GitHub上创建PR
   - 填写详细的描述
   - 等待代码审查

### 代码规范

#### 前端规范

- 使用TypeScript
- 遵循ESLint规则
- 使用Prettier格式化
- 组件使用函数式组件
- 使用Hooks进行状态管理

#### 后端规范

- 使用Python 3.9+
- 遵循PEP 8规范
- 使用类型注解
- 编写文档字符串
- 使用Pydantic进行数据验证

#### Rust规范

- 使用Rust 1.70+
- 遵循Clippy建议
- 使用rustfmt格式化
- 编写文档注释
- 使用Result处理错误

### 提交信息规范

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例**:
```
feat(api): add project creation endpoint

Add new API endpoint for creating projects with validation
and error handling.

Closes #123
```

### 测试要求

- 新功能必须包含测试
- 测试覆盖率不低于80%
- 所有测试必须通过
- 包含单元测试和集成测试

### 文档要求

- 更新相关文档
- 添加API文档
- 更新用户指南
- 添加代码注释

## 📚 相关资源

- [Tauri官方文档](https://tauri.app/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [React文档](https://react.dev/)
- [Ant Design文档](https://ant.design/)
- [Rust文档](https://doc.rust-lang.org/)

## 🆘 获取帮助

- **GitHub Issues**: 报告bug和功能请求
- **Discussions**: 技术讨论和问题解答
- **Discord**: 实时交流和协作
- **邮件**: 联系维护者

---

🎉 **感谢您的贡献！**
