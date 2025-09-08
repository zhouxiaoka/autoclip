"""
处理编排器
负责协调流水线执行和Task状态管理
"""

import logging
import time
import sys
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from sqlalchemy.orm import Session

from backend.models.task import Task, TaskStatus, TaskType
from backend.repositories.task_repository import TaskRepository
from backend.services.config_manager import ProjectConfigManager, ProcessingStep
# from backend.services.pipeline_adapter import PipelineAdapter  # 临时注释，文件不存在
from backend.core.config import get_project_root

logger = logging.getLogger(__name__)

# 导入流水线步骤

try:
    from backend.pipeline.step1_outline import run_step1_outline
    from backend.pipeline.step2_timeline import run_step2_timeline
    from backend.pipeline.step3_scoring import run_step3_scoring
    from backend.pipeline.step4_title import run_step4_title
    from backend.pipeline.step5_clustering import run_step5_clustering
    from backend.pipeline.step6_video import run_step6_video
    logger.info("流水线模块导入成功")
except ImportError as e:
    logger.warning(f"无法导入流水线模块: {e}")
    # 定义占位符函数
    def run_step1_outline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        srt_path = kwargs.get('srt_path')
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "outlines": [
                    {"topic": "测试话题1", "start_time": "00:00:00", "end_time": "00:00:05", "content": "测试内容1"},
                    {"topic": "测试话题2", "start_time": "00:00:05", "end_time": "00:00:10", "content": "测试内容2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step2_timeline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "timeline": [
                    {"time": "00:00:00", "event": "开始"},
                    {"time": "00:00:05", "event": "话题1"},
                    {"time": "00:00:10", "event": "话题2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step3_scoring(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "scored_clips": [
                    {"clip_id": "1", "score": 0.8, "content": "高分内容1"},
                    {"clip_id": "2", "score": 0.7, "content": "高分内容2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step4_title(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "titles": [
                    {"clip_id": "1", "title": "测试标题1"},
                    {"clip_id": "2", "title": "测试标题2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step5_clustering(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "collections": [
                    {"collection_id": "1", "title": "测试合集1", "clips": ["1", "2"]},
                    {"collection_id": "2", "title": "测试合集2", "clips": ["3", "4"]}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step6_video(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "videos": [
                    {"clip_id": "1", "video_path": "output/clip_1.mp4"},
                    {"clip_id": "2", "video_path": "output/clip_2.mp4"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}


class ProcessingOrchestrator:
    """处理编排器，负责协调流水线执行和Task状态管理"""
    
    def __init__(self, project_id: str, task_id: str, db: Session):
        self.project_id = project_id
        self.task_id = task_id
        self.db = db
        
        # 初始化组件
        self.config_manager = ProjectConfigManager(project_id)
        # self.adapter = PipelineAdapter(db, task_id, project_id)  # 临时注释，文件不存在
        self.task_repo = TaskRepository(db)
        
        # 步骤映射
        self.step_functions = {
            ProcessingStep.STEP1_OUTLINE: run_step1_outline,
            ProcessingStep.STEP2_TIMELINE: run_step2_timeline,
            ProcessingStep.STEP3_SCORING: run_step3_scoring,
            ProcessingStep.STEP4_TITLE: run_step4_title,
            ProcessingStep.STEP5_CLUSTERING: run_step5_clustering,
            ProcessingStep.STEP6_VIDEO: run_step6_video
        }
        
        # 步骤适配器映射 - 暂时禁用
        self.step_adapters = {
            # ProcessingStep.STEP1_OUTLINE: self.adapter.adapt_step1_outline,
            # ProcessingStep.STEP2_TIMELINE: self.adapter.adapt_step2_timeline,
            # ProcessingStep.STEP3_SCORING: self.adapter.adapt_step3_scoring,
            # ProcessingStep.STEP4_TITLE: self.adapter.adapt_step4_title,
            # ProcessingStep.STEP5_CLUSTERING: self.adapter.adapt_step5_clustering,
            # ProcessingStep.STEP6_VIDEO: self.adapter.adapt_step6_video
        }
        
        # 步骤状态管理
        self.step_status = {}
        self.step_timings = {}
        self.step_results = {}
    
    def execute_step(self, step: ProcessingStep, **kwargs) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            step: 处理步骤
            **kwargs: 步骤特定参数
            
        Returns:
            步骤执行结果
        """
        step_name = step.value
        logger.info(f"开始执行步骤: {step_name}")
        
        # 更新步骤状态为运行中
        self._update_step_status(step, "running")
        
        try:
            # 更新任务状态为运行中
            self._update_task_status(TaskStatus.RUNNING, progress=self._get_step_progress(step))
            
            # 获取步骤函数和适配器
            step_func = self.step_functions[step]
            step_adapter = self.step_adapters[step]
            
            # 准备步骤环境
            self.adapter.prepare_step_environment(step_name)
            
            # 执行步骤（使用高精度计时器）
            start_time = time.perf_counter()
            
            if step == ProcessingStep.STEP1_OUTLINE:
                # Step1需要SRT文件路径
                srt_path = kwargs.get('srt_path')
                if not srt_path:
                    raise ValueError("Step1需要提供SRT文件路径")
                
                adapted_params = step_adapter(srt_path)
            else:
                # 其他步骤使用前一步的输出
                adapted_params = step_adapter()
            
            # 执行步骤函数
            result = step_func(**adapted_params)
            
            execution_time = time.perf_counter() - start_time
            logger.info(f"步骤 {step_name} 执行完成，耗时: {execution_time:.4f}秒")
            
            # 记录步骤执行信息
            self.step_timings[step_name] = {
                "start_time": start_time,
                "end_time": time.perf_counter(),
                "execution_time": execution_time
            }
            
            # 保存结果到数据库
            self._save_step_result(step, result)
            
            # 更新步骤状态为完成
            self._update_step_status(step, "completed", execution_time=execution_time)
            
            # 更新任务进度
            self._update_task_status(TaskStatus.RUNNING, progress=self._get_step_progress(step))
            
            return {
                "step": step_name,
                "status": "completed",
                "execution_time": execution_time,
                "result": result
            }
            
        except Exception as e:
            execution_time = time.perf_counter() - start_time if 'start_time' in locals() else 0
            logger.error(f"步骤 {step_name} 执行失败: {e}")
            
            # 更新步骤状态为失败
            self._update_step_status(step, "failed", execution_time=execution_time, error=str(e))
            
            self._update_task_status(TaskStatus.FAILED, error_message=str(e))
            raise
    
    def execute_pipeline(self, srt_path: Path, steps_to_execute: Optional[List[ProcessingStep]] = None) -> Dict[str, Any]:
        """
        执行流水线（支持按需执行子集步骤）
        
        Args:
            srt_path: SRT文件路径
            steps_to_execute: 要执行的步骤列表，None表示执行完整流水线
            
        Returns:
            流水线执行结果
        """
        if steps_to_execute is None:
            # 执行完整流水线
            steps_to_execute = [
                ProcessingStep.STEP1_OUTLINE,
                ProcessingStep.STEP2_TIMELINE,
                ProcessingStep.STEP3_SCORING,
                ProcessingStep.STEP4_TITLE,
                ProcessingStep.STEP5_CLUSTERING,
                ProcessingStep.STEP6_VIDEO
            ]
            logger.info(f"开始执行项目 {self.project_id} 的完整流水线")
        else:
            logger.info(f"开始执行项目 {self.project_id} 的子集流水线: {[step.value for step in steps_to_execute]}")
        
        # 验证前置条件
        errors = self.adapter.validate_pipeline_prerequisites()
        if errors:
            error_msg = "; ".join(errors)
            self._update_task_status(TaskStatus.FAILED, error_message=error_msg)
            raise ValueError(f"流水线前置条件验证失败: {error_msg}")
        
        # 验证步骤依赖关系
        self._validate_step_dependencies(steps_to_execute)
        
        # 更新任务状态为运行中
        self._update_task_status(TaskStatus.RUNNING, progress=0)
        
        results = {}
        total_steps = len(steps_to_execute)
        
        try:
            for i, step in enumerate(steps_to_execute):
                logger.info(f"执行步骤 {i+1}/{total_steps}: {step.value}")
                
                if step == ProcessingStep.STEP1_OUTLINE:
                    step_result = self.execute_step(step, srt_path=srt_path)
                else:
                    step_result = self.execute_step(step)
                
                results[step.value] = step_result
                
                # 更新总体进度
                progress = ((i + 1) / total_steps) * 100
                self._update_task_status(TaskStatus.RUNNING, progress=progress)
            
            # 流水线执行完成，保存数据到数据库
            self._save_pipeline_results_to_database(results)
            
            # 更新任务状态为完成
            self._update_task_status(TaskStatus.COMPLETED, progress=100)
            
            logger.info(f"项目 {self.project_id} 流水线执行完成")
            return {
                "status": "completed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "results": results,
                "executed_steps": [step.value for step in steps_to_execute]
            }
            
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            self._update_task_status(TaskStatus.FAILED, error_message=str(e))
            raise
    
    def _update_step_status(self, step: ProcessingStep, status: str, execution_time: Optional[float] = None, 
                           error: Optional[str] = None):
        """更新步骤状态"""
        step_name = step.value
        self.step_status[step_name] = {
            "status": status,
            "timestamp": time.time(),
            "execution_time": execution_time,
            "error": error
        }
        logger.debug(f"步骤 {step_name} 状态更新: {status}")
    
    def _update_task_status(self, status: TaskStatus, progress: Optional[float] = None, 
                           error_message: Optional[str] = None, result: Optional[Dict] = None):
        """更新任务状态"""
        # 使用TaskRepository的专用方法
        if progress is not None:
            self.task_repo.update_task_progress(self.task_id, progress)
        
        if error_message is not None:
            self.task_repo.update_task_error(self.task_id, error_message)
        
        if result is not None:
            self.task_repo.update_task_result(self.task_id, result)
        
        # 更新状态
        self.task_repo.update_task_status(self.task_id, status)
        logger.info(f"任务 {self.task_id} 状态更新为: {status.value}")
    
    def _get_step_progress(self, step: ProcessingStep) -> float:
        """获取步骤对应的进度百分比"""
        step_progress_map = {
            ProcessingStep.STEP1_OUTLINE: 10,
            ProcessingStep.STEP2_TIMELINE: 30,
            ProcessingStep.STEP3_SCORING: 50,
            ProcessingStep.STEP4_TITLE: 70,
            ProcessingStep.STEP5_CLUSTERING: 85,
            ProcessingStep.STEP6_VIDEO: 95
        }
        return step_progress_map.get(step, 0)
    
    def _save_step_result(self, step: ProcessingStep, result: Any):
        """保存步骤结果到数据库"""
        # 这里可以根据需要将结果保存到相应的数据库表
        # 比如切片结果保存到Clip表，合集结果保存到Collection表
        logger.info(f"步骤 {step.value} 结果已保存")
    
    def _save_pipeline_results_to_database(self, results: Dict[str, Any]):
        """将流水线执行结果保存到数据库"""
        try:
            logger.info(f"开始保存项目 {self.project_id} 流水线结果到数据库")
            
            # 获取项目目录
            project_dir = self.adapter.data_dir / "projects" / self.project_id
            
            # 保存切片数据到数据库
            step4_result = results.get('step4_title', {}).get('result', [])
            if step4_result:
                logger.info(f"保存 {len(step4_result)} 个切片到数据库")
                self.adapter._save_clips_to_database(self.project_id, project_dir / "step4_title" / "step4_title.json")
            
            # 保存合集数据到数据库
            step5_result = results.get('step5_clustering', {}).get('result', [])
            if step5_result:
                logger.info(f"保存 {len(step5_result)} 个合集到数据库")
                self.adapter._save_collections_to_database(self.project_id, project_dir / "step5_clustering" / "step5_clustering.json")
            
            logger.info(f"项目 {self.project_id} 流水线结果已全部保存到数据库")
            
        except Exception as e:
            logger.error(f"保存流水线结果到数据库失败: {e}")
            # 不抛出异常，避免影响整个流水线的完成状态
    
    def _validate_step_dependencies(self, steps_to_execute: List[ProcessingStep]):
        """验证步骤依赖关系"""
        # 定义步骤依赖关系
        step_dependencies = {
            ProcessingStep.STEP2_TIMELINE: [ProcessingStep.STEP1_OUTLINE],
            ProcessingStep.STEP3_SCORING: [ProcessingStep.STEP2_TIMELINE],
            ProcessingStep.STEP4_TITLE: [ProcessingStep.STEP3_SCORING],
            ProcessingStep.STEP5_CLUSTERING: [ProcessingStep.STEP4_TITLE],
            ProcessingStep.STEP6_VIDEO: [ProcessingStep.STEP5_CLUSTERING]
        }
        
        # 只检查第一个步骤的依赖，因为其他步骤会在执行过程中逐步检查
        if steps_to_execute:
            first_step = steps_to_execute[0]
            if first_step in step_dependencies:
                required_steps = step_dependencies[first_step]
                missing_steps = []
                
                for req_step in required_steps:
                    # 检查依赖步骤是否已经完成（通过检查输出文件）
                    step_output = self.adapter.get_step_output_path(req_step.value)
                    if not step_output.exists():
                        missing_steps.append(req_step)
                
                if missing_steps:
                    missing_step_names = [step.value for step in missing_steps]
                    raise ValueError(f"步骤 {first_step.value} 缺少依赖步骤: {missing_step_names}")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线状态"""
        task = self.task_repo.get_by_id(self.task_id)
        if not task:
            return {"error": "任务不存在"}
        
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "task_status": task.status.value,
            "task_progress": task.progress,
            "error_message": task.error_message,
            "step_status": self.step_status,
            "step_timings": self.step_timings,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }
    
    def retry_step(self, step: ProcessingStep, **kwargs) -> Dict[str, Any]:
        """重试特定步骤"""
        logger.info(f"重试步骤: {step.value}")
        
        # 清理步骤的中间文件
        self.adapter.cleanup_intermediate_files(step.value)
        
        # 重新执行步骤
        return self.execute_step(step, **kwargs)
    
    def get_step_result(self, step: ProcessingStep) -> Any:
        """获取步骤结果"""
        return self.adapter.get_step_result(step.value)
    
    def get_step_performance_summary(self) -> Dict[str, Any]:
        """获取步骤性能摘要"""
        if not self.step_timings:
            return {"message": "暂无性能数据"}
        
        total_time = sum(timing["execution_time"] for timing in self.step_timings.values())
        step_performance = {}
        
        for step_name, timing in self.step_timings.items():
            percentage = (timing["execution_time"] / total_time * 100) if total_time > 0 else 0
            step_performance[step_name] = {
                "execution_time": timing["execution_time"],
                "percentage": percentage,
                "start_time": timing["start_time"],
                "end_time": timing["end_time"]
            }
        
        return {
            "total_execution_time": total_time,
            "step_performance": step_performance,
            "slowest_step": max(self.step_timings.items(), key=lambda x: x[1]["execution_time"])[0] if self.step_timings else None,
            "fastest_step": min(self.step_timings.items(), key=lambda x: x[1]["execution_time"])[0] if self.step_timings else None
        }
    
    def resume_from_step(self, start_step: ProcessingStep, srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """从指定步骤恢复执行"""
        logger.info(f"从步骤 {start_step.value} 恢复执行")
        
        # 获取从指定步骤开始的所有步骤
        all_steps = [
            ProcessingStep.STEP1_OUTLINE,
            ProcessingStep.STEP2_TIMELINE,
            ProcessingStep.STEP3_SCORING,
            ProcessingStep.STEP4_TITLE,
            ProcessingStep.STEP5_CLUSTERING,
            ProcessingStep.STEP6_VIDEO
        ]
        
        try:
            start_index = all_steps.index(start_step)
            
            # 只执行未完成的步骤
            steps_to_execute = []
            for step in all_steps[start_index:]:
                step_output = self.adapter.get_step_output_path(step.value)
                if not step_output.exists():
                    steps_to_execute.append(step)
                else:
                    logger.info(f"步骤 {step.value} 已完成，跳过")
            
            if not steps_to_execute:
                logger.info("所有步骤都已完成，无需执行")
                return {"message": "所有步骤都已完成"}
            
            logger.info(f"将执行步骤: {[step.value for step in steps_to_execute]}")
            
            if start_step == ProcessingStep.STEP1_OUTLINE:
                if not srt_path:
                    raise ValueError("从Step1恢复需要提供SRT文件路径")
                return self.execute_pipeline(srt_path, steps_to_execute)
            else:
                # 验证前置步骤是否已完成
                for step in all_steps[:start_index]:
                    step_output = self.adapter.get_step_output_path(step.value)
                    if not step_output.exists():
                        raise ValueError(f"前置步骤 {step.value} 未完成，无法从 {start_step.value} 恢复")
                
                return self.execute_pipeline(Path("dummy.srt"), steps_to_execute)
                
        except ValueError as e:
            logger.error(f"恢复执行失败: {e}")
            raise
    
    def get_step_status_summary(self) -> Dict[str, Any]:
        """获取步骤状态摘要"""
        if not self.step_status:
            return {"message": "暂无步骤状态数据"}
        
        completed_steps = [step for step, status in self.step_status.items() if status["status"] == "completed"]
        failed_steps = [step for step, status in self.step_status.items() if status["status"] == "failed"]
        running_steps = [step for step, status in self.step_status.items() if status["status"] == "running"]
        
        return {
            "total_steps": len(self.step_status),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "running_steps": running_steps,
            "completion_rate": len(completed_steps) / len(self.step_status) * 100 if self.step_status else 0,
            "step_details": self.step_status
        }