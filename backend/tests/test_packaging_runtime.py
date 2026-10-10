"""高级包装组件：按需安装、系统浏览器优先、缺组件时退回 classic。"""
import io
import os
from pathlib import Path

import pytest

from backend.services import packaging_runtime as runtime


class _Proc:
    def __init__(self, code=0, lines=None):
        self.returncode = None
        self._code = code
        self.stdout = io.StringIO("\n".join(lines or ["Collecting playwright", "Successfully installed playwright"]) + "\n")

    def wait(self):
        self.returncode = self._code
        return self._code


@pytest.fixture(autouse=True)
def isolate_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "_data_dir", lambda: tmp_path)
    for key in ("PLAYWRIGHT_DOWNLOAD_HOST", "AUTOCLIP_PLAYWRIGHT_DOWNLOAD_HOST", "AUTOCLIP_PLAYWRIGHT_MIRROR", "PIP_INDEX_URL", "PLAYWRIGHT_BROWSERS_PATH"):
        monkeypatch.delenv(key, raising=False)
    runtime._runtime_import_error = ""
    runtime._set_state(status="unknown", progress=0, message="", log_tail="")
    yield
    runtime._runtime_import_error = ""
    runtime._set_state(status="unknown", progress=0, message="", log_tail="")
    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    os.environ.pop("PLAYWRIGHT_DOWNLOAD_HOST", None)


def _install_package(tmp_path):
    package = tmp_path / "packaging-runtime" / "playwright"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# test stub\n", encoding="utf-8")
    return package


def test_install_dir_is_under_the_data_directory(tmp_path):
    assert runtime.install_root() == tmp_path / "packaging-runtime"
    assert runtime.get_install_dir() == tmp_path / "packaging-runtime"
    assert runtime.get_browsers_dir() == tmp_path / "packaging-runtime" / "browsers"
    assert runtime.get_browsers_dir().is_dir()


def test_environment_points_browsers_at_the_data_directory(tmp_path):
    ensured = runtime.ensure_environment()
    assert ensured["browsers_path"] == str(tmp_path / "packaging-runtime" / "browsers")
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == ensured["browsers_path"]
    assert "PLAYWRIGHT_DOWNLOAD_HOST" not in os.environ


def test_explicit_download_host_wins_over_the_pip_mirror(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
    monkeypatch.setenv("PLAYWRIGHT_DOWNLOAD_HOST", "https://mirror.example/playwright")
    assert runtime.download_host() == "https://mirror.example/playwright"


def test_autoclip_download_host_is_used_when_playwright_host_is_unset(monkeypatch):
    monkeypatch.setenv("AUTOCLIP_PLAYWRIGHT_DOWNLOAD_HOST", "https://mirror.example/pw")
    runtime.ensure_environment()
    assert os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] == "https://mirror.example/pw"


def test_china_pip_index_selects_the_playwright_mirror(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
    assert runtime.download_host() == runtime.CN_DOWNLOAD_HOST


def test_public_pypi_does_not_force_a_china_mirror(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://pypi.org/simple")
    assert runtime.download_host() is None


def test_mirror_switch_off_ignores_a_china_pip_index(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://mirrors.aliyun.com/pypi/simple")
    monkeypatch.setenv("AUTOCLIP_PLAYWRIGHT_MIRROR", "0")
    assert runtime.download_host() is None


def test_windows_prefers_edge_when_chrome_is_also_installed(monkeypatch):
    program = r"C:\Program Files"
    program_x86 = r"C:\Program Files (x86)"
    local = r"C:\Users\me\AppData\Local"
    monkeypatch.setenv("PROGRAMFILES", program)
    monkeypatch.setenv("PROGRAMFILES(X86)", program_x86)
    monkeypatch.setenv("LOCALAPPDATA", local)
    edge = os.path.join(program_x86, "Microsoft", "Edge", "Application", "msedge.exe")
    chrome = os.path.join(program, "Google", "Chrome", "Application", "chrome.exe")
    found = runtime.find_system_browser("win32", exists=lambda path: str(path) in {edge, chrome}, which=lambda _name: None)
    assert found == {"channel": "msedge", "executable": edge}


def test_linux_and_mac_prefer_chrome():
    chrome_bin = "/opt/google/chrome"
    edge_bin = "/opt/microsoft/edge"

    def which(name):
        return {"google-chrome-stable": chrome_bin, "microsoft-edge-stable": edge_bin}.get(name)

    assert runtime.find_system_browser("linux", exists=lambda _path: False, which=which)["channel"] == "chrome"
    mac_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    mac_edge = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    found = runtime.find_system_browser(
        "darwin",
        exists=lambda path: str(path) in {mac_chrome, mac_edge},
        which=lambda _name: None,
    )
    assert found == {"channel": "chrome", "executable": mac_chrome}


def test_missing_system_browser_asks_for_the_headless_shell(monkeypatch):
    monkeypatch.setattr(runtime, "find_system_browser", lambda: None)
    monkeypatch.setattr(runtime, "headless_shell_installed", lambda: False)
    plan = runtime.browser_plan()
    assert plan["ready"] is False
    assert plan["needs_download"] is True
    assert plan["mode"] == "chromium-headless-shell"
    assert "channel" not in runtime.launch_kwargs()


def test_installed_shell_is_enough_and_launch_stays_on_the_bundled_browser(tmp_path, monkeypatch):
    payload = tmp_path / "packaging-runtime" / "browsers" / "chromium_headless_shell-1208" / "chrome-linux"
    payload.mkdir(parents=True)
    (payload / "headless_shell").write_bytes(b"")
    monkeypatch.setattr(runtime, "find_system_browser", lambda: None)
    plan = runtime.browser_plan()
    assert plan == {"ready": True, "mode": "chromium-headless-shell", "channel": None, "executable": None, "needs_download": False}
    assert "channel" not in runtime.launch_kwargs()


def test_system_chrome_launch_uses_the_channel_and_skips_the_download(monkeypatch):
    monkeypatch.setattr(runtime, "find_system_browser", lambda: {"channel": "chrome", "executable": "/usr/bin/google-chrome"})
    plan = runtime.browser_plan()
    assert plan["needs_download"] is False
    kwargs = runtime.launch_kwargs()
    assert kwargs["channel"] == "chrome"
    assert kwargs["headless"] is True
    assert "--no-sandbox" not in kwargs["args"]


def test_root_launch_disables_the_sandbox(monkeypatch):
    monkeypatch.setattr(runtime, "find_system_browser", lambda: None)
    monkeypatch.setattr(runtime, "headless_shell_installed", lambda: True)
    monkeypatch.setattr(runtime, "_running_as_root", lambda: True)
    assert "--no-sandbox" in runtime.launch_kwargs()["args"]


def test_missing_component_falls_back_to_classic_without_blocking(monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: False)
    for requested in ("editorial", "street", "podcast", "Editorial"):
        assert runtime.effective_template(requested) == "classic"
    assert runtime.blocks_output() is False


def test_classic_family_stays_classic_even_when_the_runtime_is_ready(monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    for requested in (None, "", "classic", "auto", "interview_zh", "podcast_en", "landscape", "unknown"):
        assert runtime.effective_template(requested) == "classic"
    assert runtime.effective_template("editorial") == "editorial"
    assert runtime.effective_template("street") == "street"


def test_a_probe_failure_still_returns_classic(monkeypatch):
    def explode():
        raise RuntimeError("disk")

    monkeypatch.setattr(runtime, "is_installed", explode)
    assert runtime.effective_template("podcast") == "classic"


def test_status_reports_not_installed_and_remembers_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: False)
    assert runtime.get_status()["status"] == "not_installed"
    runtime._write_install_error("安装失败（pip 退出码 1）")
    runtime._set_state(status="unknown", progress=0, message="", log_tail="")
    status = runtime.get_status()
    assert status["status"] == "error"
    assert "退出码" in status["message"]
    assert status["fallback_template"] == "classic"
    assert status["blocks_output"] is False
    assert status["install_dir"].endswith("packaging-runtime")


def test_installing_status_is_not_overwritten(monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    runtime._set_state(status="installing", progress=40, message="正在下载", log_tail="")
    assert runtime.get_status()["status"] == "installing"


def test_start_install_refuses_a_second_concurrent_install():
    runtime._set_state(status="installing", progress=10, message="正在安装", log_tail="")
    assert runtime.start_install() == {"started": False, "message": "正在安装中"}


def test_start_install_does_nothing_when_already_ready(monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    assert runtime.start_install()["started"] is False
    assert runtime.get_status()["status"] == "installed"


def test_start_install_spawns_one_worker(monkeypatch):
    monkeypatch.setattr(runtime, "is_installed", lambda: False)
    spawned = {}

    class _Thread:
        def __init__(self, target, args=(), name=None, daemon=None):
            spawned["target"] = target
            spawned["args"] = args
            spawned["name"] = name

        def start(self):
            spawned["started"] = True

    monkeypatch.setattr(runtime.threading, "Thread", _Thread)
    assert runtime.start_install("https://pypi.org/simple")["started"] is True
    assert spawned["started"] is True
    assert spawned["name"] == "packaging-install"
    assert spawned["args"] == ("https://pypi.org/simple",)


def test_pip_install_skips_the_browser_download_when_chrome_exists(monkeypatch):
    commands = []

    def popen(command, **kwargs):
        commands.append((command, kwargs.get("env") or {}))
        return _Proc()

    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(runtime, "browser_plan", lambda: {
        "ready": True, "mode": "channel", "channel": "chrome", "executable": "/usr/bin/google-chrome", "needs_download": False,
    })
    monkeypatch.setenv("PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple")
    runtime._do_install(None)
    assert len(commands) == 1
    command, env = commands[0]
    assert command[:3] == [runtime.sys.executable, "-m", "pip"]
    assert "--target" in command
    assert command[command.index("--target") + 1].endswith(os.path.join("packaging-runtime"))
    assert "playwright>=1.49,<2" in command
    assert "chromium-headless-shell" not in command
    assert env["PLAYWRIGHT_DOWNLOAD_HOST"] == runtime.CN_DOWNLOAD_HOST
    assert env["PLAYWRIGHT_BROWSERS_PATH"].endswith(os.path.join("packaging-runtime", "browsers"))
    assert runtime.get_status()["status"] == "installed"


def test_shell_is_installed_only_when_no_system_browser_exists(monkeypatch):
    commands = []
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda command, **kwargs: commands.append(command) or _Proc())
    monkeypatch.setattr(runtime, "is_installed", lambda: True)
    monkeypatch.setattr(runtime, "browser_plan", lambda: {
        "ready": False, "mode": "chromium-headless-shell", "channel": None, "executable": None, "needs_download": True,
    })
    runtime._do_install("https://pypi.org/simple")
    assert len(commands) == 2
    assert "playwright>=1.49,<2" in commands[0]
    assert commands[0][-2:] == ["--index-url", "https://pypi.org/simple"]
    assert commands[1][-2:] == ["install", "chromium-headless-shell"]


def test_install_failure_is_remembered_without_a_local_path(tmp_path, monkeypatch):
    def popen(*_args, **_kwargs):
        raise OSError(f"cannot exec {tmp_path / 'python'}")

    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    monkeypatch.setattr(runtime, "browser_plan", lambda: {
        "ready": False, "mode": "chromium-headless-shell", "channel": None, "executable": None, "needs_download": True,
    })
    runtime._do_install(None)
    status = runtime.get_status()
    assert status["status"] == "error"
    assert str(tmp_path) not in status["message"]
    assert str(tmp_path) not in runtime._read_install_error()


def test_uninstall_removes_the_runtime_and_refuses_while_installing(tmp_path):
    runtime._set_state(status="installing", progress=3, message="正在安装", log_tail="")
    assert runtime.uninstall()["success"] is False
    runtime._set_state(status="installed", progress=100, message="", log_tail="")
    root = runtime.get_install_dir()
    _install_package(tmp_path)
    (root / "browsers" / "chromium_headless_shell-1" / "chrome-linux").mkdir(parents=True)
    runtime.sys.path.insert(0, str(root))
    runtime._write_install_error("旧错误")
    assert runtime.uninstall()["success"] is True
    assert not root.exists()
    assert str(root) not in runtime.sys.path
    assert runtime._read_install_error() == ""
    assert runtime.get_status()["status"] == "not_installed"
