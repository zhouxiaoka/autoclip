# 增强进度系统使用指南

## 📋 概述

本项目已实现增强的进度系统，提供统一的进度跟踪、状态管理和错误处理功能。该系统整合了Redis缓存、数据库持久化和内存缓存，确保进度信息的可靠性和实时性。

## 🏗️ 系统架构

### 进度阶段

```python
class ProgressStage(Enum):
    INGEST = "INGEST"          # 下载/就绪 (10%)
    SUBTITLE = "SUBTITLE"      # 字幕/对齐 (15%)
    ANALYZE = "ANALYZE"        # 语义分析/大纲 (20%)
    HIGHLIGHT = "HIGHLIGHT"    # 片段定位/打分 (25%)
    EXPORT = "EXPORT"          # 导出/封装 (20%)
    DONE = "DONE"              # 校验/归档 (10%)
    ERROR = "ERROR"            # 错误状态
```

### 进度状态

```python
class ProgressStatus(Enum):
    PENDING = "PENDING"        # 等待中
    RUNNING = "RUNNING"        # 运行中
    COMPLETED = "COMPLETED"    # 已完成
    FAILED = "FAILED"          # 失败
    CANCELLED = "CANCELLED"    # 已取消
```

### 存储层次

1. **内存缓存**: 快速访问，存储当前活跃的进度信息
2. **Redis缓存**: 分布式缓存，支持多实例共享
3. **数据库持久化**: 长期存储，与项目状态同步

## 🚀 使用方法

### 1. 基本进度跟踪

```python
from backend.services.enhanced_progress_service import (
    start_progress, update_progress, complete_progress, fail_progress,
    ProgressStage, ProgressStatus
)

# 开始进度跟踪
progress_info = start_progress(
    project_id="project_123",
    task_id="task_456",
    initial_message="开始处理视频"
)

# 更新进度
progress_info = update_progress(
    project_id="project_123",
    stage=ProgressStage.SUBTITLE,
    message="正在生成字幕",
    sub_progress=50.0  # 当前阶段50%完成
)

# 完成进度
progress_info = complete_progress(
    project_id="project_123",
    message="视频处理完成"
)

# 标记失败
progress_info = fail_progress(
    project_id="project_123",
    error_message="视频文件损坏"
)
```

### 2. 在服务中使用

```python
from backend.services.enhanced_progress_service import (
    progress_service, ProgressStage
)
from backend.core.error_middleware import handle_errors, ErrorCategory

class VideoProcessingService:
    
    @handle_errors(ErrorCategory.PROCESSING)
    async def process_video(self, project_id: str, video_path: str):
        try:
            # 开始进度跟踪
            progress_service.start_progress(
                project_id=project_id,
                initial_message="开始处理视频"
            )
            
            # 下载阶段
            progress_service.update_progress(
                project_id=project_id,
                stage=ProgressStage.INGEST,
                message="下载视频文件",
                sub_progress=100.0
            )
            
            # 字幕生成阶段
            progress_service.update_progress(
                project_id=project_id,
                stage=ProgressStage.SUBTITLE,
                message="生成字幕",
                sub_progress=0.0
            )
            
            # 模拟字幕生成过程
            for i in range(10):
                await asyncio.sleep(1)  # 模拟处理时间
                progress_service.update_progress(
                    project_id=project_id,
                    stage=ProgressStage.SUBTITLE,
                    message=f"字幕生成进度: {i*10}%",
                    sub_progress=i * 10.0
                )
            
            # 分析阶段
            progress_service.update_progress(
                project_id=project_id,
                stage=ProgressStage.ANALYZE,
                message="分析视频内容",
                sub_progress=0.0
            )
            
            # 继续其他阶段...
            
            # 完成处理
            progress_service.complete_progress(
                project_id=project_id,
                message="视频处理完成"
            )
            
        except Exception as e:
            # 标记失败
            progress_service.fail_progress(
                project_id=project_id,
                error_message=str(e)
            )
            raise
```

### 3. 在API中使用

```python
from fastapi import APIRouter, HTTPException
from backend.services.enhanced_progress_service import get_progress

router = APIRouter()

@router.get("/projects/{project_id}/progress")
async def get_project_progress(project_id: str):
    """获取项目进度"""
    try:
        progress_info = get_progress(project_id)
        if not progress_info:
            raise HTTPException(status_code=404, detail="项目进度不存在")
        
        return {
            "project_id": project_id,
            "progress": progress_info.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 4. 添加进度回调

```python
from backend.services.enhanced_progress_service import progress_service

def progress_callback(progress_info):
    """进度回调函数"""
    print(f"项目 {progress_info.project_id} 进度更新: {progress_info.progress}%")
    
    # 可以在这里添加其他逻辑，如：
    # - 发送通知
    # - 更新前端状态
    # - 记录日志
    # - 触发其他服务

# 注册回调
progress_service.add_progress_callback(progress_callback)
```

## 📊 进度信息结构

```python
@dataclass
class ProgressInfo:
    project_id: str                    # 项目ID
    task_id: Optional[str]             # 任务ID
    stage: ProgressStage               # 当前阶段
    status: ProgressStatus             # 状态
    progress: int                      # 总进度 (0-100)
    message: str                       # 当前消息
    error_message: Optional[str]       # 错误消息
    start_time: Optional[datetime]     # 开始时间
    end_time: Optional[datetime]       # 结束时间
    estimated_remaining: Optional[int] # 预估剩余时间(秒)
    metadata: Optional[Dict[str, Any]] # 元数据
```

### 进度计算规则

- **INGEST阶段**: 0-10%
- **SUBTITLE阶段**: 10-25%
- **ANALYZE阶段**: 25-45%
- **HIGHLIGHT阶段**: 45-70%
- **EXPORT阶段**: 70-90%
- **DONE阶段**: 100%

每个阶段内部可以通过`sub_progress`参数(0-100)来细分进度。

## 🔧 配置和优化

### 1. Redis配置

```python
# 在backend/core/unified_config.py中配置
redis:
  url: "redis://localhost:6379/0"
  max_connections: 10
  socket_timeout: 5
```

### 2. 清理配置

```python
# 定期清理旧进度信息
progress_service.cleanup_old_progress(max_age_hours=24)
```

### 3. 错误处理

```python
from backend.utils.error_handler import AutoClipsException, ErrorCategory

try:
    progress_service.update_progress(project_id, stage, message)
except AutoClipsException as e:
    if e.category == ErrorCategory.SYSTEM:
        # 系统错误，记录日志但不中断处理
        logger.error(f"进度更新失败: {e}")
    else:
        # 其他错误，重新抛出
        raise
```

## 📝 最佳实践

### 1. 进度消息编写

```python
# ✅ 好的进度消息
progress_service.update_progress(
    project_id=project_id,
    stage=ProgressStage.SUBTITLE,
    message="正在生成字幕，预计还需2分钟",
    sub_progress=60.0
)

# ❌ 不好的进度消息
progress_service.update_progress(
    project_id=project_id,
    stage=ProgressStage.SUBTITLE,
    message="处理中...",
    sub_progress=60.0
)
```

### 2. 错误处理

```python
# ✅ 完整的错误处理
try:
    # 处理逻辑
    result = await process_video(video_path)
    progress_service.complete_progress(project_id, "处理完成")
except Exception as e:
    # 记录详细错误信息
    error_message = f"处理失败: {str(e)}"
    progress_service.fail_progress(project_id, error_message)
    raise
```

### 3. 元数据使用

```python
# ✅ 使用元数据传递额外信息
progress_service.update_progress(
    project_id=project_id,
    stage=ProgressStage.ANALYZE,
    message="分析视频内容",
    metadata={
        "video_duration": 1200,  # 视频时长(秒)
        "analysis_method": "ai",  # 分析方法
        "estimated_clips": 5      # 预估切片数
    }
)
```

### 4. 性能优化

```python
# ✅ 批量更新进度
for i, item in enumerate(items):
    if i % 10 == 0:  # 每10个项目更新一次进度
        progress_service.update_progress(
            project_id=project_id,
            stage=ProgressStage.PROCESSING,
            message=f"处理进度: {i}/{len(items)}",
            sub_progress=i / len(items) * 100
        )
```

## 🧪 测试进度系统

### 1. 单元测试

```python
import pytest
from backend.services.enhanced_progress_service import (
    start_progress, update_progress, complete_progress,
    ProgressStage, ProgressStatus
)

def test_progress_tracking():
    project_id = "test_project"
    
    # 开始进度
    progress = start_progress(project_id, initial_message="开始测试")
    assert progress.project_id == project_id
    assert progress.status == ProgressStatus.RUNNING
    assert progress.progress == 0
    
    # 更新进度
    progress = update_progress(
        project_id=project_id,
        stage=ProgressStage.SUBTITLE,
        message="测试字幕生成",
        sub_progress=50.0
    )
    assert progress.stage == ProgressStage.SUBTITLE
    assert progress.progress > 0
    
    # 完成进度
    progress = complete_progress(project_id, "测试完成")
    assert progress.status == ProgressStatus.COMPLETED
    assert progress.progress == 100
```

### 2. 集成测试

```python
async def test_progress_integration():
    project_id = "integration_test"
    
    # 模拟完整的处理流程
    start_progress(project_id, "开始集成测试")
    
    for stage in [ProgressStage.INGEST, ProgressStage.SUBTITLE, 
                  ProgressStage.ANALYZE, ProgressStage.HIGHLIGHT, 
                  ProgressStage.EXPORT]:
        update_progress(project_id, stage, f"测试{stage.value}阶段")
        await asyncio.sleep(0.1)  # 模拟处理时间
    
    complete_progress(project_id, "集成测试完成")
    
    # 验证最终状态
    final_progress = get_progress(project_id)
    assert final_progress.status == ProgressStatus.COMPLETED
    assert final_progress.progress == 100
```

## 🔍 监控和调试

### 1. 进度监控

```python
# 获取所有活跃进度
active_progress = progress_service.get_all_active_progress()
for progress in active_progress:
    print(f"项目 {progress.project_id}: {progress.progress}% - {progress.message}")
```

### 2. 调试信息

```python
# 获取详细进度信息
progress_info = get_progress(project_id)
if progress_info:
    print(f"项目ID: {progress_info.project_id}")
    print(f"当前阶段: {progress_info.stage.value}")
    print(f"总进度: {progress_info.progress}%")
    print(f"状态: {progress_info.status.value}")
    print(f"消息: {progress_info.message}")
    print(f"开始时间: {progress_info.start_time}")
    print(f"预估剩余: {progress_info.estimated_remaining}秒")
    if progress_info.metadata:
        print(f"元数据: {progress_info.metadata}")
```

### 3. 日志记录

```python
import logging

# 配置进度日志
progress_logger = logging.getLogger('progress')
progress_logger.setLevel(logging.INFO)

def progress_log_callback(progress_info):
    progress_logger.info(
        f"项目 {progress_info.project_id} 进度更新: "
        f"{progress_info.progress}% - {progress_info.message}"
    )

progress_service.add_progress_callback(progress_log_callback)
```

## 🚨 常见问题

### 1. Redis连接失败

```python
# 系统会自动降级到内存缓存
# 检查Redis配置和连接
if not progress_service.redis_client:
    logger.warning("Redis不可用，使用内存缓存")
```

### 2. 进度信息丢失

```python
# 定期清理可能导致进度信息丢失
# 建议设置合理的清理时间
progress_service.cleanup_old_progress(max_age_hours=48)  # 48小时
```

### 3. 进度更新频率过高

```python
# 系统内置了节流机制，避免频繁更新
# 建议在循环中控制更新频率
for i, item in enumerate(items):
    if i % 10 == 0:  # 每10次更新一次
        update_progress(project_id, stage, message, i/len(items)*100)
```

## 📚 相关文档

- [错误处理指南](./ERROR_HANDLING_GUIDE.md)
- [配置管理指南](./CONFIGURATION_GUIDE.md)
- [API文档](./API_DOCUMENTATION.md)
