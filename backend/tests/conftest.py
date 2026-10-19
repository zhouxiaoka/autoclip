"""
pytest配置文件
提供共享的fixtures和测试工具
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, MagicMock
import sys
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 测试库放临时目录。默认的 sqlite:///./data/autoclip.db 相对 cwd，
# test_repositories 的 reset_database() 会 drop_all 掉开发者本机的库。
# 必须在任何 backend.core.database 导入之前设置。
_TEST_DB_DIR = tempfile.mkdtemp(prefix="autoclip-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(_TEST_DB_DIR) / 'autoclip.db'}")


def pytest_configure(config):
    config.addinivalue_line("markers", "store_lock: store lock / receipt tests, also run on Windows CI (msvcrt)")
    config.addinivalue_line("markers", "stdlib_only: runtime regression without application dependencies")
    config.addinivalue_line("markers", "own_whisper_status: the test simulates its own Whisper runtime state; skip the default simulated installed Whisper")
    config.addinivalue_line("markers", "reads_whisper_stand_in: the test asserts the conftest stand-in itself")
    config.addinivalue_line("markers", "real_media_probe: run the real preflight material probe (ffprobe / ffmpeg) instead of the placeholder stand-in")
    config.addinivalue_line("markers", "real_hf: compare the snapshot-cache fake with an installed huggingface_hub; skipped when it is not installed")


class _FollowStudioExecutor:
    """Route Studio renders through whatever `jobs.executor` a test installed."""

    def __init__(self, jobs):
        self.jobs = jobs

    def submit(self, *args, **kwargs):
        return self.jobs.executor.submit(*args, **kwargs)


# Every env name the code reads for a Sentry DSN or a PostHog key/host (backend, frontend build, scripts).
TELEMETRY_ENV = ('SENTRY_DSN', 'VITE_PUBLIC_SENTRY_DSN', 'SENTRY_AUTH_TOKEN', 'AUTOCLIP_POSTHOG_KEY', 'AUTOCLIP_POSTHOG_HOST',
                 'VITE_PUBLIC_POSTHOG_KEY', 'VITE_PUBLIC_POSTHOG_HOST', 'POSTHOG_KEY', 'POSTHOG_HOST', 'POSTHOG_PERSONAL_API_KEY')


@pytest.fixture(autouse=True)
def _no_ambient_telemetry(monkeypatch, request):
    # pre #419 : create_app calls init_sentry, which reads SENTRY_DSN from the
    # environment and sets the module-level `_initialized` for the rest of the process.
    # With a DSN in the developer's shell, any create_app test turned the SDK on for real
    # (sending test events) and left `_initialized` True and the SDK client bound, so later
    # "no DSN -> no-op" checks failed. : the same for PostHog the QA, LLM and MCP
    # events post whenever AUTOCLIP_POSTHOG_KEY / VITE_PUBLIC_POSTHOG_KEY is set. Telemetry is
    # off under pytest: tests never inherit a DSN or a key; a test that wants one sets it with
    # monkeypatch (and stubs urlopen), and whatever init_sentry() bound is undone here.
    for name in TELEMETRY_ENV:
        monkeypatch.delenv(name, raising=False)
    if request.node.get_closest_marker("stdlib_only"):
        yield
        return
    from backend.core import sentry_setup
    monkeypatch.setattr(sentry_setup, "_initialized", False)
    try:
        import sentry_sdk
    except ImportError:
        yield
        return
    scope = sentry_sdk.get_global_scope()
    client = scope.client
    yield
    if scope.client is not client:
        scope.set_client(client)  # unbind whatever init_sentry() bound during the test


@pytest.fixture(autouse=True)
def _studio_render_follows_executor(monkeypatch):
    # Tests stub `jobs.executor` to run work inline; keep renders on that stub instead of
    # the real background render worker. Tests that target `render_executor` override this.
    jobs = sys.modules.get("backend.services.studio.jobs")
    if jobs is not None:
        monkeypatch.setattr(jobs, "render_executor", _FollowStudioExecutor(jobs))
    yield


@pytest.fixture(autouse=True)
def _qa_stays_off_for_unrelated_renders(monkeypatch, request):
    # Shadow QA is queued after every completed render. Other suites must not
    # spawn that worker; test_studio_qa covers the real path.
    if request.node.get_closest_marker("stdlib_only"):
        yield
        return
    name = getattr(request.node.module, "__name__", "")
    if name.endswith("test_studio_qa"):
        yield
        return
    monkeypatch.setenv("AUTOCLIP_QA_DISABLED", "1")
    yield


@pytest.fixture(autouse=True)
def _isolated_branding_settings(tmp_path, monkeypatch, request):
    if request.node.get_closest_marker("stdlib_only"):
        return
    from backend.services import output_branding, output_captions
    monkeypatch.setattr(output_branding, 'settings_path', lambda: tmp_path / 'output-branding.json')
    monkeypatch.setattr(output_captions, 'settings_path', lambda: tmp_path / 'output-captions.json')


@pytest.fixture(autouse=True)
def _no_framing_install(monkeypatch, request):
    # Automatic output starts the on-demand OpenCV install; tests must never run pip.
    if not request.node.get_closest_marker("stdlib_only"):
        from backend.services.studio import framing
        monkeypatch.setattr(framing, "start_install", lambda index_url=None: {"started": False, "message": "test"})
    yield

def _called_from_test_code(depth: int = 2) -> bool:
    """True when the stand-in was called directly by test code (a tests/ module), not by product code."""
    filename = Path(sys._getframe(depth).f_code.co_filename).resolve()
    return _TESTS_DIR in filename.parents


_TESTS_DIR = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _whisper_installed_by_default(monkeypatch, request):
    # 1.5.7 #115: with no settings document the import gate assumes the default local Whisper.
    # CI has no Whisper, so every suite runs with "local Whisper installed, model on disk" simulated;
    # the gate code itself still runs everywhere and passes because its condition is not met.
    # Tests that exercise the Whisper state functions themselves carry @pytest.mark.own_whisper_status.
    # detected at runtime, whatever the import style or directory: if test code calls the
    # stand-in directly and the test is not marked, the test fails here instead of passing on the stand-in.
    if request.node.get_closest_marker("stdlib_only") or request.node.get_closest_marker("own_whisper_status"):
        yield
        return
    from backend.services import whisper_runtime
    from backend.services.studio import readiness
    direct = []
    allowed = request.node.get_closest_marker("reads_whisper_stand_in") is not None

    def get_status(*a, **k):
        if not allowed and _called_from_test_code():
            direct.append("whisper_runtime.get_status")
        return {"status": "installed"}

    def whisper_model(name):
        if not allowed and _called_from_test_code():
            direct.append("readiness._whisper_model")
        return {"ok": True, "code": "whisper_installed"}
    monkeypatch.setattr(whisper_runtime, "get_status", get_status)
    monkeypatch.setattr(readiness, "_whisper_model", whisper_model)
    yield
    if direct:
        pytest.fail(f"{request.node.nodeid} calls {sorted(set(direct))} directly but reads the conftest stand-in; "
                    "mark it @pytest.mark.own_whisper_status and simulate the state it needs (R21 #176)", pytrace=False)

@pytest.fixture(autouse=True)
def _placeholder_media_is_readable(monkeypatch, request):
    # #418 rewrite: every entry now probes the source before anything else. Most suites use placeholder bytes
    # as "a video"; they get a readable 60 s source with audio. Tests about the source itself (and the #418
    # acceptance tests) carry @pytest.mark.real_media_probe and run the real ffprobe / ffmpeg probe.
    if request.node.get_closest_marker("stdlib_only") or request.node.get_closest_marker("real_media_probe"):
        yield
        return
    try:
        from backend.services.studio import preflight
    except Exception:  # noqa: BLE001
        yield
        return
    monkeypatch.setattr(preflight, "probe_material",
                        lambda video: preflight.MaterialProbe(preflight.ProbeState.READABLE, video, 60.0, True, ffprobe_runs=1))
    # A caller's own ffprobe that found no duration (fake bytes) finishes as the same readable stand-in (#351).
    monkeypatch.setattr(preflight, "_after_ffprobe",
                        lambda path, duration, audio, width, height, stderr='': preflight.MaterialProbe(
                            preflight.ProbeState.READABLE, path, duration or 60.0, True if audio is None else audio, width, height, ffprobe_runs=1))
    yield


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


@pytest.fixture
def mock_db_session():
    """创建模拟数据库会话"""
    session = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.close = Mock()
    return session


@pytest.fixture
def mock_task_repository():
    """创建模拟任务仓库"""
    mock_repo = Mock()
    mock_task = Mock()
    mock_task.id = "test_task_001"
    mock_task.project_id = "test_project"
    mock_task.status = Mock(value="pending")
    mock_task.progress = 0.0
    mock_task.metadata = {}
    mock_repo.create.return_value = mock_task
    mock_repo.get_by_id.return_value = mock_task
    return mock_repo


@pytest.fixture
def temp_project_dir(tmp_path):
    """创建临时项目目录"""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def mock_srt_file(tmp_path):
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
def invalid_srt_file(tmp_path):
    """创建无效的SRT文件"""
    srt_file = tmp_path / "invalid.srt"
    srt_file.write_text("这不是有效的SRT格式")
    return srt_file


@pytest.fixture
def mock_config():
    """创建模拟配置"""
    return {
        "processing_params": {
            "max_clips": 50,
            "min_duration": 10.0,
            "max_duration": 300.0
        },
        "llm": {
            "api_key": "test_api_key",
            "model_name": "qwen-plus",
            "max_retries": 3,
            "timeout_seconds": 30
        },
        "prompts": {
            "custom_paths": {}
        }
    }


@pytest.fixture
def mock_pipeline_result():
    """创建模拟流水线结果"""
    return {
        "success": True,
        "output_files": {
            "outline": "outline.json",
            "timeline": "timeline.json",
            "scoring": "scoring.json"
        },
        "statistics": {
            "total_clips": 10,
            "processed_clips": 8,
            "failed_clips": 2
        }
    }


@pytest.fixture
def mock_orchestrator_status():
    """创建模拟编排器状态"""
    return {
        "project_id": "test_project",
        "task_id": "test_task",
        "status": "running",
        "progress": 50.0,
        "current_step": "step2_timeline",
        "steps": {
            "step1_outline": {"status": "completed", "duration": 30.5},
            "step2_timeline": {"status": "running", "duration": 15.2},
            "step3_scoring": {"status": "pending", "duration": 0.0}
        },
        "error_message": None
    }


class TestDataManager:
    """测试数据管理器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.created_files = []
        self.created_dirs = []
    
    def create_srt_file(self, name: str, content: Optional[str] = None) -> Path:
        """创建SRT文件"""
        if content is None:
            content = f"""1
00:00:01,000 --> 00:00:05,000
{name} 第一段字幕

2
00:00:05,000 --> 00:00:10,000
{name} 第二段字幕
"""
        
        srt_file = self.base_dir / f"{name}.srt"
        srt_file.write_text(content, encoding='utf-8')
        self.created_files.append(srt_file)
        return srt_file
    
    def create_project_structure(self, project_id: str) -> Path:
        """创建项目目录结构"""
        project_dir = self.base_dir / project_id
        project_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        subdirs = ["srt", "output", "logs", "temp"]
        for subdir in subdirs:
            (project_dir / subdir).mkdir(exist_ok=True)
            self.created_dirs.append(project_dir / subdir)
        
        self.created_dirs.append(project_dir)
        return project_dir
    
    def create_config_file(self, project_dir: Path, config: dict) -> Path:
        """创建配置文件"""
        config_file = project_dir / "config.yaml"
        import yaml
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        self.created_files.append(config_file)
        return config_file
    
    def cleanup(self):
        """清理创建的测试数据"""
        for file_path in self.created_files:
            if file_path.exists():
                file_path.unlink()
        
        for dir_path in reversed(self.created_dirs):
            if dir_path.exists():
                shutil.rmtree(dir_path)


@pytest.fixture
def test_data_manager(tmp_path):
    """创建测试数据管理器"""
    manager = TestDataManager(tmp_path)
    yield manager
    manager.cleanup()


def assert_file_exists(file_path: Path, description: str = ""):
    """断言文件存在"""
    assert file_path.exists(), f"文件不存在: {file_path} {description}"


def assert_file_content(file_path: Path, expected_content: str, description: str = ""):
    """断言文件内容"""
    assert_file_exists(file_path, description)
    actual_content = file_path.read_text(encoding='utf-8')
    assert actual_content.strip() == expected_content.strip(), \
        f"文件内容不匹配: {file_path} {description}"


def assert_dict_contains(dict_obj: dict, expected_keys: list, description: str = ""):
    """断言字典包含指定键"""
    for key in expected_keys:
        assert key in dict_obj, f"字典缺少键: {key} {description}"


def assert_error_contains(error: Exception, expected_message: str, description: str = ""):
    """断言错误信息包含指定内容"""
    assert expected_message in str(error), \
        f"错误信息不包含预期内容: {expected_message} {description}"
