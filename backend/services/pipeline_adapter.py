"""
流水线适配器
负责文件路径映射和流水线接口适配，让现有流水线逻辑保持原状
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from shutil import copy2

from .config_manager import ProjectConfigManager
from .path_manager import PathManager

logger = logging.getLogger(__name__)


class PipelineAdapter:
    """流水线适配器，负责路径映射和接口适配"""
    
    def __init__(self, project_id: str, debug_mode: bool = False):
        self.project_id = project_id
        self.debug_mode = debug_mode
        self.config_manager = ProjectConfigManager(project_id)
        self.path_manager = PathManager(project_id)
        self.project_paths = self.path_manager.get_project_paths()
        
        # 确保项目目录结构存在
        self.path_manager.ensure_directories()
    
    def get_step_input_path(self, step_name: str) -> Path:
        """获取步骤输入文件路径"""
        return self.path_manager.get_step_input_path(step_name)
    
    def get_step_output_path(self, step_name: str) -> Path:
        """获取步骤输出文件路径"""
        return self.path_manager.get_step_output_path(step_name)
    
    def get_step_intermediate_dir(self, step_name: str) -> Path:
        """获取步骤中间文件目录"""
        return self.path_manager.get_step_intermediate_dir(step_name)
    
    def prepare_step_environment(self, step_name: str, input_data: Any = None):
        """准备步骤执行环境"""
        # 使用PathManager创建步骤目录
        self.path_manager.create_step_directories(step_name)
        
        # 如果有输入数据，保存到输入文件
        if input_data is not None:
            input_path = self.get_step_input_path(step_name)
            self._save_json(input_path, input_data)
    
    def should_skip_step(self, step_name: str) -> bool:
        """
        判断是否应该跳过步骤（debug模式下如果输出已存在则跳过）
        
        Args:
            step_name: 步骤名称
            
        Returns:
            是否应该跳过
        """
        if not self.debug_mode:
            return False
        
        output_path = self.get_step_output_path(step_name)
        if output_path.exists():
            logger.info(f"Debug模式：跳过步骤 {step_name}，输出文件已存在: {output_path}")
            return True
        
        return False
    
    def get_step_cache_info(self, step_name: str) -> Dict[str, Any]:
        """
        获取步骤缓存信息
        
        Args:
            step_name: 步骤名称
            
        Returns:
            缓存信息
        """
        output_path = self.get_step_output_path(step_name)
        input_path = self.get_step_input_path(step_name)
        
        cache_info = {
            "step_name": step_name,
            "output_exists": output_path.exists(),
            "input_exists": input_path.exists(),
            "output_path": str(output_path),
            "input_path": str(input_path),
            "output_size": output_path.stat().st_size if output_path.exists() else 0,
            "input_size": input_path.stat().st_size if input_path.exists() else 0,
            "output_modified": output_path.stat().st_mtime if output_path.exists() else 0,
            "input_modified": input_path.stat().st_mtime if input_path.exists() else 0
        }
        
        return cache_info
    
    def _save_json(self, path: Path, data: Any):
        """保存JSON数据到文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已保存到: {path}")
    
    def _load_json(self, path: Path) -> Any:
        """从文件加载JSON数据"""
        if not path.exists():
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def adapt_step(self, step_name: str, **kwargs) -> Dict[str, Any]:
        """
        统一的步骤适配方法
        
        Args:
            step_name: 步骤名称
            **kwargs: 步骤特定参数
            
        Returns:
            适配后的参数
        """
        logger.info(f"开始适配步骤: {step_name}")
        logger.debug(f"步骤 {step_name} 输入参数: {list(kwargs.keys())}")
        
        step_config = {
            "step1_outline": {
                "required_inputs": ["srt_path"],
                "input_mapping": {"srt_path": "srt_path"},
                "output_path": "step1_outline",
                "special_handling": "copy_srt_file"
            },
            "step2_timeline": {
                "required_inputs": ["step1_outline"],
                "input_mapping": {"outline_path": "step1_outline"},
                "output_path": "step2_timeline"
            },
            "step3_scoring": {
                "required_inputs": ["step2_timeline"],
                "input_mapping": {"timeline_path": "step2_timeline"},
                "output_path": "step3_scoring"
            },
            "step4_title": {
                "required_inputs": ["step3_scoring"],
                "input_mapping": {"high_score_clips_path": "step3_scoring"},
                "output_path": "step4_title",
                "metadata_dir_type": "str"
            },
            "step5_clustering": {
                "required_inputs": ["step4_title"],
                "input_mapping": {"clips_with_titles_path": "step4_title"},
                "output_path": "step5_clustering",
                "metadata_dir_type": "str"
            },
            "step6_video": {
                "required_inputs": ["step4_title", "step5_clustering"],
                "input_mapping": {
                    "clips_with_titles_path": "step4_title",
                    "collections_path": "step5_clustering",
                    "input_video": "input_video"
                },
                "output_path": "step6_video",
                "metadata_dir_type": "str",
                "output_param_name": "output_dir",
                "special_handling": "add_input_video"
            }
        }
        
        if step_name not in step_config:
            logger.error(f"未知的步骤: {step_name}")
            raise ValueError(f"未知的步骤: {step_name}")
        
        config = step_config[step_name]
        logger.debug(f"步骤 {step_name} 配置: {config}")
        
        # 处理特殊输入（如SRT文件复制）
        if "special_handling" in config:
            if config["special_handling"] == "copy_srt_file":
                srt_path = kwargs.get("srt_path")
                if not srt_path or not srt_path.exists():
                    logger.error(f"SRT文件不存在: {srt_path}")
                    raise FileNotFoundError(f"SRT文件不存在: {srt_path}")
                
                # 复制SRT文件到项目目录
                project_srt_path = self.path_manager.get_srt_path()
                
                # 检查源路径和目标路径是否相同
                if srt_path.resolve() == project_srt_path.resolve():
                    logger.info(f"SRT文件已在目标位置，跳过复制: {srt_path}")
                else:
                    logger.info(f"复制SRT文件: {srt_path} -> {project_srt_path}")
                    copy2(srt_path, project_srt_path)
                
                kwargs["srt_path"] = project_srt_path
            elif config["special_handling"] == "add_input_video":
                # 为step6_video添加输入视频路径
                input_video_path = self.path_manager.get_video_path()
                if not input_video_path.exists():
                    logger.error(f"输入视频文件不存在: {input_video_path}")
                    raise FileNotFoundError(f"输入视频文件不存在: {input_video_path}")
                
                kwargs["input_video"] = input_video_path
                logger.info(f"添加输入视频路径: {input_video_path}")
        
        # 验证输入文件
        for input_name in config["required_inputs"]:
            if input_name not in kwargs:
                # 尝试从前一步的输出获取
                prev_step_output = self.get_step_output_path(input_name)
                logger.debug(f"检查输入文件: {input_name} -> {prev_step_output}")
                if not prev_step_output.exists():
                    logger.error(f"输入文件不存在: {input_name} -> {prev_step_output}")
                    raise FileNotFoundError(f"输入文件不存在: {input_name} -> {prev_step_output}")
                kwargs[input_name] = prev_step_output
                logger.debug(f"使用前一步输出作为输入: {input_name}")
        
        # 构建输出路径
        output_path = self.get_step_output_path(config["output_path"])
        logger.debug(f"步骤 {step_name} 输出路径: {output_path}")
        
        # 构建基础参数
        output_param_name = config.get("output_param_name", "output_path")
        params = {
            output_param_name: output_path
        }
        
        # 只有非step6的步骤才添加prompt_files
        if step_name != "step6_video":
            params["prompt_files"] = self.config_manager.get_prompt_files()
        
        # 处理特殊输出映射（如step6的output_dir）
        if "special_output_mapping" in config:
            for param_name, output_param in config["special_output_mapping"].items():
                params[param_name] = params[output_param]
                logger.debug(f"特殊输出映射: {param_name} <- {output_param}")
        
        # 添加输入映射
        for param_name, input_name in config["input_mapping"].items():
            if input_name in kwargs:
                params[param_name] = kwargs[input_name]
                logger.debug(f"映射参数: {param_name} <- {input_name}")
        
        # 添加metadata_dir
        metadata_dir = self.project_paths["metadata_dir"]
        if config.get("metadata_dir_type") == "str":
            params["metadata_dir"] = str(metadata_dir)
            logger.debug(f"metadata_dir类型: str")
        else:
            params["metadata_dir"] = metadata_dir
            logger.debug(f"metadata_dir类型: Path")
        
        logger.info(f"步骤 {step_name} 适配完成，参数: {list(params.keys())}")
        return params
    
    # 保持向后兼容的方法
    def adapt_step1_outline(self, srt_path: Path) -> Dict[str, Any]:
        """适配Step1: 大纲提取"""
        return self.adapt_step("step1_outline", srt_path=srt_path)
    
    def adapt_step2_timeline(self) -> Dict[str, Any]:
        """适配Step2: 时间线提取"""
        return self.adapt_step("step2_timeline")
    
    def adapt_step3_scoring(self) -> Dict[str, Any]:
        """适配Step3: 评分"""
        return self.adapt_step("step3_scoring")
    
    def adapt_step4_title(self) -> Dict[str, Any]:
        """适配Step4: 标题生成"""
        return self.adapt_step("step4_title")
    
    def adapt_step5_clustering(self) -> Dict[str, Any]:
        """适配Step5: 聚类"""
        return self.adapt_step("step5_clustering")
    
    def adapt_step6_video(self) -> Dict[str, Any]:
        """适配Step6: 视频生成"""
        return self.adapt_step("step6_video")
    
    def get_step_result(self, step_name: str) -> Any:
        """获取步骤执行结果"""
        output_path = self.get_step_output_path(step_name)
        result = self._load_json(output_path)
        logger.debug(f"获取步骤 {step_name} 结果: {'成功' if result else '失败'}")
        return result
    
    def get_pipeline_cache_info(self) -> Dict[str, Any]:
        """获取流水线缓存信息"""
        steps = [
            "step1_outline", "step2_timeline", "step3_scoring",
            "step4_title", "step5_clustering", "step6_video"
        ]
        
        cache_info = {}
        for step in steps:
            cache_info[step] = self.get_step_cache_info(step)
        
        return cache_info
    
    def get_project_size_info(self) -> Dict[str, Any]:
        """获取项目大小信息"""
        return self.path_manager.get_project_size_info()
    
    def cleanup_all_intermediate_files(self):
        """清理所有步骤的中间文件"""
        steps = [
            "step1_outline", "step2_timeline", "step3_scoring",
            "step4_title", "step5_clustering", "step6_video"
        ]
        
        for step in steps:
            self.cleanup_intermediate_files(step)
        
        logger.info("已清理所有步骤的中间文件")
    
    def cleanup_intermediate_files(self, step_name: str):
        """清理步骤的中间文件"""
        self.path_manager.cleanup_step_files(step_name, keep_output=True)
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线执行状态"""
        status = {}
        steps = [
            "step1_outline", "step2_timeline", "step3_scoring",
            "step4_title", "step5_clustering", "step6_video"
        ]
        
        for step in steps:
            output_path = self.get_step_output_path(step)
            status[step] = {
                "completed": output_path.exists(),
                "output_path": str(output_path),
                "file_size": output_path.stat().st_size if output_path.exists() else 0
            }
        
        return status
    
    def validate_pipeline_prerequisites(self) -> List[str]:
        """验证流水线前置条件"""
        errors = []
        
        # 检查路径有效性
        path_errors = self.path_manager.validate_paths()
        errors.extend(path_errors)
        
        # 检查SRT文件
        srt_path = self.path_manager.get_srt_path()
        if not srt_path.exists():
            errors.append(f"SRT文件不存在: {srt_path}")
        
        # 检查LLM配置
        try:
            self.config_manager.get_llm_config()
        except ValueError as e:
            errors.append(str(e))
        
        return errors 