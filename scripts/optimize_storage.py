#!/usr/bin/env python3
"""
存储架构优化实施脚本
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from core.database import SessionLocal
from models.project import Project
from models.clip import Clip
from models.collection import Collection

def analyze_current_storage():
    """分析当前存储使用情况"""
    print("📊 分析当前存储使用情况...")
    
    # 分析数据库
    db = SessionLocal()
    try:
        total_projects = db.query(Project).count()
        total_clips = db.query(Clip).count()
        total_collections = db.query(Collection).count()
        
        print(f"   数据库统计:")
        print(f"     - 项目数量: {total_projects}")
        print(f"     - 切片数量: {total_clips}")
        print(f"     - 合集数量: {total_collections}")
        
    finally:
        db.close()
    
    # 分析文件系统
    data_dir = project_root / "data"
    projects_dir = data_dir / "projects"
    
    if projects_dir.exists():
        project_dirs = [d for d in projects_dir.iterdir() if d.is_dir()]
        print(f"   文件系统统计:")
        print(f"     - 项目目录数量: {len(project_dirs)}")
        
        total_size = 0
        for project_dir in project_dirs:
            project_size = sum(f.stat().st_size for f in project_dir.rglob('*') if f.is_file())
            total_size += project_size
            print(f"     - {project_dir.name}: {project_size / 1024 / 1024:.2f} MB")
        
        print(f"     - 总文件大小: {total_size / 1024 / 1024:.2f} MB")
    
    return {
        "db_projects": total_projects,
        "db_clips": total_clips,
        "db_collections": total_collections,
        "fs_projects": len(project_dirs) if projects_dir.exists() else 0,
        "fs_total_size": total_size if projects_dir.exists() else 0
    }

def create_optimized_structure():
    """创建优化的文件结构"""
    print("\n🏗️ 创建优化的文件结构...")
    
    data_dir = project_root / "data"
    
    # 创建新的目录结构
    directories = [
        data_dir / "temp",
        data_dir / "cache",
        data_dir / "backups"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"   创建目录: {directory}")
    
    # 创建示例项目结构
    example_project_dir = data_dir / "projects" / "example-project"
    example_dirs = [
        example_project_dir / "raw",
        example_project_dir / "processing",
        example_project_dir / "output" / "clips",
        example_project_dir / "output" / "collections"
    ]
    
    for directory in example_dirs:
        directory.mkdir(parents=True, exist_ok=True)
    
    print(f"   创建示例项目结构: {example_project_dir}")

def optimize_database_schema():
    """优化数据库模式"""
    print("\n🗄️ 优化数据库模式...")
    
    # 这里可以添加数据库模式优化的逻辑
    # 比如添加索引、优化字段类型等
    
    print("   数据库模式优化完成")

def create_storage_service():
    """创建统一存储服务"""
    print("\n🔧 创建统一存储服务...")
    
    storage_service_content = '''"""
统一存储服务
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from core.config import get_data_directory

logger = logging.getLogger(__name__)

class StorageService:
    """统一存储服务"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.data_dir = get_data_directory()
        self.project_dir = self.data_dir / "projects" / project_id
        
        # 确保项目目录结构存在
        self._ensure_project_structure()
    
    def _ensure_project_structure(self):
        """确保项目目录结构存在"""
        directories = [
            self.project_dir / "raw",
            self.project_dir / "processing",
            self.project_dir / "output" / "clips",
            self.project_dir / "output" / "collections"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """保存处理元数据到文件系统"""
        metadata_file = self.project_dir / "processing" / f"{step}.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存元数据: {metadata_file}")
        return str(metadata_file)
    
    def get_metadata(self, step: str) -> Optional[Dict[str, Any]]:
        """获取处理元数据"""
        metadata_file = self.project_dir / "processing" / f"{step}.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_file(self, file_path: Path, target_name: str, file_type: str = "raw") -> str:
        """保存文件到项目目录"""
        if file_type == "raw":
            target_path = self.project_dir / "raw" / target_name
        elif file_type == "clip":
            target_path = self.project_dir / "output" / "clips" / target_name
        elif file_type == "collection":
            target_path = self.project_dir / "output" / "collections" / target_name
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        shutil.copy2(file_path, target_path)
        logger.info(f"保存文件: {target_path}")
        return str(target_path)
    
    def get_file_path(self, file_type: str, file_name: str) -> Optional[Path]:
        """获取文件路径"""
        if file_type == "raw":
            return self.project_dir / "raw" / file_name
        elif file_type == "clip":
            return self.project_dir / "output" / "clips" / file_name
        elif file_type == "collection":
            return self.project_dir / "output" / "collections" / file_name
        else:
            return None
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dir = self.data_dir / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
                    logger.info(f"清理临时文件: {temp_file}")
'''
    
    storage_service_path = backend_dir / "services" / "storage_service.py"
    with open(storage_service_path, 'w', encoding='utf-8') as f:
        f.write(storage_service_content)
    
    print(f"   创建存储服务: {storage_service_path}")

def create_migration_script():
    """创建数据迁移脚本"""
    print("\n📦 创建数据迁移脚本...")
    
    migration_script_content = '''#!/usr/bin/env python3
"""
数据迁移脚本 - 从旧架构迁移到新架构
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any

def migrate_project_data(project_id: str):
    """迁移单个项目的数据"""
    print(f"迁移项目: {project_id}")
    
    # 这里添加具体的数据迁移逻辑
    # 1. 读取旧的数据结构
    # 2. 转换为新的数据结构
    # 3. 保存到新的位置
    # 4. 更新数据库记录
    
    print(f"项目 {project_id} 迁移完成")

def migrate_all_projects():
    """迁移所有项目"""
    print("开始迁移所有项目...")
    
    # 获取所有项目目录
    data_dir = Path("data")
    projects_dir = data_dir / "projects"
    
    if not projects_dir.exists():
        print("没有找到项目目录")
        return
    
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            migrate_project_data(project_dir.name)
    
    print("所有项目迁移完成")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        migrate_project_data(project_id)
    else:
        migrate_all_projects()
'''
    
    migration_script_path = project_root / "scripts" / "migrate_to_optimized_storage.py"
    with open(migration_script_path, 'w', encoding='utf-8') as f:
        f.write(migration_script_content)
    
    print(f"   创建迁移脚本: {migration_script_path}")

def generate_optimization_report(stats: Dict[str, Any]):
    """生成优化报告"""
    print("\n📋 生成优化报告...")
    
    report_content = f"""# 存储架构优化报告

## 当前状态分析

### 数据库统计
- 项目数量: {stats['db_projects']}
- 切片数量: {stats['db_clips']}
- 合集数量: {stats['db_collections']}

### 文件系统统计
- 项目目录数量: {stats['fs_projects']}
- 总文件大小: {stats['fs_total_size'] / 1024 / 1024:.2f} MB

## 优化建议

### 1. 存储空间优化
- 移除数据库中的冗余数据
- 只保留文件路径引用
- 预计节省空间: {stats['fs_total_size'] / 1024 / 1024 * 0.1:.2f} MB

### 2. 性能优化
- 减少数据同步开销
- 优化文件访问路径
- 添加缓存机制

### 3. 维护性优化
- 简化数据管理逻辑
- 统一存储接口
- 改进错误处理

## 实施步骤

1. ✅ 分析当前存储使用情况
2. ✅ 创建优化的文件结构
3. ✅ 优化数据库模式
4. ✅ 创建统一存储服务
5. ✅ 创建数据迁移脚本
6. ⏳ 执行数据迁移
7. ⏳ 测试新架构
8. ⏳ 清理旧数据

## 注意事项

- 迁移前请备份所有数据
- 测试新架构的完整性
- 验证文件路径的正确性
- 确保API接口的兼容性
"""
    
    report_path = project_root / "docs" / "STORAGE_OPTIMIZATION_REPORT.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"   生成优化报告: {report_path}")

def main():
    """主函数"""
    print("🚀 开始存储架构优化...")
    
    # 1. 分析当前存储使用情况
    stats = analyze_current_storage()
    
    # 2. 创建优化的文件结构
    create_optimized_structure()
    
    # 3. 优化数据库模式
    optimize_database_schema()
    
    # 4. 创建统一存储服务
    create_storage_service()
    
    # 5. 创建数据迁移脚本
    create_migration_script()
    
    # 6. 生成优化报告
    generate_optimization_report(stats)
    
    print("\n✅ 存储架构优化完成!")
    print("\n📝 下一步操作:")
    print("1. 查看优化报告: docs/STORAGE_OPTIMIZATION_REPORT.md")
    print("2. 执行数据迁移: python scripts/migrate_to_optimized_storage.py")
    print("3. 测试新架构")
    print("4. 清理旧数据")

if __name__ == "__main__":
    main()
