#!/usr/bin/env python3
"""
存储优化实施检查清单
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

def check_database_models():
    """检查数据库模型优化状态"""
    print("🔍 检查数据库模型优化状态...")
    
    checklist = {
        "Clip模型优化": {
            "移除processing_result字段": False,
            "优化clip_metadata字段": False,
            "保留video_path字段": False,
            "保留thumbnail_path字段": False
        },
        "Project模型优化": {
            "添加video_path字段": False,
            "添加subtitle_path字段": False,
            "优化project_metadata字段": False
        },
        "Collection模型优化": {
            "添加export_path字段": False,
            "优化collection_metadata字段": False
        }
    }
    
    # 检查Clip模型
    try:
        from models.clip import Clip
        clip_columns = [col.name for col in Clip.__table__.columns]
        
        if "processing_result" not in clip_columns:
            checklist["Clip模型优化"]["移除processing_result字段"] = True
        
        if "video_path" in clip_columns:
            checklist["Clip模型优化"]["保留video_path字段"] = True
            
        if "thumbnail_path" in clip_columns:
            checklist["Clip模型优化"]["保留thumbnail_path字段"] = True
        
        # 检查计算属性
        if hasattr(Clip, 'metadata_file_path'):
            checklist["Clip模型优化"]["优化clip_metadata字段"] = True
            
    except ImportError:
        print("    ❌ 无法导入Clip模型")
    
    # 检查Project模型
    try:
        from models.project import Project
        project_columns = [col.name for col in Project.__table__.columns]
        
        if "video_path" in project_columns:
            checklist["Project模型优化"]["添加video_path字段"] = True
            
        if "subtitle_path" in project_columns:
            checklist["Project模型优化"]["添加subtitle_path字段"] = True
        
        # 检查计算属性
        if hasattr(Project, 'storage_initialized'):
            checklist["Project模型优化"]["优化project_metadata字段"] = True
            
    except ImportError:
        print("    ❌ 无法导入Project模型")
    
    # 检查Collection模型
    try:
        from models.collection import Collection
        collection_columns = [col.name for col in Collection.__table__.columns]
        
        if "export_path" in collection_columns:
            checklist["Collection模型优化"]["添加export_path字段"] = True
        
        # 检查计算属性
        if hasattr(Collection, 'metadata_file_path'):
            checklist["Collection模型优化"]["优化collection_metadata字段"] = True
            
    except ImportError:
        print("    ❌ 无法导入Collection模型")
    
    return checklist

def check_storage_service():
    """检查存储服务状态"""
    print("\n🔍 检查存储服务状态...")
    
    checklist = {
        "StorageService": {
            "文件存在": False,
            "save_metadata方法": False,
            "save_file方法": False,
            "get_file_path方法": False,
            "cleanup_temp_files方法": False
        }
    }
    
    storage_service_path = backend_dir / "services" / "storage_service.py"
    
    if storage_service_path.exists():
        checklist["StorageService"]["文件存在"] = True
        
        # 读取文件内容检查方法
        with open(storage_service_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "def save_metadata" in content:
            checklist["StorageService"]["save_metadata方法"] = True
            
        if "def save_file" in content:
            checklist["StorageService"]["save_file方法"] = True
            
        if "def get_file_path" in content:
            checklist["StorageService"]["get_file_path方法"] = True
            
        if "def cleanup_temp_files" in content:
            checklist["StorageService"]["cleanup_temp_files方法"] = True
    
    return checklist

def check_pipeline_adapter():
    """检查PipelineAdapter优化状态"""
    print("\n🔍 检查PipelineAdapter优化状态...")
    
    checklist = {
        "PipelineAdapter": {
            "文件存在": False,
            "使用StorageService": False,
            "分离存储逻辑": False
        }
    }
    
    pipeline_adapter_path = backend_dir / "services" / "pipeline_adapter.py"
    
    if pipeline_adapter_path.exists():
        checklist["PipelineAdapter"]["文件存在"] = True
        
        # 读取文件内容检查
        with open(pipeline_adapter_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "StorageService" in content:
            checklist["PipelineAdapter"]["使用StorageService"] = True
            
        if "_save_clips_to_database" in content and "_save_collections_to_database" in content:
            checklist["PipelineAdapter"]["分离存储逻辑"] = True
    
    return checklist

def check_repositories():
    """检查Repository层优化状态"""
    print("\n🔍 检查Repository层优化状态...")
    
    checklist = {
        "ClipRepository": {
            "文件存在": False,
            "分离存储方法": False,
            "文件访问方法": False
        },
        "CollectionRepository": {
            "文件存在": False,
            "分离存储方法": False,
            "文件访问方法": False
        },
        "ProjectRepository": {
            "文件存在": False,
            "文件路径管理": False
        }
    }
    
    # 检查ClipRepository
    clip_repo_path = backend_dir / "repositories" / "clip_repository.py"
    if clip_repo_path.exists():
        checklist["ClipRepository"]["文件存在"] = True
        
        with open(clip_repo_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "get_clip_file" in content:
            checklist["ClipRepository"]["文件访问方法"] = True
        
        if "create_clip" in content:
            checklist["ClipRepository"]["分离存储方法"] = True
    
    # 检查CollectionRepository
    collection_repo_path = backend_dir / "repositories" / "collection_repository.py"
    if collection_repo_path.exists():
        checklist["CollectionRepository"]["文件存在"] = True
        
        with open(collection_repo_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "get_collection_file" in content:
            checklist["CollectionRepository"]["文件访问方法"] = True
        
        if "create_collection" in content:
            checklist["CollectionRepository"]["分离存储方法"] = True
    
    # 检查ProjectRepository
    project_repo_path = backend_dir / "repositories" / "project_repository.py"
    if project_repo_path.exists():
        checklist["ProjectRepository"]["文件存在"] = True
        
        with open(project_repo_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "get_project_file_paths" in content:
            checklist["ProjectRepository"]["文件路径管理"] = True
    
    return checklist

def check_api_endpoints():
    """检查API端点优化状态"""
    print("\n🔍 检查API端点优化状态...")
    
    checklist = {
        "文件上传API": {
            "文件存在": False,
            "优化存储逻辑": False
        },
        "切片API": {
            "文件存在": False,
            "按需加载数据": False
        },
        "合集API": {
            "文件存在": False,
            "按需加载数据": False
        },
        "文件访问API": {
            "文件存在": False,
            "内容访问端点": False
        }
    }
    
    # 检查文件上传API
    files_api_path = backend_dir / "api" / "v1" / "files.py"
    if files_api_path.exists():
        checklist["文件上传API"]["文件存在"] = True
        
        with open(files_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "upload" in content:
            checklist["文件上传API"]["优化存储逻辑"] = True
    
    # 检查切片API
    clips_api_path = backend_dir / "api" / "v1" / "clips.py"
    if clips_api_path.exists():
        checklist["切片API"]["文件存在"] = True
        
        with open(clips_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "get_clips" in content:
            checklist["切片API"]["按需加载数据"] = True
    
    # 检查合集API
    collections_api_path = backend_dir / "api" / "v1" / "collections.py"
    if collections_api_path.exists():
        checklist["合集API"]["文件存在"] = True
        
        with open(collections_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "include_content" in content:
            checklist["合集API"]["按需加载数据"] = True
    
    # 检查文件访问API
    files_api_path = backend_dir / "api" / "v1" / "files.py"
    if files_api_path.exists():
        checklist["文件访问API"]["文件存在"] = True
        
        with open(files_api_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "get_clip_content" in content:
            checklist["文件访问API"]["内容访问端点"] = True
    
    return checklist

def check_migration_scripts():
    """检查数据迁移脚本状态"""
    print("\n🔍 检查数据迁移脚本状态...")
    
    checklist = {
        "迁移脚本": {
            "文件存在": False,
            "数据验证": False,
            "回滚机制": False
        }
    }
    
    migration_script_path = backend_dir / "migrations" / "optimize_storage_models.py"
    
    if migration_script_path.exists():
        checklist["迁移脚本"]["文件存在"] = True
        
        with open(migration_script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "validate_migration" in content:
            checklist["迁移脚本"]["数据验证"] = True
            
        if "rollback_migration" in content:
            checklist["迁移脚本"]["回滚机制"] = True
    
    return checklist

def check_file_structure():
    """检查文件结构优化状态"""
    print("\n🔍 检查文件结构优化状态...")
    
    checklist = {
        "目录结构": {
            "temp目录": False,
            "cache目录": False,
            "backups目录": False,
            "示例项目结构": False
        }
    }
    
    data_dir = project_root / "data"
    
    if (data_dir / "temp").exists():
        checklist["目录结构"]["temp目录"] = True
        
    if (data_dir / "cache").exists():
        checklist["目录结构"]["cache目录"] = True
        
    if (data_dir / "backups").exists():
        checklist["目录结构"]["backups目录"] = True
        
    if (data_dir / "projects" / "example-project").exists():
        checklist["目录结构"]["示例项目结构"] = True
    
    return checklist

def print_checklist_results(all_checklists: Dict[str, Dict[str, Dict[str, bool]]]):
    """打印检查清单结果"""
    print("\n" + "="*60)
    print("📋 存储优化实施检查清单结果")
    print("="*60)
    
    total_items = 0
    completed_items = 0
    
    for category, items in all_checklists.items():
        print(f"\n🔸 {category}")
        print("-" * 40)
        
        for subcategory, checks in items.items():
            print(f"  📁 {subcategory}")
            
            for check_name, completed in checks.items():
                status = "✅" if completed else "❌"
                print(f"    {status} {check_name}")
                total_items += 1
                if completed:
                    completed_items += 1
    
    print("\n" + "="*60)
    completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
    print(f"📊 总体完成度: {completion_rate:.1f}% ({completed_items}/{total_items})")
    
    if completion_rate >= 80:
        print("🎉 存储优化实施进展良好！")
    elif completion_rate >= 50:
        print("🚧 存储优化实施进行中，需要继续推进")
    else:
        print("⚠️ 存储优化实施需要加快进度")
    
    print("="*60)

def generate_next_steps(all_checklists: Dict[str, Dict[str, Dict[str, bool]]]):
    """生成下一步行动计划"""
    print("\n📝 下一步行动计划:")
    print("-" * 40)
    
    next_steps = []
    
    # 检查数据库模型优化
    db_models = all_checklists.get("数据库模型优化", {})
    for subcategory, checks in db_models.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查存储服务
    storage_service = all_checklists.get("存储服务", {})
    for subcategory, checks in storage_service.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查PipelineAdapter
    pipeline_adapter = all_checklists.get("PipelineAdapter", {})
    for subcategory, checks in pipeline_adapter.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查Repository层
    repositories = all_checklists.get("Repository层", {})
    for subcategory, checks in repositories.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查API端点
    api_endpoints = all_checklists.get("API端点", {})
    for subcategory, checks in api_endpoints.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查迁移脚本
    migration_scripts = all_checklists.get("迁移脚本", {})
    for subcategory, checks in migration_scripts.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    # 检查文件结构
    file_structure = all_checklists.get("文件结构", {})
    for subcategory, checks in file_structure.items():
        for check_name, completed in checks.items():
            if not completed:
                next_steps.append(f"🔧 完成 {subcategory} - {check_name}")
    
    if next_steps:
        for i, step in enumerate(next_steps[:10], 1):  # 只显示前10个
            print(f"{i}. {step}")
        
        if len(next_steps) > 10:
            print(f"... 还有 {len(next_steps) - 10} 个任务")
    else:
        print("🎉 所有任务已完成！")

def main():
    """主函数"""
    print("🚀 开始存储优化实施检查...")
    
    # 执行各项检查
    all_checklists = {
        "数据库模型优化": check_database_models(),
        "存储服务": check_storage_service(),
        "PipelineAdapter": check_pipeline_adapter(),
        "Repository层": check_repositories(),
        "API端点": check_api_endpoints(),
        "迁移脚本": check_migration_scripts(),
        "文件结构": check_file_structure()
    }
    
    # 打印结果
    print_checklist_results(all_checklists)
    
    # 生成下一步计划
    generate_next_steps(all_checklists)
    
    print("\n📚 相关文档:")
    print("- docs/STORAGE_ARCHITECTURE_OPTIMIZATION.md")
    print("- docs/STORAGE_OPTIMIZATION_WORK_BREAKDOWN.md")
    print("- docs/STORAGE_ARCHITECTURE_ANALYSIS.md")

if __name__ == "__main__":
    main()
