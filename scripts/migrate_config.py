#!/usr/bin/env python3
"""
配置迁移脚本
将旧的分散配置系统迁移到新的统一配置系统
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

from backend.core.unified_config import UnifiedConfig, config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_old_configs():
    """分析旧的配置文件"""
    logger.info("🔍 分析旧配置文件...")
    
    old_configs = {}
    
    # 检查data/settings.json
    settings_file = project_root / "data" / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                old_configs['settings.json'] = json.load(f)
            logger.info(f"✅ 找到配置文件: {settings_file}")
        except Exception as e:
            logger.warning(f"⚠️  读取配置文件失败: {e}")
    
    # 检查.env文件
    env_file = project_root / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                env_content = f.read()
                old_configs['.env'] = parse_env_file(env_content)
            logger.info(f"✅ 找到环境变量文件: {env_file}")
        except Exception as e:
            logger.warning(f"⚠️  读取环境变量文件失败: {e}")
    
    # 检查backend/core/config.py中的默认值
    old_configs['config.py_defaults'] = {
        "database_url": "sqlite:///./data/autoclip.db",
        "redis_url": "redis://localhost:6379/0",
        "api_dashscope_api_key": "",
        "api_model_name": "qwen-plus",
        "processing_chunk_size": 5000,
        "processing_min_score_threshold": 0.7,
        "log_level": "INFO"
    }
    
    return old_configs


def parse_env_file(env_content: str) -> dict:
    """解析.env文件内容"""
    env_vars = {}
    for line in env_content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip().strip('"\'')
    return env_vars


def migrate_configs(old_configs: dict, dry_run: bool = True):
    """迁移配置到新的统一配置系统"""
    logger.info(f"🔄 开始配置迁移 (dry_run={dry_run})")
    
    migration_log = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "migrated_settings": {},
        "issues": []
    }
    
    try:
        # 创建新的配置实例
        new_config = UnifiedConfig()
        
        # 迁移settings.json中的配置
        if 'settings.json' in old_configs:
            settings = old_configs['settings.json']
            migrated_settings = migrate_settings_json(settings, new_config)
            migration_log['migrated_settings']['settings.json'] = migrated_settings
        
        # 迁移.env文件中的配置
        if '.env' in old_configs:
            env_vars = old_configs['.env']
            migrated_env = migrate_env_vars(env_vars, new_config)
            migration_log['migrated_settings']['.env'] = migrated_env
        
        # 验证新配置
        validation_result = new_config.validate_config()
        if not validation_result['valid']:
            migration_log['issues'].extend(validation_result['issues'])
        
        if dry_run:
            logger.info("🔍 模拟迁移完成")
            return {
                "success": True,
                "dry_run": True,
                "migration_log": migration_log,
                "new_config_summary": new_config.get_config_summary()
            }
        
        # 实际迁移
        if not migration_log['issues']:
            # 备份旧配置
            backup_old_configs(old_configs)
            
            # 保存新配置
            new_config.save_to_file()
            
            logger.info("✅ 配置迁移完成")
            return {
                "success": True,
                "migration_log": migration_log,
                "new_config_summary": new_config.get_config_summary()
            }
        else:
            logger.error("❌ 配置验证失败，无法迁移")
            return {
                "success": False,
                "migration_log": migration_log
            }
            
    except Exception as e:
        logger.error(f"❌ 配置迁移失败: {e}")
        migration_log['issues'].append(f"迁移过程中发生错误: {str(e)}")
        return {
            "success": False,
            "migration_log": migration_log
        }


def migrate_settings_json(settings: dict, new_config: UnifiedConfig) -> dict:
    """迁移settings.json中的配置"""
    migrated = {}
    
    # API配置
    if 'dashscope_api_key' in settings:
        new_config.api.dashscope_api_key = settings['dashscope_api_key']
        migrated['dashscope_api_key'] = 'migrated'
    
    if 'model_name' in settings:
        new_config.api.model_name = settings['model_name']
        migrated['model_name'] = 'migrated'
    
    # 处理配置
    if 'chunk_size' in settings:
        new_config.processing.chunk_size = settings['chunk_size']
        migrated['chunk_size'] = 'migrated'
    
    if 'min_score_threshold' in settings:
        new_config.processing.min_score_threshold = settings['min_score_threshold']
        migrated['min_score_threshold'] = 'migrated'
    
    if 'max_clips_per_collection' in settings:
        new_config.processing.max_clips_per_collection = settings['max_clips_per_collection']
        migrated['max_clips_per_collection'] = 'migrated'
    
    # 语音识别配置
    if 'speech_recognition_method' in settings:
        new_config.speech_recognition.method = settings['speech_recognition_method']
        migrated['speech_recognition_method'] = 'migrated'
    
    if 'speech_recognition_language' in settings:
        new_config.speech_recognition.language = settings['speech_recognition_language']
        migrated['speech_recognition_language'] = 'migrated'
    
    # B站配置
    if 'bilibili_auto_upload' in settings:
        new_config.bilibili.auto_upload = settings['bilibili_auto_upload']
        migrated['bilibili_auto_upload'] = 'migrated'
    
    if 'bilibili_default_tid' in settings:
        new_config.bilibili.default_tid = settings['bilibili_default_tid']
        migrated['bilibili_default_tid'] = 'migrated'
    
    return migrated


def migrate_env_vars(env_vars: dict, new_config: UnifiedConfig) -> dict:
    """迁移环境变量"""
    migrated = {}
    
    # 数据库配置
    if 'DATABASE_URL' in env_vars:
        new_config.database.url = env_vars['DATABASE_URL']
        migrated['DATABASE_URL'] = 'migrated'
    
    # Redis配置
    if 'REDIS_URL' in env_vars:
        new_config.redis.url = env_vars['REDIS_URL']
        migrated['REDIS_URL'] = 'migrated'
    
    # API配置
    if 'DASHSCOPE_API_KEY' in env_vars:
        new_config.api.dashscope_api_key = env_vars['DASHSCOPE_API_KEY']
        migrated['DASHSCOPE_API_KEY'] = 'migrated'
    
    if 'API_MODEL_NAME' in env_vars:
        new_config.api.model_name = env_vars['API_MODEL_NAME']
        migrated['API_MODEL_NAME'] = 'migrated'
    
    # 处理配置
    if 'PROCESSING_CHUNK_SIZE' in env_vars:
        new_config.processing.chunk_size = int(env_vars['PROCESSING_CHUNK_SIZE'])
        migrated['PROCESSING_CHUNK_SIZE'] = 'migrated'
    
    if 'PROCESSING_MIN_SCORE_THRESHOLD' in env_vars:
        new_config.processing.min_score_threshold = float(env_vars['PROCESSING_MIN_SCORE_THRESHOLD'])
        migrated['PROCESSING_MIN_SCORE_THRESHOLD'] = 'migrated'
    
    # 日志配置
    if 'LOG_LEVEL' in env_vars:
        new_config.logging.level = env_vars['LOG_LEVEL']
        migrated['LOG_LEVEL'] = 'migrated'
    
    if 'LOG_FILE' in env_vars:
        new_config.logging.file = env_vars['LOG_FILE']
        migrated['LOG_FILE'] = 'migrated'
    
    return migrated


def backup_old_configs(old_configs: dict):
    """备份旧配置文件"""
    backup_dir = project_root / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(exist_ok=True)
    
    logger.info(f"📦 创建配置备份: {backup_dir}")
    
    # 备份settings.json
    if 'settings.json' in old_configs:
        settings_file = project_root / "data" / "settings.json"
        if settings_file.exists():
            backup_file = backup_dir / "settings.json"
            with open(settings_file, 'r', encoding='utf-8') as src, \
                 open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
    
    # 备份.env文件
    env_file = project_root / ".env"
    if env_file.exists():
        backup_file = backup_dir / ".env"
        with open(env_file, 'r', encoding='utf-8') as src, \
             open(backup_file, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    # 保存迁移日志
    migration_log_file = backup_dir / "migration_log.json"
    with open(migration_log_file, 'w', encoding='utf-8') as f:
        json.dump(old_configs, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 配置备份完成: {backup_dir}")


def display_config_comparison(old_configs: dict, new_config_summary: dict):
    """显示配置对比"""
    print("\n" + "=" * 80)
    print("📊 配置对比")
    print("=" * 80)
    
    print("\n🔧 API配置:")
    print(f"  模型名称: {new_config_summary['api']['model_name']}")
    print(f"  最大Token: {new_config_summary['api']['max_tokens']}")
    print(f"  超时时间: {new_config_summary['api']['timeout']}秒")
    print(f"  API密钥: {'已配置' if new_config_summary['api']['has_api_key'] else '未配置'}")
    
    print("\n⚙️  处理配置:")
    print(f"  分块大小: {new_config_summary['processing']['chunk_size']}")
    print(f"  最小评分阈值: {new_config_summary['processing']['min_score_threshold']}")
    print(f"  最大切片数: {new_config_summary['processing']['max_clips_per_collection']}")
    
    print("\n🗄️  数据库配置:")
    print(f"  数据库URL: {new_config_summary['database']['url']}")
    print(f"  Redis URL: {new_config_summary['redis']['url']}")
    
    print("\n📁 路径配置:")
    print(f"  数据目录: {new_config_summary['paths']['data_dir']}")
    print(f"  上传目录: {new_config_summary['paths']['uploads_dir']}")
    print(f"  输出目录: {new_config_summary['paths']['output_dir']}")
    
    print("\n📝 日志配置:")
    print(f"  日志级别: {new_config_summary['logging']['level']}")
    print(f"  日志文件: {new_config_summary['logging']['file']}")


def main():
    """主函数"""
    logger.info("🚀 开始配置迁移...")
    
    # 分析旧配置
    old_configs = analyze_old_configs()
    
    if not old_configs:
        logger.info("📭 没有找到需要迁移的配置文件")
        return
    
    print("\n📋 发现的配置文件:")
    for config_name in old_configs.keys():
        print(f"  • {config_name}")
    
    # 询问是否继续
    print("\n" + "=" * 60)
    print("🔧 迁移选项:")
    print("1. 模拟迁移 (dry run) - 查看迁移效果但不实际执行")
    print("2. 执行迁移 - 实际迁移配置并备份旧文件")
    print("3. 退出")
    
    while True:
        choice = input("\n请选择操作 (1/2/3): ").strip()
        if choice in ['1', '2', '3']:
            break
        print("❌ 无效选择，请输入 1、2 或 3")
    
    if choice == '3':
        logger.info("👋 用户取消迁移")
        return
    
    dry_run = (choice == '1')
    
    # 执行迁移
    result = migrate_configs(old_configs, dry_run)
    
    if result['success']:
        if dry_run:
            print("\n🔍 模拟迁移结果:")
        else:
            print("\n✅ 迁移完成:")
        
        # 显示配置对比
        if 'new_config_summary' in result:
            display_config_comparison(old_configs, result['new_config_summary'])
        
        # 显示迁移日志
        migration_log = result['migration_log']
        if migration_log['migrated_settings']:
            print("\n📊 迁移统计:")
            for config_name, migrated in migration_log['migrated_settings'].items():
                print(f"  {config_name}: {len(migrated)} 个设置项")
        
        # 显示问题
        if migration_log['issues']:
            print("\n⚠️  发现的问题:")
            for issue in migration_log['issues']:
                print(f"  • {issue}")
        
        if not dry_run:
            print(f"\n💾 备份位置: config_backup_*")
            print("🔧 建议:")
            print("1. 测试系统功能是否正常")
            print("2. 确认无误后可以删除备份文件")
            print("3. 检查新的配置文件格式")
    
    else:
        print("\n❌ 迁移失败:")
        migration_log = result['migration_log']
        if migration_log['issues']:
            for issue in migration_log['issues']:
                print(f"  • {issue}")
    
    logger.info("🎉 配置迁移完成!")


if __name__ == "__main__":
    main()
