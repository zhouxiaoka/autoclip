#!/usr/bin/env python3
"""
数据一致性检查脚本
检查数据库和文件系统之间的一致性
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.models.project import Project
from backend.models.clip import Clip
from backend.models.collection import Collection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_project_consistency(db, project_id: str):
    """检查单个项目的数据一致性"""
    logger.info(f"🔍 检查项目一致性: {project_id}")
    
    issues = []
    
    try:
        # 检查数据库中的项目
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            issues.append("项目在数据库中不存在")
            return {"project_id": project_id, "issues": issues, "status": "error"}
        
        # 检查项目目录
        data_dir = project_root / "data"
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            issues.append("项目目录不存在")
            return {"project_id": project_id, "issues": issues, "status": "error"}
        
        # 检查切片一致性
        clips_issues = check_clips_consistency(db, project_id, project_dir)
        issues.extend(clips_issues)
        
        # 检查合集一致性
        collections_issues = check_collections_consistency(db, project_id, project_dir)
        issues.extend(collections_issues)
        
        # 检查文件路径
        file_path_issues = check_file_paths_consistency(db, project_id, project_dir)
        issues.extend(file_path_issues)
        
        status = "warning" if issues else "ok"
        return {
            "project_id": project_id,
            "issues": issues,
            "status": status,
            "clips_count": len(db.query(Clip).filter(Clip.project_id == project_id).all()),
            "collections_count": len(db.query(Collection).filter(Collection.project_id == project_id).all())
        }
        
    except Exception as e:
        logger.error(f"检查项目 {project_id} 时发生错误: {e}")
        return {
            "project_id": project_id,
            "issues": [f"检查过程中发生错误: {str(e)}"],
            "status": "error"
        }


def check_clips_consistency(db, project_id: str, project_dir: Path):
    """检查切片数据一致性"""
    issues = []
    
    try:
        # 获取数据库中的切片
        db_clips = db.query(Clip).filter(Clip.project_id == project_id).all()
        
        # 检查文件系统中的切片文件
        clips_dir = project_dir / "output" / "clips"
        fs_clips = list(clips_dir.glob("*.mp4")) if clips_dir.exists() else []
        
        # 检查数据库中的切片文件是否存在
        for clip in db_clips:
            if clip.video_path:
                file_path = project_root / "data" / clip.video_path
                if not file_path.exists():
                    issues.append(f"切片文件不存在: {clip.video_path}")
        
        # 检查文件系统中的切片是否在数据库中有记录
        for clip_file in fs_clips:
            clip_name = clip_file.name
            found_in_db = any(clip.video_path and clip.video_path.endswith(clip_name) for clip in db_clips)
            if not found_in_db:
                issues.append(f"文件系统中的切片未在数据库中记录: {clip_name}")
        
        # 检查重复数据
        clips_metadata_file = project_dir / "clips_metadata.json"
        if clips_metadata_file.exists():
            issues.append("存在重复的切片元数据文件 (clips_metadata.json)")
        
    except Exception as e:
        issues.append(f"检查切片一致性时发生错误: {str(e)}")
    
    return issues


def check_collections_consistency(db, project_id: str, project_dir: Path):
    """检查合集数据一致性"""
    issues = []
    
    try:
        # 获取数据库中的合集
        db_collections = db.query(Collection).filter(Collection.project_id == project_id).all()
        
        # 检查文件系统中的合集文件
        collections_dir = project_dir / "output" / "collections"
        fs_collections = list(collections_dir.glob("*.mp4")) if collections_dir.exists() else []
        
        # 检查数据库中的合集文件是否存在
        for collection in db_collections:
            if collection.video_path:
                file_path = project_root / "data" / collection.video_path
                if not file_path.exists():
                    issues.append(f"合集文件不存在: {collection.video_path}")
        
        # 检查文件系统中的合集是否在数据库中有记录
        for collection_file in fs_collections:
            collection_name = collection_file.name
            found_in_db = any(collection.video_path and collection.video_path.endswith(collection_name) for collection in db_collections)
            if not found_in_db:
                issues.append(f"文件系统中的合集未在数据库中记录: {collection_name}")
        
        # 检查重复数据
        collections_metadata_file = project_dir / "collections_metadata.json"
        if collections_metadata_file.exists():
            issues.append("存在重复的合集元数据文件 (collections_metadata.json)")
        
    except Exception as e:
        issues.append(f"检查合集一致性时发生错误: {str(e)}")
    
    return issues


def check_file_paths_consistency(db, project_id: str, project_dir: Path):
    """检查文件路径一致性"""
    issues = []
    
    try:
        # 检查项目文件路径
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.video_path:
            video_path = project_root / "data" / project.video_path
            if not video_path.exists():
                issues.append(f"项目视频文件不存在: {project.video_path}")
        
        if project and project.subtitle_path:
            subtitle_path = project_root / "data" / project.subtitle_path
            if not subtitle_path.exists():
                issues.append(f"项目字幕文件不存在: {project.subtitle_path}")
        
    except Exception as e:
        issues.append(f"检查文件路径一致性时发生错误: {str(e)}")
    
    return issues


def generate_consistency_report(results):
    """生成一致性检查报告"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_projects": len(results),
        "ok_projects": len([r for r in results if r["status"] == "ok"]),
        "warning_projects": len([r for r in results if r["status"] == "warning"]),
        "error_projects": len([r for r in results if r["status"] == "error"]),
        "results": results
    }
    
    return report


def main():
    """主函数"""
    logger.info("🔍 开始数据一致性检查...")
    
    db = SessionLocal()
    try:
        # 获取所有项目
        projects = db.query(Project).all()
        
        if not projects:
            logger.info("📭 没有找到项目")
            return
        
        logger.info(f"📊 找到 {len(projects)} 个项目，开始检查...")
        
        results = []
        for project in projects:
            result = check_project_consistency(db, project.id)
            results.append(result)
        
        # 生成报告
        report = generate_consistency_report(results)
        
        # 显示检查结果
        print("\n" + "=" * 80)
        print("📊 数据一致性检查报告")
        print("=" * 80)
        print(f"检查时间: {report['timestamp']}")
        print(f"总项目数: {report['total_projects']}")
        print(f"✅ 正常: {report['ok_projects']}")
        print(f"⚠️  警告: {report['warning_projects']}")
        print(f"❌ 错误: {report['error_projects']}")
        
        print("\n📋 详细结果:")
        print("-" * 80)
        
        for result in results:
            status_icon = {
                "ok": "✅",
                "warning": "⚠️ ",
                "error": "❌"
            }.get(result["status"], "❓")
            
            print(f"{status_icon} 项目 {result['project_id'][:8]}... | "
                  f"切片: {result.get('clips_count', 0)} | "
                  f"合集: {result.get('collections_count', 0)}")
            
            if result["issues"]:
                for issue in result["issues"]:
                    print(f"    • {issue}")
        
        # 保存报告
        report_file = project_root / f"consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细报告已保存: {report_file}")
        
        # 提供建议
        if report['warning_projects'] > 0 or report['error_projects'] > 0:
            print("\n🔧 建议:")
            print("1. 运行数据迁移脚本修复问题")
            print("2. 检查文件权限和路径配置")
            print("3. 清理重复的元数据文件")
        
    except Exception as e:
        logger.error(f"❌ 检查过程中发生错误: {e}")
    finally:
        db.close()
    
    logger.info("🎉 一致性检查完成!")


if __name__ == "__main__":
    main()
