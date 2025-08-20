# 存储优化工作拆解

## 总体目标
将当前的双重存储架构（文件系统+数据库）优化为分离存储架构（数据库存储元数据+文件系统存储实际文件），避免数据冗余，提升系统性能。

## 工作拆解

### 第一阶段：数据库模型优化 (2-3天)

#### 1.1 优化Clip模型 (0.5天)
**当前问题：**
- `processing_result` 字段存储了完整的处理结果数据
- `clip_metadata` 字段可能包含冗余信息

**需要修改：**
```python
# backend/models/clip.py
class Clip(BaseModel):
    # 移除冗余字段
    # processing_result = Column(JSON, nullable=True, comment="处理结果数据")  # 删除
    
    # 优化文件路径字段
    video_path = Column(String(500), nullable=True, comment="切片视频文件路径")
    thumbnail_path = Column(String(500), nullable=True, comment="缩略图文件路径")
    
    # 保留必要的元数据
    clip_metadata = Column(JSON, nullable=True, comment="切片元数据（精简版）")
```

**具体工作：**
- [ ] 分析 `processing_result` 字段的使用情况
- [ ] 确定哪些数据需要保留在数据库，哪些移到文件系统
- [ ] 修改Clip模型，移除冗余字段
- [ ] 创建数据库迁移脚本

#### 1.2 优化Project模型 (0.5天)
**当前问题：**
- `project_metadata` 字段可能包含大量文件系统数据

**需要修改：**
```python
# backend/models/project.py
class Project(BaseModel):
    # 添加文件路径引用字段
    video_path = Column(String(500), nullable=True, comment="视频文件路径")
    subtitle_path = Column(String(500), nullable=True, comment="字幕文件路径")
    
    # 优化元数据字段
    project_metadata = Column(JSON, nullable=True, comment="项目元数据（精简版）")
```

**具体工作：**
- [ ] 分析 `project_metadata` 字段的内容
- [ ] 添加文件路径引用字段
- [ ] 优化元数据存储结构
- [ ] 创建数据库迁移脚本

#### 1.3 优化Collection模型 (0.5天)
**当前问题：**
- `collection_metadata` 字段可能包含冗余数据

**需要修改：**
```python
# backend/models/collection.py
class Collection(BaseModel):
    # 添加文件路径引用字段
    export_path = Column(String(500), nullable=True, comment="合集导出文件路径")
    
    # 优化元数据字段
    collection_metadata = Column(JSON, nullable=True, comment="合集元数据（精简版）")
```

**具体工作：**
- [ ] 分析 `collection_metadata` 字段的内容
- [ ] 添加文件路径引用字段
- [ ] 优化元数据存储结构
- [ ] 创建数据库迁移脚本

#### 1.4 创建数据库迁移 (1天)
**具体工作：**
- [ ] 创建Alembic迁移脚本
- [ ] 测试迁移脚本
- [ ] 备份现有数据
- [ ] 执行迁移
- [ ] 验证数据完整性

### 第二阶段：存储服务重构 (3-4天)

#### 2.1 完善StorageService (1天)
**当前状态：**
- 已创建基础的StorageService
- 需要完善文件管理功能

**需要完善的功能：**
```python
# backend/services/storage_service.py
class StorageService:
    def save_processing_result(self, step: str, result: Dict[str, Any]) -> str:
        """保存处理结果到文件系统"""
        
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """保存切片文件并返回路径"""
        
    def save_collection_file(self, collection_data: Dict[str, Any], collection_id: str) -> str:
        """保存合集文件并返回路径"""
        
    def get_file_content(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件内容"""
        
    def cleanup_old_files(self, project_id: str, keep_days: int = 30):
        """清理旧文件"""
```

**具体工作：**
- [ ] 完善文件保存功能
- [ ] 添加文件读取功能
- [ ] 添加文件清理功能
- [ ] 添加错误处理
- [ ] 添加日志记录

#### 2.2 重构PipelineAdapter (1天)
**当前问题：**
- `_save_clips_to_database` 方法存储了完整的数据
- `_save_collections_to_database` 方法存储了完整的数据

**需要修改：**
```python
# backend/services/pipeline_adapter.py
class PipelineAdapter:
    def _save_clips_to_database(self, project_id: str, clips_file: Path):
        """将切片数据保存到数据库（只保存元数据）"""
        # 1. 读取切片数据
        # 2. 保存切片文件到文件系统
        # 3. 保存元数据到数据库（只保存路径引用）
        
    def _save_collections_to_database(self, project_id: str, collections_file: Path):
        """将合集数据保存到数据库（只保存元数据）"""
        # 1. 读取合集数据
        # 2. 保存合集文件到文件系统
        # 3. 保存元数据到数据库（只保存路径引用）
```

**具体工作：**
- [ ] 分析当前的保存逻辑
- [ ] 重构为分离存储模式
- [ ] 集成StorageService
- [ ] 测试新的保存逻辑

#### 2.3 重构Repository层 (1天)
**需要修改的Repository：**
- `ClipRepository`
- `CollectionRepository`
- `ProjectRepository`

**具体工作：**
```python
# backend/repositories/clip_repository.py
class ClipRepository(BaseRepository[Clip]):
    def create_clip(self, clip_data: Dict[str, Any]) -> Clip:
        """创建切片记录（分离存储）"""
        # 1. 保存切片文件到文件系统
        # 2. 保存元数据到数据库
        
    def get_clip_file(self, clip_id: str) -> Optional[Path]:
        """获取切片文件路径"""
        
    def get_clip_content(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """获取切片完整内容"""
```

**具体工作：**
- [ ] 重构ClipRepository
- [ ] 重构CollectionRepository
- [ ] 重构ProjectRepository
- [ ] 添加文件访问方法
- [ ] 测试Repository功能

#### 2.4 优化Service层 (0.5天)
**需要修改的Service：**
- `ClipService`
- `CollectionService`
- `ProjectService`

**具体工作：**
- [ ] 更新Service层以使用新的存储模式
- [ ] 添加文件访问接口
- [ ] 优化数据返回格式
- [ ] 测试Service功能

### 第三阶段：API层优化 (2天)

#### 3.1 优化文件上传API (0.5天)
**当前问题：**
- 文件上传后可能存储了冗余数据

**需要修改：**
```python
# backend/api/v1/files.py
@router.post("/upload")
async def upload_files(
    files: List[UploadFile],
    project_id: str,
    db: Session = Depends(get_db)
):
    """上传文件（优化存储）"""
    # 1. 保存文件到文件系统
    # 2. 更新数据库中的文件路径
    # 3. 不存储文件内容到数据库
```

**具体工作：**
- [ ] 分析当前的文件上传逻辑
- [ ] 优化为只保存文件路径
- [ ] 添加文件验证
- [ ] 测试上传功能

#### 3.2 优化数据返回API (0.5天)
**需要修改的API：**
- `/api/v1/clips/` - 切片数据API
- `/api/v1/collections/` - 合集数据API
- `/api/v1/projects/` - 项目数据API

**具体工作：**
```python
# backend/api/v1/clips.py
@router.get("/")
async def get_clips(
    project_id: str = Query(None),
    db: Session = Depends(get_db)
):
    """获取切片列表（优化数据返回）"""
    # 1. 从数据库获取元数据
    # 2. 根据需要从文件系统获取完整数据
    # 3. 返回优化后的数据格式
```

**具体工作：**
- [ ] 分析当前的数据返回逻辑
- [ ] 优化为按需加载完整数据
- [ ] 添加数据缓存机制
- [ ] 测试API功能

#### 3.3 添加文件访问API (0.5天)
**需要新增的API：**
```python
# backend/api/v1/files.py
@router.get("/clips/{clip_id}/content")
async def get_clip_content(clip_id: str, db: Session = Depends(get_db)):
    """获取切片完整内容"""
    
@router.get("/collections/{collection_id}/content")
async def get_collection_content(collection_id: str, db: Session = Depends(get_db)):
    """获取合集完整内容"""
```

**具体工作：**
- [ ] 创建文件内容访问API
- [ ] 添加访问权限控制
- [ ] 添加缓存机制
- [ ] 测试API功能

#### 3.4 优化前端API调用 (0.5天)
**需要修改的前端代码：**
- `frontend/src/services/api.ts`
- 相关的React组件

**具体工作：**
- [ ] 分析当前的前端API调用
- [ ] 优化为按需加载数据
- [ ] 添加数据缓存
- [ ] 测试前端功能

### 第四阶段：数据迁移 (1天)

#### 4.1 创建数据迁移脚本 (0.5天)
**具体工作：**
```python
# scripts/migrate_to_optimized_storage.py
def migrate_clips_data():
    """迁移切片数据"""
    # 1. 读取数据库中的完整数据
    # 2. 保存到文件系统
    # 3. 更新数据库为只保存路径引用
    
def migrate_collections_data():
    """迁移合集数据"""
    # 1. 读取数据库中的完整数据
    # 2. 保存到文件系统
    # 3. 更新数据库为只保存路径引用
```

**具体工作：**
- [ ] 创建数据迁移脚本
- [ ] 添加数据验证
- [ ] 添加回滚机制
- [ ] 测试迁移脚本

#### 4.2 执行数据迁移 (0.5天)
**具体工作：**
- [ ] 备份现有数据
- [ ] 执行迁移脚本
- [ ] 验证数据完整性
- [ ] 清理冗余数据

### 第五阶段：测试和优化 (1-2天)

#### 5.1 功能测试 (0.5天)
**测试内容：**
- [ ] 文件上传功能
- [ ] 数据处理功能
- [ ] 数据查询功能
- [ ] 文件访问功能

#### 5.2 性能测试 (0.5天)
**测试内容：**
- [ ] 存储空间使用情况
- [ ] 数据访问性能
- [ ] 系统响应时间
- [ ] 并发处理能力

#### 5.3 优化调整 (0.5天)
**优化内容：**
- [ ] 根据测试结果调整配置
- [ ] 优化缓存策略
- [ ] 优化文件组织
- [ ] 优化错误处理

## 时间安排

| 阶段 | 工作内容 | 预计时间 | 负责人 |
|------|----------|----------|--------|
| 第一阶段 | 数据库模型优化 | 2-3天 | 后端开发 |
| 第二阶段 | 存储服务重构 | 3-4天 | 后端开发 |
| 第三阶段 | API层优化 | 2天 | 后端开发 |
| 第四阶段 | 数据迁移 | 1天 | 后端开发 |
| 第五阶段 | 测试和优化 | 1-2天 | 全栈开发 |

**总计：9-12天**

## 风险评估

### 高风险项
1. **数据迁移风险**
   - 风险：数据丢失或损坏
   - 缓解：充分备份，分步迁移，回滚机制

2. **API兼容性风险**
   - 风险：前端功能受影响
   - 缓解：保持API接口兼容，渐进式迁移

3. **性能风险**
   - 风险：文件访问性能下降
   - 缓解：添加缓存机制，优化文件组织

### 中风险项
1. **代码复杂度增加**
   - 风险：维护难度增加
   - 缓解：良好的代码组织，完善的文档

2. **测试覆盖不足**
   - 风险：功能缺陷
   - 缓解：全面的测试用例，自动化测试

## 成功标准

### 功能标准
- [ ] 所有现有功能正常工作
- [ ] 数据完整性得到保证
- [ ] 文件访问功能正常
- [ ] API接口保持兼容

### 性能标准
- [ ] 存储空间使用减少10%以上
- [ ] 数据访问性能不降低
- [ ] 系统响应时间保持稳定
- [ ] 并发处理能力保持稳定

### 质量标准
- [ ] 代码覆盖率不低于80%
- [ ] 无严重bug
- [ ] 文档完整
- [ ] 测试通过率100%

## 后续维护

### 监控指标
- 存储空间使用情况
- 文件访问性能
- 数据一致性
- 错误率

### 维护任务
- 定期清理临时文件
- 监控存储空间使用
- 优化文件组织
- 更新文档

这个工作拆解涵盖了从数据库模型优化到最终测试的完整流程，确保存储优化能够顺利实施。
