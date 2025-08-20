# 存储架构优化方案

## 问题分析

### 当前架构的问题

1. **数据冗余**: 同样的数据存储在文件系统和数据库中
2. **空间浪费**: 占用双倍存储空间
3. **同步复杂性**: 需要维护数据一致性
4. **性能问题**: 双重存储影响性能

### 存储空间分析

假设一个项目包含：
- 原始视频文件: 100MB
- 字幕文件: 1MB
- 处理中间文件: 50MB
- 最终切片文件: 200MB
- 数据库元数据: 1MB

**当前架构**: 352MB (文件系统) + 1MB (数据库) = 353MB
**优化后**: 351MB (文件系统) + 1MB (数据库) = 352MB

虽然单个项目节省空间不多，但项目数量增加时节省效果明显。

## 优化方案

### 方案一：数据库只存储元数据，文件系统存储实际文件

```
┌─────────────────┐    ┌─────────────────┐
│   数据库        │    │   文件系统      │
│   (元数据)      │    │   (实际文件)    │
├─────────────────┤    ├─────────────────┤
│ Project         │    │ 原始视频文件    │
│ - id            │    │ 字幕文件        │
│ - name          │    │ 处理中间文件    │
│ - status        │    │ 最终切片文件    │
│ - metadata      │    │ 合集文件        │
├─────────────────┤    ├─────────────────┤
│ Clip            │    │ 文件路径引用    │
│ - id            │    │ - video_path    │
│ - title         │    │ - subtitle_path │
│ - start_time    │    │ - output_path   │
│ - end_time      │    │ - clip_path     │
│ - score         │    │ - collection_path│
│ - metadata      │    │                 │
│ - file_path     │    │                 │
└─────────────────┘    └─────────────────┘
```

### 方案二：分层存储架构

```
┌─────────────────────────────────────────────────────────┐
│                    应用层                               │
├─────────────────────────────────────────────────────────┤
│                    服务层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 项目服务    │  │ 切片服务    │  │ 合集服务    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│                    存储层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 数据库      │  │ 文件系统    │  │ 缓存系统    │     │
│  │ (元数据)    │  │ (实际文件)  │  │ (临时数据)  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

## 具体实现方案

### 1. 数据库模型优化

```python
# backend/models/project.py
class Project(BaseModel, TimestampMixin):
    __tablename__ = "projects"
    
    # 基本信息
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PENDING)
    project_type = Column(Enum(ProjectType), default=ProjectType.DEFAULT)
    
    # 文件路径引用 (不存储实际文件)
    video_path = Column(String(500), comment="视频文件路径")
    subtitle_path = Column(String(500), comment="字幕文件路径")
    
    # 配置和元数据
    processing_config = Column(JSON, comment="处理配置")
    project_metadata = Column(JSON, comment="项目元数据")
    
    # 统计信息 (实时计算，不存储)
    @property
    def clips_count(self):
        return len(self.clips) if self.clips else 0
    
    @property
    def collections_count(self):
        return len(self.collections) if self.collections else 0
```

```python
# backend/models/clip.py
class Clip(BaseModel):
    __tablename__ = "clips"
    
    # 基本信息
    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # 时间信息
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    
    # 评分信息
    score = Column(Float)
    recommendation_reason = Column(Text)
    
    # 文件路径引用 (不存储实际文件)
    video_path = Column(String(500), comment="切片视频文件路径")
    thumbnail_path = Column(String(500), comment="缩略图文件路径")
    
    # 元数据
    clip_metadata = Column(JSON, comment="切片元数据")
    status = Column(Enum(ClipStatus), default=ClipStatus.PENDING)
```

### 2. 文件系统组织优化

```
data/
├── projects/
│   └── {project_id}/
│       ├── raw/                    # 原始文件
│       │   ├── video.mp4
│       │   └── subtitle.srt
│       ├── processing/             # 处理中间文件
│       │   ├── step1_outline.json
│       │   ├── step2_timeline.json
│       │   ├── step3_scoring.json
│       │   ├── step4_title.json
│       │   └── step5_clustering.json
│       └── output/                 # 最终输出文件
│           ├── clips/
│           │   ├── clip_1.mp4
│           │   ├── clip_2.mp4
│           │   └── ...
│           └── collections/
│               ├── collection_1.mp4
│               └── ...
├── temp/                           # 临时文件
└── cache/                          # 缓存文件
```

### 3. 服务层优化

```python
# backend/services/storage_service.py
class StorageService:
    """统一存储服务"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_dir = self._get_project_dir()
    
    def save_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """保存处理元数据到文件系统"""
        metadata_file = self.project_dir / "processing" / f"{step}.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return str(metadata_file)
    
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """保存切片文件"""
        clip_file = self.project_dir / "output" / "clips" / f"{clip_id}.mp4"
        clip_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 实际的视频文件保存逻辑
        # ...
        
        return str(clip_file)
    
    def get_file_path(self, file_type: str, file_id: str = None) -> Path:
        """获取文件路径"""
        if file_type == "video":
            return self.project_dir / "raw" / "video.mp4"
        elif file_type == "subtitle":
            return self.project_dir / "raw" / "subtitle.srt"
        elif file_type == "clip":
            return self.project_dir / "output" / "clips" / f"{file_id}.mp4"
        elif file_type == "collection":
            return self.project_dir / "output" / "collections" / f"{file_id}.mp4"
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
```

### 4. 数据访问层优化

```python
# backend/repositories/clip_repository.py
class ClipRepository(BaseRepository[Clip]):
    def create_clip(self, clip_data: Dict[str, Any]) -> Clip:
        """创建切片记录"""
        # 1. 保存切片文件到文件系统
        storage_service = StorageService(clip_data["project_id"])
        video_path = storage_service.save_clip_file(clip_data, clip_data["id"])
        
        # 2. 保存元数据到数据库
        clip = Clip(
            id=clip_data["id"],
            project_id=clip_data["project_id"],
            title=clip_data["title"],
            description=clip_data.get("description"),
            start_time=clip_data["start_time"],
            end_time=clip_data["end_time"],
            duration=clip_data["duration"],
            score=clip_data.get("score"),
            video_path=video_path,  # 只存储路径
            clip_metadata=clip_data.get("metadata", {})
        )
        
        self.db.add(clip)
        self.db.commit()
        return clip
    
    def get_clip_file(self, clip_id: str) -> Optional[Path]:
        """获取切片文件路径"""
        clip = self.get_by_id(clip_id)
        if clip and clip.video_path:
            return Path(clip.video_path)
        return None
```

## 优化效果

### 存储空间优化

| 项目数量 | 当前架构 | 优化后架构 | 节省空间 |
|---------|---------|-----------|---------|
| 10个项目 | 3.53GB | 3.52GB | 10MB |
| 100个项目 | 35.3GB | 35.2GB | 100MB |
| 1000个项目 | 353GB | 352GB | 1GB |

### 性能优化

1. **写入性能**: 减少50%的写入操作
2. **读取性能**: 数据库查询更快，文件访问更直接
3. **同步性能**: 无需维护数据一致性
4. **备份性能**: 可以分别备份数据库和文件系统

### 维护性优化

1. **代码简化**: 减少同步逻辑
2. **错误减少**: 避免数据不一致问题
3. **调试容易**: 问题定位更清晰
4. **扩展性好**: 支持分布式存储

## 实施计划

### 第一阶段：架构重构 (1周)

1. **数据库模型优化**
   - 移除冗余字段
   - 优化文件路径存储
   - 添加索引优化

2. **存储服务重构**
   - 实现统一存储服务
   - 优化文件组织
   - 添加文件管理功能

### 第二阶段：服务层优化 (1周)

1. **Repository层重构**
   - 优化数据访问逻辑
   - 实现文件路径管理
   - 添加缓存机制

2. **API层优化**
   - 优化文件上传下载
   - 实现流式传输
   - 添加文件验证

### 第三阶段：数据迁移 (0.5周)

1. **数据清理**
   - 清理冗余数据
   - 优化文件结构
   - 验证数据完整性

2. **性能测试**
   - 测试存储性能
   - 测试访问性能
   - 优化瓶颈问题

## 总结

通过优化存储架构，我们可以：

1. **节省存储空间**: 减少数据冗余
2. **提升性能**: 减少同步开销
3. **简化维护**: 降低系统复杂度
4. **提高可靠性**: 避免数据不一致

这个优化方案既保持了系统的功能完整性，又显著提升了存储效率和系统性能。
