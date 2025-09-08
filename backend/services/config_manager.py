"""
项目配置管理器
负责集中管理每个项目的配置信息，包括prompt文件、API密钥、处理参数等
"""

import os
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from ..models.project import ProjectType
from ..core.database import get_db

logger = logging.getLogger(__name__)


class ProcessingStep(str, Enum):
    """处理步骤枚举"""
    STEP1_OUTLINE = "step1_outline"
    STEP2_TIMELINE = "step2_timeline"
    STEP3_SCORING = "step3_scoring"
    STEP4_TITLE = "step4_title"
    STEP5_CLUSTERING = "step5_clustering"
    STEP6_VIDEO = "step6_video"


@dataclass
class LLMConfig:
    """LLM配置"""
    api_key: str
    model_name: str = "qwen-plus"
    max_retries: int = 3
    timeout_seconds: int = 30


@dataclass
class ProcessingParams:
    """处理参数"""
    chunk_size: int = 5000
    min_score_threshold: float = 0.7
    max_clips_per_collection: int = 5
    min_topic_duration_minutes: int = 2
    max_topic_duration_minutes: int = 12
    target_topic_duration_minutes: int = 5
    min_topics_per_chunk: int = 3
    max_topics_per_chunk: int = 8


class ProjectConfigManager:
    """项目配置管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_dir = Path(f"data/projects/{project_id}")
        self.config_path = self.project_dir / "config.yaml"
        # 使用绝对路径指向项目根目录的prompt文件夹
        project_root = Path(__file__).parent.parent.parent
        self.prompt_dir = Path(__file__).parent.parent / "prompt"
        
        # 确保项目目录存在
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载项目配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config is None:
                        logger.warning(f"配置文件为空: {self.config_path}")
                        return {}
                    return config
            except yaml.YAMLError as e:
                logger.error(f"YAML解析错误: {self.config_path}, 错误: {e}")
                return {}
            except FileNotFoundError as e:
                logger.error(f"配置文件不存在: {self.config_path}, 错误: {e}")
                return {}
            except Exception as e:
                logger.error(f"加载项目配置失败: {self.config_path}, 错误: {e}")
                return {}
        return {}
    
    def _save_config(self):
        """保存项目配置"""
        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"配置已保存: {self.config_path}")
        except Exception as e:
            logger.error(f"保存项目配置失败: {self.config_path}, 错误: {e}")
            raise
    
    def get_prompt_files(self, project_type: str = "default", language: str = "zh") -> Dict[str, Path]:
        """
        获取项目对应的prompt文件路径
        
        Args:
            project_type: 项目类型，对应不同的prompt模板
            language: 语言版本，支持多语言prompt
            
        Returns:
            prompt文件路径字典
        """
        # 从配置中获取prompt设置
        prompt_config = self.config.get("prompts", {})
        
        # 基础prompt文件
        base_prompts = {
            "outline": self.prompt_dir / "大纲.txt",
            "timeline": self.prompt_dir / "时间点.txt",
            "recommendation": self.prompt_dir / "推荐理由.txt",
            "title": self.prompt_dir / "标题生成.txt",
            "clustering": self.prompt_dir / "主题聚类.txt"
        }
        
        # 如果配置中指定了自定义prompt路径，使用配置的路径
        if "custom_paths" in prompt_config:
            for key, custom_path in prompt_config["custom_paths"].items():
                if key in base_prompts:
                    custom_file = Path(custom_path)
                    if custom_file.exists():
                        base_prompts[key] = custom_file
                        logger.info(f"使用自定义prompt: {key} -> {custom_path}")
        
        # 检查项目类型特定的prompt文件
        type_prompt_dir = self.prompt_dir / project_type
        if type_prompt_dir.exists():
            for key in base_prompts:
                type_specific_prompt = type_prompt_dir / f"{key}.txt"
                if type_specific_prompt.exists():
                    base_prompts[key] = type_specific_prompt
                    logger.info(f"使用项目类型特定prompt: {key} -> {type_specific_prompt}")
        
        # 检查多语言prompt文件
        if language != "zh":
            lang_prompt_dir = self.prompt_dir / "languages" / language
            if lang_prompt_dir.exists():
                for key in base_prompts:
                    lang_specific_prompt = lang_prompt_dir / f"{key}.txt"
                    if lang_specific_prompt.exists():
                        base_prompts[key] = lang_specific_prompt
                        logger.info(f"使用多语言prompt: {key} -> {lang_specific_prompt}")
        
        # 验证所有prompt文件是否存在
        missing_prompts = []
        for key, path in base_prompts.items():
            if not path.exists():
                missing_prompts.append(f"{key}: {path}")
        
        if missing_prompts:
            logger.warning(f"缺少prompt文件: {missing_prompts}")
        
        return base_prompts
    
    def get_llm_config(self) -> LLMConfig:
        """获取LLM配置"""
        # 优先从项目配置获取
        llm_config = self.config.get("llm", {})
        
        # API密钥优先级：项目配置 > 环境变量 > 默认值
        api_key = llm_config.get("api_key") or os.getenv("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY 未在项目配置或环境变量中设置")
        
        return LLMConfig(
            api_key=api_key,
            model_name=llm_config.get("model_name", "qwen-plus"),
            max_retries=llm_config.get("max_retries", 3),
            timeout_seconds=llm_config.get("timeout_seconds", 30)
        )
    
    def get_processing_params(self) -> ProcessingParams:
        """获取处理参数"""
        params = self.config.get("processing_params", {})
        return ProcessingParams(
            chunk_size=params.get("chunk_size", 5000),
            min_score_threshold=params.get("min_score_threshold", 0.7),
            max_clips_per_collection=params.get("max_clips_per_collection", 5),
            min_topic_duration_minutes=params.get("min_topic_duration_minutes", 2),
            max_topic_duration_minutes=params.get("max_topic_duration_minutes", 12),
            target_topic_duration_minutes=params.get("target_topic_duration_minutes", 5),
            min_topics_per_chunk=params.get("min_topics_per_chunk", 3),
            max_topics_per_chunk=params.get("max_topics_per_chunk", 8)
        )
    
    def update_processing_params(self, **kwargs):
        """更新处理参数"""
        if "processing_params" not in self.config:
            self.config["processing_params"] = {}
        
        self.config["processing_params"].update(kwargs)
        self._save_config()
    
    def update_llm_config(self, **kwargs):
        """更新LLM配置"""
        if "llm" not in self.config:
            self.config["llm"] = {}
        
        self.config["llm"].update(kwargs)
        self._save_config()
    
    def get_project_paths(self) -> Dict[str, Path]:
        """获取项目相关路径"""
        return {
            "project_dir": self.project_dir,
            "metadata_dir": self.project_dir / "metadata",
            "raw_dir": self.project_dir / "raw",
            "outputs_dir": self.project_dir / "outputs",
            "logs_dir": self.project_dir / "logs"
        }
    
    def ensure_project_directories(self):
        """确保项目目录结构存在"""
        paths = self.get_project_paths()
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
    
    def get_step_config(self, step_name: str) -> Dict[str, Any]:
        """获取特定步骤的配置"""
        step_configs = self.config.get("steps", {})
        return step_configs.get(step_name, {})
    
    def update_step_config(self, step_name: str, **kwargs):
        """更新特定步骤的配置"""
        if "steps" not in self.config:
            self.config["steps"] = {}
        
        if step_name not in self.config["steps"]:
            self.config["steps"][step_name] = {}
        
        self.config["steps"][step_name].update(kwargs)
        self._save_config()
    
    def backup_config(self, backup_path: Optional[Path] = None) -> Path:
        """备份当前配置"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.project_dir / f"config_backup_{timestamp}.yaml"
        
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"配置已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"配置备份失败: {e}")
            raise
    
    def restore_config(self, backup_path: Path) -> bool:
        """从备份恢复配置"""
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_config = yaml.safe_load(f)
            
            if backup_config is None:
                raise ValueError("备份文件为空")
            
            # 先备份当前配置
            self.backup_config()
            
            # 恢复配置
            self.config = backup_config
            self._save_config()
            
            logger.info(f"配置已从备份恢复: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"配置恢复失败: {e}")
            return False
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "project_id": self.project_id,
            "llm_config": {
                "api_key": self.get_llm_config().api_key,
                "model_name": self.get_llm_config().model_name,
                "max_retries": self.get_llm_config().max_retries,
                "timeout_seconds": self.get_llm_config().timeout_seconds
            },
            "processing_params": {
                "chunk_size": self.get_processing_params().chunk_size,
                "min_score_threshold": self.get_processing_params().min_score_threshold,
                "max_clips_per_collection": self.get_processing_params().max_clips_per_collection,
                "min_topic_duration_minutes": self.get_processing_params().min_topic_duration_minutes,
                "max_topic_duration_minutes": self.get_processing_params().max_topic_duration_minutes,
                "target_topic_duration_minutes": self.get_processing_params().target_topic_duration_minutes,
                "min_topics_per_chunk": self.get_processing_params().min_topics_per_chunk,
                "max_topics_per_chunk": self.get_processing_params().max_topics_per_chunk
            },
            "project_paths": self.get_project_paths(),
            "prompt_files": self.get_prompt_files()
        }
    
    def get_project_config(self) -> Dict[str, Any]:
        """获取项目配置"""
        # 尝试从数据库获取项目配置
        try:
            from sqlalchemy.orm import Session
            from ..core.database import SessionLocal
            from ..models.project import Project
            
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == self.project_id).first()
                if project and project.processing_config:
                    return project.processing_config
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"无法从数据库获取项目配置: {e}")
        
        # 回退到本地配置文件
        return self.config
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置的完整性和有效性"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "missing_files": []
        }
        
        # 验证LLM配置
        try:
            self.get_llm_config()
        except ValueError as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"LLM配置错误: {e}")
        
        # 验证prompt文件
        prompt_files = self.get_prompt_files()
        for key, path in prompt_files.items():
            if not path.exists():
                validation_result["warnings"].append(f"Prompt文件不存在: {key} -> {path}")
                validation_result["missing_files"].append(str(path))
        
        # 验证项目目录
        project_paths = self.get_project_paths()
        for key, path in project_paths.items():
            if not path.exists():
                validation_result["warnings"].append(f"项目目录不存在: {key} -> {path}")
        
        # 验证处理参数
        try:
            params = self.get_processing_params()
            if params.chunk_size <= 0:
                validation_result["errors"].append("chunk_size必须大于0")
            if params.min_score_threshold < 0 or params.min_score_threshold > 1:
                validation_result["errors"].append("min_score_threshold必须在0-1之间")
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"处理参数错误: {e}")
        
        if validation_result["errors"]:
            validation_result["valid"] = False
        
        return validation_result