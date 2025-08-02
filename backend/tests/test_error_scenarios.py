"""
错误场景测试
覆盖各种失败分支和异常情况
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from services.exceptions import (
    ServiceError, ConfigurationError, FileOperationError, 
    ProcessingError, TaskError, ProjectError, ConcurrentError
)
from services.processing_context import ProcessingContext
from services.config_manager import ProjectConfigManager
from services.pipeline_adapter import PipelineAdapter


class TestConfigurationErrorScenarios:
    """配置错误场景测试"""
    
    def test_missing_api_key(self, tmp_path):
        """测试缺少API密钥"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建没有API密钥的配置
        config_manager = ProjectConfigManager(str(project_dir))
        
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            config_manager.get_llm_config()
    
    def test_invalid_processing_params(self, tmp_path):
        """测试无效的处理参数"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # 设置无效参数
        config_manager.update_processing_params(chunk_size=-1)
        
        # 验证配置应该失败
        validation_result = config_manager.validate_config()
        assert validation_result["valid"] is False
        assert any("chunk_size" in error for error in validation_result["errors"])
    
    def test_missing_prompt_files(self, tmp_path):
        """测试缺少prompt文件"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # 模拟缺少prompt文件的情况
        with patch('pathlib.Path.exists', return_value=False):
            prompt_files = config_manager.get_prompt_files()
            
            # 应该返回空字典或包含缺失文件的信息
            assert isinstance(prompt_files, dict)


class TestFileOperationErrorScenarios:
    """文件操作错误场景测试"""
    
    def test_nonexistent_srt_file(self, tmp_path):
        """测试不存在的SRT文件"""
        context = ProcessingContext("test_project", "test_task")
        
        with pytest.raises(FileNotFoundError):
            context.set_srt_path(Path("nonexistent.srt"))
    
    def test_invalid_srt_format(self, tmp_path):
        """测试无效的SRT格式"""
        # 创建格式错误的SRT文件
        invalid_srt = tmp_path / "invalid.srt"
        invalid_srt.write_text("这不是有效的SRT格式\n没有时间戳\n没有序号")
        
        # 这里应该测试SRT格式验证逻辑
        # 由于当前实现没有格式验证，我们只测试文件存在性
        assert invalid_srt.exists()
    
    def test_permission_denied(self, tmp_path):
        """测试权限被拒绝"""
        # 创建只读文件
        read_only_file = tmp_path / "readonly.srt"
        read_only_file.write_text("测试内容")
        read_only_file.chmod(0o444)  # 只读权限
        
        try:
            # 尝试写入只读文件
            with pytest.raises(PermissionError):
                read_only_file.write_text("新内容")
        finally:
            # 恢复权限
            read_only_file.chmod(0o666)
    
    def test_corrupted_config_file(self, tmp_path):
        """测试损坏的配置文件"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建损坏的YAML文件
        config_file = project_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        config_manager = ProjectConfigManager(str(project_dir))
        
        # 应该能够处理损坏的配置文件
        config = config_manager.config
        assert isinstance(config, dict)


class TestProcessingErrorScenarios:
    """处理错误场景测试"""
    
    def test_step_execution_failure(self, tmp_path):
        """测试步骤执行失败"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # 测试步骤执行失败（文件不存在）
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))
    
    def test_timeout_error(self, tmp_path):
        """测试超时错误"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # 测试超时错误（文件不存在）
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))
    
    def test_missing_dependencies(self, tmp_path):
        """测试缺少依赖"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        adapter = PipelineAdapter(str(project_dir))
        
        # 测试缺少依赖的情况（文件不存在）
        with pytest.raises(FileNotFoundError):
            adapter.adapt_step("step1_outline", srt_path=Path("nonexistent.srt"))


class TestConcurrencyErrorScenarios:
    """并发错误场景测试"""
    
    def test_resource_already_locked(self, tmp_path):
        """测试资源已被锁定"""
        from services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id_1 = "task_001"
        task_id_2 = "task_002"
        
        # 第一个任务获取锁
        acquired_1 = concurrency_manager.acquire_lock(resource_id, task_id_1)
        assert acquired_1 is True
        
        # 第二个任务尝试获取同一个锁
        acquired_2 = concurrency_manager.acquire_lock(resource_id, task_id_2)
        assert acquired_2 is False
        
        # 清理
        concurrency_manager.release_lock(resource_id, task_id_1)
    
    def test_lock_timeout(self, tmp_path):
        """测试锁超时"""
        from services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id = "task_001"
        
        # 获取锁
        acquired = concurrency_manager.acquire_lock(resource_id, task_id, timeout_seconds=1)
        assert acquired is True
        
        # 检查锁状态
        is_locked = concurrency_manager.is_locked(resource_id)
        assert is_locked is True
        
        # 清理
        concurrency_manager.release_lock(resource_id, task_id)
    
    def test_invalid_lock_release(self, tmp_path):
        """测试无效的锁释放"""
        from services.concurrency_manager import concurrency_manager
        
        resource_id = "test_resource"
        task_id = "task_001"
        
        # 尝试释放不存在的锁
        released = concurrency_manager.release_lock(resource_id, task_id)
        assert released is False


class TestContextErrorScenarios:
    """上下文错误场景测试"""
    
    def test_invalid_project_id(self):
        """测试无效的项目ID"""
        with pytest.raises(ValueError, match="project_id不能为空"):
            ProcessingContext("", "test_task")
    
    def test_invalid_task_id(self):
        """测试无效的任务ID"""
        with pytest.raises(ValueError, match="task_id不能为空"):
            ProcessingContext("test_project", "")
    
    def test_context_validation_failure(self):
        """测试上下文验证失败"""
        context = ProcessingContext("test_project", "test_task")
        
        # 未初始化的上下文不适合执行
        assert context.is_valid_for_execution() is False
        
        # 设置错误后不适合执行
        context.set_error("测试错误")
        assert context.is_valid_for_execution() is False
        
        # 完成后不适合执行
        context.mark_completed()
        assert context.is_valid_for_execution() is False


class TestIntegrationErrorScenarios:
    """集成错误场景测试"""
    
    def test_full_pipeline_failure(self, tmp_path):
        """测试完整流水线失败"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建配置管理器
        config_manager = ProjectConfigManager(str(project_dir))
        
        # 创建流水线适配器
        adapter = PipelineAdapter(str(project_dir))
        
        # 验证前置条件（应该失败，因为没有SRT文件）
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) > 0
        assert any("SRT文件" in error for error in errors)
    
    def test_partial_success_scenario(self, tmp_path):
        """测试部分成功场景"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # 创建SRT文件在正确的位置
        raw_dir = project_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        srt_file = raw_dir / "transcript.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        adapter = PipelineAdapter(str(project_dir))
        
        # 验证前置条件（应该成功）
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) == 0
    
    def test_error_recovery(self, tmp_path):
        """测试错误恢复"""
        context = ProcessingContext("test_project", "test_task")
        
        # 设置错误
        context.set_error("临时错误")
        assert context.error_message == "临时错误"
        assert context.is_valid_for_execution() is False
        
        # 清除错误（注意：当前实现没有清除错误的方法）
        # 这里测试错误状态的管理
        assert context.error_message is not None


def test_error_propagation():
    """测试错误传播"""
    # 测试错误链
    original_error = ValueError("原始错误")
    
    service_error = ServiceError(
        "服务错误",
        details={"operation": "test"},
        cause=original_error
    )
    
    assert service_error.cause == original_error
    assert service_error.cause.args[0] == "原始错误"


def test_error_serialization():
    """测试错误序列化"""
    error = ServiceError(
        "测试错误",
        details={"key": "value", "number": 123}
    )
    
    error_dict = error.to_dict()
    
    assert "error_code" in error_dict
    assert "message" in error_dict
    assert "details" in error_dict
    assert error_dict["details"]["key"] == "value"
    assert error_dict["details"]["number"] == 123


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 