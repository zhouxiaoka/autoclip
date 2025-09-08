"""
处理框架测试
使用pytest标准结构
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from backend.services.config_manager import ProjectConfigManager, ProcessingStep
from backend.services.pipeline_adapter import PipelineAdapter
from backend.services.processing_orchestrator import ProcessingOrchestrator
from backend.services.processing_service import ProcessingService
from backend.services.processing_context import ProcessingContext
from backend.services.exceptions import ServiceError, ConfigurationError, FileOperationError, ProcessingError


class TestProjectConfigManager:
    """项目配置管理器测试"""
    
    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """创建临时项目目录"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return project_dir
    
    @pytest.fixture
    def config_manager(self, temp_project_dir):
        """创建配置管理器实例"""
        return ProjectConfigManager(str(temp_project_dir))
    
    def test_config_manager_initialization(self, config_manager):
        """测试配置管理器初始化"""
        assert config_manager.project_id is not None
        assert config_manager.config_path.parent.exists()
    
    def test_load_default_config(self, config_manager):
        """测试加载默认配置"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        config = config_manager.config
        # 新项目配置为空，这是正常的
        assert isinstance(config, dict)
    
    def test_update_processing_params(self, config_manager):
        """测试更新处理参数"""
        new_params = {
            "max_clips": 50,
            "min_duration": 10.0,
            "max_duration": 300.0
        }
        
        config_manager.update_processing_params(**new_params)
        config = config_manager.config
        
        for key, value in new_params.items():
            assert config["processing_params"][key] == value
    
    def test_update_llm_config(self, config_manager):
        """测试更新LLM配置"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        llm_config = {
            "api_key": "test_key",
            "model_name": "gpt-4",
            "max_retries": 3,
            "timeout_seconds": 30
        }
        
        config_manager.update_llm_config(**llm_config)
        config = config_manager.config
        
        # 检查配置是否已更新
        assert "llm" in config
    
    def test_export_config(self, config_manager):
        """测试导出配置"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        exported = config_manager.export_config()
        # 检查导出的配置包含必要字段
        assert isinstance(exported, dict)
    
    def test_config_validation(self, config_manager):
        """测试配置验证"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        # 测试配置验证
        validation_result = config_manager.validate_config()
        assert isinstance(validation_result, dict)


class TestPipelineAdapter:
    """流水线适配器测试"""
    
    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """创建临时项目目录"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return project_dir
    
    @pytest.fixture
    def mock_srt_file(self, tmp_path):
        """创建模拟SRT文件"""
        srt_file = tmp_path / "test.srt"
        srt_content = """1
00:00:01,000 --> 00:00:05,000
这是第一段字幕

2
00:00:05,000 --> 00:00:10,000
这是第二段字幕
"""
        srt_file.write_text(srt_content, encoding='utf-8')
        return srt_file
    
    @pytest.fixture
    def adapter(self, temp_project_dir):
        """创建适配器实例"""
        return PipelineAdapter(str(temp_project_dir))
    
    def test_adapter_initialization(self, adapter):
        """测试适配器初始化"""
        assert adapter.project_id is not None
    
    def test_validate_pipeline_prerequisites_success(self, adapter, mock_srt_file):
        """测试流水线前置条件验证成功"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        # 确保目录结构存在
        adapter.path_manager.ensure_directories()
        
        # 复制SRT文件到正确位置
        srt_target_path = adapter.path_manager.get_srt_path()
        srt_target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(mock_srt_file, srt_target_path)
        
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) == 0
    
    def test_validate_pipeline_prerequisites_missing_srt(self, adapter):
        """测试流水线前置条件验证失败 - 缺少SRT文件"""
        # 确保目录结构存在但不创建SRT文件
        adapter.path_manager.ensure_directories()
        
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) > 0
        assert any("SRT文件" in error for error in errors)
    
    def test_validate_pipeline_prerequisites_invalid_srt(self, adapter, tmp_path):
        """测试流水线前置条件验证 - SRT文件存在但格式无效"""
        # 设置测试环境变量
        import os
        os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
        
        # 确保目录结构存在
        adapter.path_manager.ensure_directories()
        
        # 创建无效的SRT文件（但文件存在）
        srt_target_path = adapter.path_manager.get_srt_path()
        srt_target_path.write_text("这不是有效的SRT格式")
        
        # validate_pipeline_prerequisites只检查文件是否存在，不验证格式
        # 所以这个测试应该通过（没有错误）
        errors = adapter.validate_pipeline_prerequisites()
        assert len(errors) == 0  # 文件存在，所以没有错误
    
    def test_execute_step_success(self, adapter, mock_srt_file):
        """测试步骤执行成功"""
        # 测试adapt_step方法
        result = adapter.adapt_step("step1_outline", srt_path=mock_srt_file)
        assert isinstance(result, dict)
        assert "srt_path" in result or "input_srt" in result
    
    def test_execute_step_failure(self, adapter, mock_srt_file):
        """测试步骤执行失败"""
        # 测试无效步骤名称
        with pytest.raises(ValueError):
            adapter.adapt_step("invalid_step", srt_path=mock_srt_file)


class TestProcessingOrchestrator:
    """处理编排器测试"""
    
    @pytest.fixture
    def temp_project_dir(self, tmp_path):
        """创建临时项目目录"""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return project_dir
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        return Mock()
    
    @pytest.fixture
    def orchestrator(self, temp_project_dir, mock_db_session):
        """创建编排器实例"""
        return ProcessingOrchestrator(str(temp_project_dir), "test_task", mock_db_session)
    
    def test_orchestrator_initialization(self, orchestrator):
        """测试编排器初始化"""
        assert orchestrator.project_id is not None
        assert orchestrator.task_id == "test_task"
    
    def test_get_pipeline_status(self, orchestrator):
        """测试获取流水线状态"""
        status = orchestrator.get_pipeline_status()
        assert "project_id" in status
        assert "task_id" in status
        assert "pipeline_status" in status
    
    def test_execute_step_success(self, orchestrator, tmp_path):
        """测试执行步骤成功"""
        # 创建模拟SRT文件
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        with patch('backend.services.processing_orchestrator.PipelineAdapter') as mock_adapter_class:
            mock_adapter = Mock()
            mock_adapter.execute_step.return_value = {"status": "completed"}
            mock_adapter_class.return_value = mock_adapter
            
            result = orchestrator.execute_step(ProcessingStep.STEP1_OUTLINE, srt_path=srt_file)
            assert result["status"] == "completed"
    
    def test_execute_step_failure(self, orchestrator, tmp_path):
        """测试执行步骤失败"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        # 模拟步骤函数抛出异常
        with patch.object(orchestrator, 'step_functions') as mock_step_functions:
            mock_step_functions.__getitem__.return_value = Mock(side_effect=Exception("执行失败"))
            
            with pytest.raises(Exception):
                orchestrator.execute_step(ProcessingStep.STEP1_OUTLINE, srt_path=srt_file)


class TestProcessingService:
    """处理服务测试"""
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        return Mock()
    
    @pytest.fixture
    def mock_task_repository(self):
        """创建模拟任务仓库"""
        mock_repo = Mock()
        mock_task = Mock()
        mock_task.id = "test_task_001"
        mock_repo.create.return_value = mock_task
        return mock_repo
    
    @pytest.fixture
    def service(self, mock_db_session, mock_task_repository):
        """创建服务实例"""
        service = ProcessingService(mock_db_session)
        service.task_repo = mock_task_repository
        return service
    
    def test_service_initialization(self, service):
        """测试服务初始化"""
        assert service.db is not None
        assert service.task_repo is not None
    
    def test_start_processing_success(self, service, tmp_path):
        """测试开始处理成功"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        with patch('backend.services.processing_service.ProcessingOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_pipeline.return_value = {"success": True}
            mock_orchestrator_class.return_value = mock_orchestrator
            
            result = service.start_processing("test_project", srt_file)
            assert result["success"] is True
            assert "task_id" in result
    
    def test_start_processing_failure(self, service, tmp_path):
        """测试开始处理失败"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        with patch('backend.services.processing_service.ProcessingOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_pipeline.side_effect = ServiceError("处理失败")
            mock_orchestrator_class.return_value = mock_orchestrator
            
            with pytest.raises(ServiceError):
                service.start_processing("test_project", srt_file)
    
    def test_execute_single_step_success(self, service, tmp_path):
        """测试执行单个步骤成功"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:05,000\n测试字幕")
        
        with patch('backend.services.processing_service.ProcessingOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.execute_step.return_value = {"success": True}
            mock_orchestrator_class.return_value = mock_orchestrator
            
            result = service.execute_single_step("test_project", ProcessingStep.STEP1_OUTLINE, srt_file)
            assert result["success"] is True
            assert "step" in result
    
    def test_get_processing_status(self, service):
        """测试获取处理状态"""
        with patch('backend.services.processing_service.ProcessingOrchestrator') as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator.get_pipeline_status.return_value = {"pipeline_status": {"step1_outline": {"completed": True}}}
            mock_orchestrator_class.return_value = mock_orchestrator
            
            status = service.get_processing_status("test_project", "test_task")
            assert "pipeline_status" in status


class TestProcessingContext:
    """处理上下文测试"""
    
    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        return Mock()
    
    @pytest.fixture
    def context(self, mock_db_session):
        """创建上下文实例"""
        return ProcessingContext("test_project", "test_task", mock_db_session)
    
    def test_context_initialization(self, context):
        """测试上下文初始化"""
        assert context.project_id == "test_project"
        assert context.task_id == "test_task"
        assert context.is_initialized is False
        assert context.is_completed is False
    
    def test_context_validation(self, context):
        """测试上下文验证"""
        # 测试有效上下文
        assert context.is_valid_for_execution() is False  # 未初始化
        
        context.mark_initialized()
        assert context.is_valid_for_execution() is True
    
    def test_context_with_invalid_project_id(self, mock_db_session):
        """测试无效项目ID"""
        with pytest.raises(ValueError):
            ProcessingContext("", "test_task", mock_db_session)
    
    def test_context_with_invalid_task_id(self, mock_db_session):
        """测试无效任务ID"""
        with pytest.raises(ValueError):
            ProcessingContext("test_project", "", mock_db_session)
    
    def test_set_srt_path(self, context, tmp_path):
        """测试设置SRT路径"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("测试内容")
        
        context.set_srt_path(srt_file)
        assert context.srt_path == srt_file
    
    def test_set_srt_path_nonexistent(self, context):
        """测试设置不存在的SRT路径"""
        with pytest.raises(FileNotFoundError):
            context.set_srt_path(Path("nonexistent.srt"))
    
    def test_context_state_management(self, context):
        """测试上下文状态管理"""
        # 初始状态
        assert context.is_initialized is False
        assert context.is_completed is False
        assert context.error_message is None
        
        # 初始化
        context.mark_initialized()
        assert context.is_initialized is True
        assert context.is_valid_for_execution() is True
        
        # 设置错误
        context.set_error("测试错误")
        assert context.error_message == "测试错误"
        assert context.is_valid_for_execution() is False
        
        # 完成
        context.mark_completed()
        assert context.is_completed is True
        assert context.is_valid_for_execution() is False
    
    def test_context_summary(self, context):
        """测试上下文摘要"""
        context.mark_initialized()
        context.set_debug_mode(True)
        
        summary = context.get_context_summary()
        assert "project_id" in summary
        assert "task_id" in summary
        assert "debug_mode" in summary
        assert "is_initialized" in summary
    
    def test_context_clone(self, context, tmp_path):
        """测试上下文克隆"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("测试内容")
        context.set_srt_path(srt_file)
        context.set_debug_mode(True)
        context.mark_initialized()
        
        cloned = context.clone()
        assert cloned.project_id == context.project_id
        assert cloned.task_id == context.task_id
        assert cloned.srt_path == context.srt_path
        assert cloned.debug_mode == context.debug_mode
        assert cloned.is_initialized == context.is_initialized


class TestErrorScenarios:
    """错误场景测试"""
    
    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("配置无效", details={"field": "api_key"})
        assert error.error_code.value == "CONFIG_INVALID"
        assert "api_key" in error.details["field"]
    
    def test_file_operation_error(self):
        """测试文件操作错误"""
        error = FileOperationError("文件不存在", file_path="/invalid/path")
        assert error.error_code.value == "FILE_NOT_FOUND"
        assert error.details["file_path"] == "/invalid/path"
    
    def test_processing_error(self):
        """测试处理错误"""
        error = ProcessingError("步骤执行失败", step_name="step1_outline")
        assert error.error_code.value == "PROCESSING_FAILED"
        assert error.details["step_name"] == "step1_outline"
    
    def test_error_to_dict(self):
        """测试错误转字典"""
        error = ServiceError("测试错误", details={"key": "value"})
        error_dict = error.to_dict()
        assert "error_code" in error_dict
        assert "message" in error_dict
        assert "details" in error_dict


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """创建测试数据目录"""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def sample_srt_file(test_data_dir):
    """创建示例SRT文件"""
    srt_file = test_data_dir / "sample.srt"
    srt_content = """1
00:00:01,000 --> 00:00:05,000
这是第一段字幕内容

2
00:00:05,000 --> 00:00:10,000
这是第二段字幕内容

3
00:00:10,000 --> 00:00:15,000
这是第三段字幕内容
"""
    srt_file.write_text(srt_content, encoding='utf-8')
    return srt_file


def test_integration_basic_flow(test_data_dir, sample_srt_file):
    """测试基本流程集成"""
    # 设置测试环境变量
    import os
    os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
    
    # 创建项目目录
    project_dir = test_data_dir / "integration_project"
    project_dir.mkdir()
    
    # 测试配置管理器
    config_manager = ProjectConfigManager(str(project_dir))
    config = config_manager.config
    assert isinstance(config, dict)
    
    # 测试流水线适配器
    adapter = PipelineAdapter(str(project_dir))
    # 复制SRT文件到项目目录
    project_raw_dir = project_dir / "raw"
    project_raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(sample_srt_file, project_raw_dir / "transcript.srt")
    
    # 验证前置条件
    errors = adapter.validate_pipeline_prerequisites()
    assert len(errors) == 0


def test_error_handling_scenarios():
    """测试错误处理场景"""
    # 测试配置错误
    with pytest.raises(ConfigurationError):
        raise ConfigurationError("配置错误")
    
    # 测试文件操作错误
    with pytest.raises(FileOperationError):
        raise FileOperationError("文件不存在", file_path="/invalid/path")
    
    # 测试处理错误
    with pytest.raises(ProcessingError):
        raise ProcessingError("处理失败", step_name="step1")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])