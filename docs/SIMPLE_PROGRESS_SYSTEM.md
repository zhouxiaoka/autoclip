# 简化进度系统实现指南

## 概述

这是一个基于"做笨做稳"理念的简化进度同步系统，使用固定阶段 + 固定权重来驱动进度，不再依赖复杂的订阅机制。

## 核心特性

- **固定阶段**: 6个预定义阶段，每个阶段有固定权重
- **简单轮询**: 前端通过HTTP API轮询获取进度，无需WebSocket
- **Redis存储**: 后端使用Redis存储进度快照，支持持久化
- **极简事件**: 每个阶段切换时发送一次事件，最多6次

## 系统架构

### 后端组件

1. **`backend/services/simple_progress.py`** - 核心进度服务
   - 阶段定义和权重计算
   - Redis存储和事件发布
   - 进度快照管理

2. **`backend/api/v1/simple_progress.py`** - API接口
   - `/api/v1/simple-progress/snapshot` - 批量获取进度快照
   - `/api/v1/simple-progress/snapshot/{project_id}` - 单个项目进度
   - `/api/v1/simple-progress/stages` - 获取阶段配置

3. **`backend/services/simple_pipeline_adapter.py`** - 流水线适配器
   - 集成进度上报到现有流水线
   - 自动发送阶段切换事件

### 前端组件

1. **`frontend/src/stores/useSimpleProgressStore.ts`** - 状态管理
   - Zustand状态管理
   - 轮询控制
   - 进度数据缓存

2. **`frontend/src/components/SimpleProgressBar.tsx`** - 进度条组件
   - 单个项目进度显示
   - 批量项目进度显示
   - 自动轮询集成

3. **`frontend/src/components/SimpleProjectCard.tsx`** - 项目卡片
   - 集成进度显示
   - 状态管理
   - 操作按钮

## 阶段定义

```python
STAGES = [
    ("INGEST", 10),        # 下载/就绪
    ("SUBTITLE", 15),      # 字幕/对齐  
    ("ANALYZE", 20),       # 语义分析/大纲
    ("HIGHLIGHT", 25),     # 片段定位/打分
    ("EXPORT", 20),        # 导出/封装
    ("DONE", 10),          # 校验/归档
]
```

## 进度计算

```python
def compute_percent(stage: str, subpercent: Optional[float] = None) -> int:
    # 累加之前阶段权重
    done = 0
    for s in ORDER:
        if s == stage:
            break
        done += WEIGHTS[s]
    
    # 当前阶段
    cur = WEIGHTS.get(stage, 0)
    
    if subpercent is None:
        return min(100, done + cur) if stage == "DONE" else min(99, done)
    else:
        return min(99, done + int(cur * subpercent / 100))
```

## 事件格式

```json
{
  "project_id": "46ab50a6-....",
  "stage": "HIGHLIGHT", 
  "percent": 70,
  "message": "已完成片段定位，共 12 段候选",
  "ts": 1640995200
}
```

## 使用方法

### 后端集成

1. **在流水线中发送进度事件**:
```python
from backend.services.simple_progress import emit_progress

# 阶段切换
emit_progress(project_id, "ANALYZE", "开始内容分析")

# 带子进度
emit_progress(project_id, "ANALYZE", "分析中(50%)", subpercent=50)
```

2. **使用简化的流水线适配器**:
```python
from backend.services.simple_pipeline_adapter import create_simple_pipeline_adapter

adapter = create_simple_pipeline_adapter(project_id, task_id)
result = adapter.process_project_sync(video_path, srt_path)
```

### 前端集成

1. **使用进度状态管理**:
```typescript
import { useSimpleProgressStore } from '../stores/useSimpleProgressStore'

const { startPolling, stopPolling, getProgress } = useSimpleProgressStore()

// 开始轮询
startPolling(['project-1', 'project-2'], 2000)

// 获取进度
const progress = getProgress('project-1')
```

2. **使用进度条组件**:
```tsx
import { SimpleProgressBar } from '../components/SimpleProgressBar'

<SimpleProgressBar
  projectId="project-1"
  autoStart={true}
  pollingInterval={2000}
  showDetails={true}
  onProgressUpdate={(progress) => console.log(progress)}
/>
```

3. **使用项目卡片组件**:
```tsx
import { SimpleProjectCard } from '../components/SimpleProjectCard'

<SimpleProjectCard
  project={project}
  onStartProcessing={handleStart}
  onViewDetails={handleView}
  onDelete={handleDelete}
  onRetry={handleRetry}
/>
```

## API接口

### 获取进度快照

```bash
# 批量获取
GET /api/v1/simple-progress/snapshot?project_ids=project-1&project_ids=project-2

# 单个获取
GET /api/v1/simple-progress/snapshot/project-1
```

### 获取阶段配置

```bash
GET /api/v1/simple-progress/stages
```

## 配置选项

### 轮询间隔
- 默认: 2000ms (2秒)
- 建议范围: 1000-5000ms
- 可根据网络状况调整

### 阶段权重
- 总权重: 100
- 可调整各阶段权重以适应实际处理时间
- 权重分配应考虑各阶段的实际耗时

## 故障处理

### Redis连接失败
- 系统会记录警告日志
- 进度事件发送会被跳过
- 前端轮询会返回空数据

### 网络中断
- 前端轮询会自动重试
- 进度数据会缓存在本地状态
- 网络恢复后自动同步

### 阶段异常
- 支持失败状态检测
- 自动标记为失败状态
- 提供重试机制

## 性能优化

1. **批量轮询**: 一次请求获取多个项目进度
2. **智能缓存**: 避免重复请求相同数据
3. **条件轮询**: 只在需要时启动轮询
4. **自动清理**: 定期清理过期进度数据

## 扩展性

1. **新增阶段**: 修改STAGES配置即可
2. **调整权重**: 重新分配各阶段权重
3. **自定义消息**: 支持阶段特定的消息格式
4. **多环境支持**: 通过配置支持不同环境

## 监控和调试

1. **日志记录**: 详细的进度事件日志
2. **状态检查**: 实时进度状态查询
3. **错误追踪**: 完整的错误信息记录
4. **性能指标**: 轮询频率和响应时间监控

## 迁移指南

从旧的复杂进度系统迁移到简化系统：

1. **后端迁移**:
   - 替换进度回调为emit_progress调用
   - 使用SimplePipelineAdapter替换旧适配器
   - 移除复杂的WebSocket进度发布

2. **前端迁移**:
   - 使用useSimpleProgressStore替换旧状态管理
   - 使用SimpleProgressBar替换旧进度组件
   - 配置轮询替代WebSocket订阅

3. **数据迁移**:
   - 清理旧的进度数据
   - 初始化新的Redis进度存储
   - 更新项目状态映射

## 总结

这个简化进度系统通过"做笨做稳"的设计理念，提供了：

- ✅ **可靠性**: 基于HTTP轮询，不依赖WebSocket
- ✅ **简单性**: 固定阶段，易于理解和维护
- ✅ **性能**: 最小化网络请求，智能缓存
- ✅ **扩展性**: 易于添加新阶段和功能
- ✅ **调试性**: 完整的日志和状态追踪

相比之前的复杂系统，这个方案更加稳定可靠，易于维护和扩展。
