"""高级包装组件（桌面模式，按需安装）。

杂志风 / 街头 / 播客模板要用 Playwright 抓 HTML 叠加层。桌面安装包默认不带这份运行时
（Python 包约 40 MB，无头 Chromium 再加大约 100 MB）。没装好时成片走 classic（ASS），
出片不被挡住。

安装位置和 Whisper / 人物识别同一套约定：

- 装到用户可写目录 `<data_dir>/packaging-runtime`，不写进 .app（避免只读和破坏签名）。
- 用当前后端的 Python（`sys.executable`）做 `pip install --target`。
- 浏览器二进制放在该目录下的 `browsers/`，并设置 `PLAYWRIGHT_BROWSERS_PATH`。
- pip 源看 `AUTOCLIP_PIP_INDEX`（默认 `auto`）：先连官方 PyPI，静默超时再改清华镜像。
  `pypi` 只用官方，`mirror` 只用镜像。已经设置 `PIP_INDEX_URL` 时尊重它，不再自动切换。
- 浏览器下载看 `AUTOCLIP_PLAYWRIGHT_DOWNLOAD_SOURCE`（默认 `auto`）：先官方 CDN，超时再改
  npmmirror。`PLAYWRIGHT_DOWNLOAD_HOST` 或 `AUTOCLIP_PLAYWRIGHT_DOWNLOAD_HOST` 钉死地址时
  不再切换。系统里已有 Chrome 或 Edge 就用 `channel='chrome'/'msedge'`，不再下载
  chromium-headless-shell，也不会访问下载镜像。Windows 优先 Edge，其他系统优先 Chrome。
"""
from __future__ import annotations

import importlib
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

PACKAGES = ["playwright>=1.49,<2"]
IMPORT_NAME = "playwright"
BROWSER_PACKAGE = "chromium-headless-shell"
# Playwright 文档里的下载根。npmmirror 按 `<host>/<revision>/<browser>` 提供同一套构建。
CN_DOWNLOAD_HOST = "https://npmmirror.com/mirrors/playwright"
OFFICIAL_PIP_INDEX = "https://pypi.org/simple"
# 桌面构建脚本的默认 pip 源。大陆机器连不上 pypi.org 时用它做回退。
CN_PIP_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_INDEX_MODES = ("auto", "pypi", "mirror")
PLAYWRIGHT_DOWNLOAD_MODES = ("auto", "official", "mirror")
# 大陆到官方源的路由会黑洞。pip 自己的重试可以空转十几分钟且没有任何输出。
# 官方源一旦静默就改走镜像；镜像侧留出真正下载的时间。
PIP_OFFICIAL_STALL_SECONDS = 40
PIP_OFFICIAL_TIMEOUT_SECONDS = 90
PIP_MIRROR_STALL_SECONDS = 120
PIP_MIRROR_TIMEOUT_SECONDS = 600
BROWSER_OFFICIAL_STALL_SECONDS = 45
BROWSER_OFFICIAL_TIMEOUT_SECONDS = 180
BROWSER_MIRROR_STALL_SECONDS = 180
BROWSER_MIRROR_TIMEOUT_SECONDS = 600
PIP_SOCKET_TIMEOUT = "15"
PIP_RETRIES = "1"
TIMEOUT_EXIT = 124
HTML_TEMPLATES = frozenset({"editorial", "street", "podcast"})
CLASSIC = "classic"
# 旧版式仍然是 ASS，读到它们时不要误当成 HTML 模板。
_CLASSIC_ALIASES = frozenset({"", CLASSIC, "interview_zh", "podcast_en", "landscape", "none", "auto"})
_SHELL_PREFIXES = ("chromium_headless_shell-", "chromium-")
_SHELL_BINARIES = {
    "chrome", "chrome.exe", "chromium", "chromium.exe",
    "headless_shell", "headless_shell.exe",
}

_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "unknown",  # not_installed | installing | installed | error
    "progress": 0,
    "message": "",
    "log_tail": "",
}
_runtime_import_error = ""


def _data_dir() -> Path:
    try:
        from backend.core.desktop_config import get_desktop_data_dir
        return Path(get_desktop_data_dir())
    except Exception:
        return Path(os.getenv("AUTOCLIP_DATA_DIR", str(Path.home() / "Library/Application Support/AutoClip")))


def install_root() -> Path:
    """安装目录。探测时不创建，避免只读数据目录把状态轮询变成一次写入。"""
    return _data_dir() / "packaging-runtime"


def get_install_dir() -> Path:
    path = install_root()
    path.mkdir(parents=True, exist_ok=True)
    return path


def browsers_dir() -> Path:
    return install_root() / "browsers"


def get_browsers_dir() -> Path:
    path = browsers_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _error_path() -> Path:
    return _data_dir() / "packaging-install-error.txt"


def _read_install_error() -> str:
    try:
        return _error_path().read_text(encoding="utf-8").strip()[:500]
    except Exception:
        return ""


def _write_install_error(message: str) -> None:
    try:
        path = _error_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((message or "安装失败")[:500], encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("记录包装组件安装失败原因失败: %s", type(exc).__name__)


def _clear_install_error() -> None:
    try:
        _error_path().unlink(missing_ok=True)
    except Exception:
        pass


def _named_mode(value: str, allowed: tuple[str, ...], aliases: dict[str, str]) -> str | None:
    text = aliases.get(value, value)
    return text if text in allowed else None


def pip_index_mode() -> str:
    raw = (os.getenv("AUTOCLIP_PIP_INDEX") or "auto").strip().lower()
    return _named_mode(raw, PIP_INDEX_MODES, {
        "official": "pypi", "pypi.org": "pypi",
        "cn": "mirror", "china": "mirror", "tuna": "mirror", "tsinghua": "mirror",
    }) or "auto"


def pip_index_plan(explicit: str | None = None) -> list[tuple[str, str]]:
    """[(label, index url)]，按尝试顺序。

    和 Whisper 的下载计划同一形状：显式模式优先；用户设置了 PIP_INDEX_URL 时只用它；
    auto 先官方索引，再清华镜像。
    """
    if explicit and explicit.strip():
        return [("custom", explicit.strip())]
    mode = pip_index_mode()
    if mode == "pypi":
        return [("pypi", OFFICIAL_PIP_INDEX)]
    if mode == "mirror":
        return [("mirror", CN_PIP_INDEX)]
    custom = (os.getenv("PIP_INDEX_URL") or "").strip()
    if custom:
        return [("custom", custom)]
    return [("pypi", OFFICIAL_PIP_INDEX), ("mirror", CN_PIP_INDEX)]


def playwright_download_mode() -> str:
    raw = (os.getenv("AUTOCLIP_PLAYWRIGHT_DOWNLOAD_SOURCE") or "").strip().lower()
    chosen = _named_mode(raw, PLAYWRIGHT_DOWNLOAD_MODES, {
        "cdn": "official", "playwright": "official",
        "npmmirror": "mirror", "cn": "mirror", "china": "mirror",
    })
    if chosen:
        return chosen
    switch = (os.getenv("AUTOCLIP_PLAYWRIGHT_MIRROR") or "").strip().lower()
    if switch in {"0", "off", "false", "no"}:
        return "official"
    if switch in {"1", "on", "true", "yes", "cn"}:
        return "mirror"
    return "auto"


def browser_download_plan() -> list[tuple[str, str | None]]:
    """[(label, PLAYWRIGHT_DOWNLOAD_HOST)]。官方 CDN 的 host 是 None。"""
    explicit = (os.getenv("PLAYWRIGHT_DOWNLOAD_HOST") or "").strip()
    override = (os.getenv("AUTOCLIP_PLAYWRIGHT_DOWNLOAD_HOST") or "").strip()
    pinned = explicit or override
    if pinned:
        return [("custom", pinned)]
    mode = playwright_download_mode()
    if mode == "official":
        return [("official", None)]
    if mode == "mirror":
        return [("mirror", CN_DOWNLOAD_HOST)]
    return [("official", None), ("mirror", CN_DOWNLOAD_HOST)]


def download_host() -> str | None:
    """钉死的浏览器下载根。auto 会逐个尝试，这里返回 None，避免还没试官方源就写上镜像。"""
    plan = browser_download_plan()
    if len(plan) == 1:
        return plan[0][1]
    return None


def ensure_environment() -> dict[str, Any]:
    """把浏览器缓存和国内镜像收口到数据目录。抓帧前调用一次即可。"""
    browsers = get_browsers_dir()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers)
    host = download_host()
    if host:
        os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = host
    ensure_on_path()
    return {"browsers_path": str(browsers), "download_host": host}


def ensure_on_path() -> None:
    install_dir = str(install_root())
    if install_dir not in sys.path:
        sys.path.insert(0, install_dir)


def package_present() -> bool:
    return (install_root() / IMPORT_NAME / "__init__.py").is_file()


def _playwright_importable() -> bool:
    global _runtime_import_error
    ensure_on_path()
    try:
        importlib.import_module(IMPORT_NAME)
    except Exception as exc:
        missing = isinstance(exc, ModuleNotFoundError) and exc.name == IMPORT_NAME
        if not missing and not _runtime_import_error:
            logger.warning("包装运行时导入失败: %s", type(exc).__name__)
        _runtime_import_error = "" if missing else (
            "包装运行时依赖加载失败。请重新安装高级包装组件后重启 AutoClip。"
        )
        return False
    _runtime_import_error = ""
    return True


def _running_as_root() -> bool:
    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid and geteuid() == 0)


def chromium_args() -> list[str]:
    args = ["--disable-dev-shm-usage", "--disable-extensions"]
    # 容器里若必须以 root 跑，Chromium 沙箱会直接拒绝启动。普通桌面用户保持沙箱。
    if _running_as_root():
        args.append("--no-sandbox")
    return args


def _channel_order(platform: str) -> list[str]:
    # Windows 桌面一定有 Edge；macOS / Linux 上 Chrome 更常见。
    if platform == "win32":
        return ["msedge", "chrome"]
    return ["chrome", "msedge"]


def _channel_locations(platform: str, channel: str) -> list[str]:
    if platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        program = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        program_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        if channel == "msedge":
            relative = os.path.join("Microsoft", "Edge", "Application", "msedge.exe")
            return [os.path.join(program_x86, relative), os.path.join(program, relative), os.path.join(local, relative)]
        relative = os.path.join("Google", "Chrome", "Application", "chrome.exe")
        return [os.path.join(local, relative), os.path.join(program, relative), os.path.join(program_x86, relative)]
    if platform == "darwin":
        home = str(Path.home())
        if channel == "chrome":
            name = "Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            name = "Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        return [str(Path("/Applications") / name), str(Path(home) / "Applications" / name)]
    if channel == "chrome":
        return ["google-chrome-stable", "google-chrome"]
    return ["microsoft-edge-stable", "microsoft-edge"]


def find_system_browser(
    platform: str | None = None,
    exists: Callable[[Path], bool] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, str] | None:
    """系统 Chrome / Edge。找到就不必下载 chromium-headless-shell。"""
    system = platform or sys.platform
    exists = exists or (lambda path: path.is_file())
    which = which or shutil.which
    for channel in _channel_order(system):
        for location in _channel_locations(system, channel):
            path = Path(location)
            absolute = path.is_absolute() or (system == "win32" and len(location) > 2 and location[1] == ":")
            if absolute:
                if exists(path):
                    return {"channel": channel, "executable": str(path)}
                continue
            found = which(location)
            if found:
                return {"channel": channel, "executable": found}
    return None


def _shell_payload_present(root: Path) -> bool:
    if not root.is_dir():
        return False
    try:
        children = list(root.iterdir())
    except OSError:
        return False
    for child in children:
        if not child.is_dir() or not child.name.startswith(_SHELL_PREFIXES):
            continue
        try:
            for file in child.rglob("*"):
                if file.is_file() and file.name.lower() in _SHELL_BINARIES:
                    return True
        except OSError:
            continue
    return False


def headless_shell_installed() -> bool:
    return _shell_payload_present(browsers_dir())


def browser_plan() -> dict[str, Any]:
    found = find_system_browser()
    if found:
        return {
            "ready": True,
            "mode": "channel",
            "channel": found["channel"],
            "executable": found["executable"],
            "needs_download": False,
        }
    if headless_shell_installed():
        return {
            "ready": True,
            "mode": BROWSER_PACKAGE,
            "channel": None,
            "executable": None,
            "needs_download": False,
        }
    return {
        "ready": False,
        "mode": BROWSER_PACKAGE,
        "channel": None,
        "executable": None,
        "needs_download": True,
    }


def launch_kwargs() -> dict[str, Any]:
    """给 `playwright.chromium.launch` 的参数。系统浏览器优先。"""
    plan = browser_plan()
    kwargs: dict[str, Any] = {"headless": True, "args": chromium_args()}
    if plan["mode"] == "channel" and plan.get("channel"):
        kwargs["channel"] = plan["channel"]
    return kwargs


def is_installed() -> bool:
    if not package_present() or not _playwright_importable():
        return False
    return bool(browser_plan()["ready"])


def effective_template(requested: str | None) -> str:
    """组件没就绪时改走 classic。任何探测失败都退回 classic，不把异常抛给出片。"""
    name = (requested or "").strip().lower()
    if name in _CLASSIC_ALIASES or name not in HTML_TEMPLATES:
        return CLASSIC
    try:
        ready = is_installed()
    except Exception:
        logger.exception("包装运行时状态探测失败，改用 classic")
        return CLASSIC
    return name if ready else CLASSIC


def blocks_output() -> bool:
    """高级包装是可选的。缺组件只降级模板，不阻断出片。"""
    return False


def _set_state(**kwargs: Any) -> None:
    with _state_lock:
        _state.update(kwargs)


def _public_failure(message: str) -> str:
    # 设置页轮询会拿到 message。异常原文里常有本机路径，只写进日志。
    return message


def get_status() -> dict[str, Any]:
    with _state_lock:
        status = dict(_state)
    if status["status"] != "installing":
        try:
            ready = is_installed()
        except Exception:
            logger.exception("包装运行时状态探测失败")
            ready = False
            status["status"] = "error"
            status["message"] = _public_failure("包装组件状态读取失败。请重新安装高级包装组件。")
        if ready:
            status["status"] = "installed"
            status["progress"] = 100
        elif status["status"] == "error":
            pass
        else:
            remembered = _runtime_import_error or _read_install_error()
            if remembered:
                status["status"] = "error"
                status["message"] = remembered
            else:
                status["status"] = "not_installed"
    try:
        plan = browser_plan()
    except Exception:
        logger.exception("包装浏览器探测失败")
        plan = {"ready": False, "mode": BROWSER_PACKAGE, "channel": None, "executable": None, "needs_download": True}
    host = None
    try:
        host = download_host()
    except Exception:
        logger.exception("包装下载镜像探测失败")
    status["platform_supported"] = True
    status["packages"] = list(PACKAGES)
    status["browser_package"] = BROWSER_PACKAGE
    status["install_dir"] = str(install_root())
    status["browsers_path"] = str(browsers_dir())
    status["download_host"] = host
    status["browser"] = {key: plan.get(key) for key in ("mode", "channel", "needs_download", "ready")}
    status["fallback_template"] = CLASSIC
    status["blocks_output"] = blocks_output()
    return status


def _child_env() -> dict[str, str]:
    ensured = ensure_environment()
    env = os.environ.copy()
    root = str(get_install_dir())
    env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PIP_PROGRESS_BAR"] = "off"
    env["PLAYWRIGHT_BROWSERS_PATH"] = ensured["browsers_path"]
    if ensured["download_host"]:
        env["PLAYWRIGHT_DOWNLOAD_HOST"] = ensured["download_host"]
    return env


def pip_command(index_url: str | None) -> list[str]:
    command = [
        sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check",
        # 套接字超时挡不住被黑洞的 DNS / TCP。进程级静默超时在 _stream 里兜底。
        "--timeout", PIP_SOCKET_TIMEOUT, "--retries", PIP_RETRIES,
        "--target", str(get_install_dir()), *PACKAGES,
    ]
    if index_url:
        command += ["--index-url", index_url]
    return command


def browser_install_command() -> list[str]:
    return [sys.executable, "-m", "playwright", "install", BROWSER_PACKAGE]


def _bump(min_value: int, max_value: int, message: str) -> None:
    with _state_lock:
        current = int(_state.get("progress") or 0)
        _state["progress"] = max(min_value, min(max_value, current + 2))
        _state["message"] = message


def _attempt_limits(kind: str, label: str) -> tuple[float, float]:
    short = label in {"pypi", "official"}
    if kind == "browser":
        if short:
            return (BROWSER_OFFICIAL_TIMEOUT_SECONDS, BROWSER_OFFICIAL_STALL_SECONDS)
        return (BROWSER_MIRROR_TIMEOUT_SECONDS, BROWSER_MIRROR_STALL_SECONDS)
    if short:
        return (PIP_OFFICIAL_TIMEOUT_SECONDS, PIP_OFFICIAL_STALL_SECONDS)
    return (PIP_MIRROR_TIMEOUT_SECONDS, PIP_MIRROR_STALL_SECONDS)


def _with_download_host(env: dict[str, str], host: str | None) -> dict[str, str]:
    copied = dict(env)
    if host:
        copied["PLAYWRIGHT_DOWNLOAD_HOST"] = host
    else:
        copied.pop("PLAYWRIGHT_DOWNLOAD_HOST", None)
    return copied


def _stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    stdout = getattr(proc, "stdout", None)
    if stdout is not None:
        try:
            stdout.close()
        except Exception:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def _stream(
    command: list[str],
    env: dict[str, str],
    progress: tuple[int, int],
    timeout: float | None = None,
    stall_timeout: float | None = None,
) -> int:
    # 没传超时也要停。大陆网络上一次没有输出的 pip 可以空转到十几分钟。
    if timeout is None:
        timeout = PIP_MIRROR_TIMEOUT_SECONDS
    if stall_timeout is None:
        stall_timeout = PIP_MIRROR_STALL_SECONDS
    logger.info("包装组件: %s", " ".join(command))
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1, env=env,
    )
    assert proc.stdout is not None
    lines_out: queue.Queue[str | None] = queue.Queue()

    def _read() -> None:
        try:
            for line in iter(proc.stdout.readline, ""):
                lines_out.put(line)
        except Exception:
            logger.debug("包装组件输出读取中断", exc_info=True)
        finally:
            lines_out.put(None)

    threading.Thread(target=_read, name="packaging-install-output", daemon=True).start()
    started = time.monotonic()
    last_output = started
    lines: list[str] = []
    while True:
        now = time.monotonic()
        waits: list[float] = []
        if timeout is not None:
            waits.append(started + timeout - now)
        if stall_timeout is not None:
            waits.append(last_output + stall_timeout - now)
        wait = min(waits) if waits else None
        if wait is not None and wait <= 0:
            logger.warning("包装组件命令静默超时，已终止")
            _stop_process(proc)
            return TIMEOUT_EXIT
        try:
            item = lines_out.get(timeout=wait)
        except queue.Empty:
            logger.warning("包装组件命令静默超时，已终止")
            _stop_process(proc)
            return TIMEOUT_EXIT
        if item is None:
            break
        last_output = time.monotonic()
        line = item.rstrip()
        if not line:
            continue
        lines.append(line)
        lines[:] = lines[-40:]
        low = line.lower()
        if "collecting" in low or "downloading" in low or "download" in low:
            _bump(progress[0], progress[1], line[:180])
        _set_state(log_tail="\n".join(lines[-12:]))
    return proc.wait()


def _run_plan(
    kind: str,
    plan: list[tuple[str, str | None]],
    env: dict[str, str],
    progress: tuple[int, int],
) -> tuple[int, list[str]]:
    code = 1
    failures: list[str] = []
    for index, (label, value) in enumerate(plan):
        hard, stall = _attempt_limits(kind, label)
        if kind == "browser":
            command = browser_install_command()
            attempt_env = _with_download_host(env, value)
        else:
            command = pip_command(value if isinstance(value, str) else None)
            attempt_env = env
        if index and failures:
            logger.warning("包装组件 %s 从 %s 失败（%s），改用 %s", kind, plan[index - 1][0], failures[-1], label)
            _set_state(message="官方源无响应，改用国内镜像…")
        code = _stream(command, attempt_env, progress, timeout=hard, stall_timeout=stall)
        if code == 0:
            return 0, failures
        reason = "超时" if code == TIMEOUT_EXIT else f"退出码 {code}"
        failures.append(f"{label}: {reason}")
    return code, failures


def _failure_message(kind: str, code: int, failures: list[str]) -> str:
    timed_out = code == TIMEOUT_EXIT
    if len(failures) > 1:
        if kind == "browser":
            return "浏览器下载失败（官方源无响应，国内镜像也失败）"
        return "安装失败（官方 PyPI 无响应，国内镜像也失败）"
    if kind == "browser":
        return "浏览器下载失败（超时）" if timed_out else f"浏览器下载失败（退出码 {code}）"
    return "安装失败（pip 超时）" if timed_out else f"安装失败（pip 退出码 {code}）"


def _do_install(index_url: str | None) -> None:
    _set_state(status="installing", progress=5, message="正在准备高级包装组件…", log_tail="")
    try:
        env = _child_env()
        if not package_present() or not _playwright_importable():
            code, failures = _run_plan("pip", pip_index_plan(index_url), env, (10, 60))
            if code != 0:
                message = _public_failure(_failure_message("pip", code, failures))
                _write_install_error(message)
                _set_state(status="error", message=message)
                logger.error("包装组件 pip 安装失败: %s", "; ".join(failures) or code)
                return
        plan = browser_plan()
        if plan["needs_download"]:
            _set_state(progress=65, message="正在下载无头浏览器…")
            code, failures = _run_plan("browser", browser_download_plan(), env, (65, 95))
            if code != 0:
                message = _public_failure(_failure_message("browser", code, failures))
                _write_install_error(message)
                _set_state(status="error", message=message)
                logger.error("chromium-headless-shell 安装失败: %s", "; ".join(failures) or code)
                return
        if is_installed():
            _clear_install_error()
            _set_state(status="installed", progress=100, message="安装完成")
            logger.info("高级包装组件安装完成，浏览器模式 %s", browser_plan()["mode"])
        else:
            message = _public_failure("安装结束，但包装组件仍不可用")
            _write_install_error(message)
            _set_state(status="error", message=message)
    except Exception as exc:  # noqa: BLE001
        logger.error("安装高级包装组件异常: %s", exc, exc_info=True)
        message = _public_failure("安装异常。请稍后重试，或继续使用经典模板出片。")
        _write_install_error(message)
        _set_state(status="error", message=message)


def start_install(index_url: str | None = None) -> dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "正在安装中"}
        _state.update(status="installing", progress=0, message="正在检查运行时…", log_tail="")
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return {"started": False, "message": "已安装"}
    # None 交给 pip_index_plan：auto 先官方再镜像，PIP_INDEX_URL 则只用用户指定的源。
    threading.Thread(target=_do_install, args=(index_url,), name="packaging-install", daemon=True).start()
    return {"started": True, "message": "已开始安装"}


def install_blocking(index_url: str | None = None) -> dict[str, Any]:
    """测速和修复脚本用的同步安装。设置页走 `start_install`。"""
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return get_status()
    _do_install(index_url)
    return get_status()


def uninstall() -> dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"success": False, "message": "正在安装中，无法卸载"}
    root = install_root()
    try:
        shutil.rmtree(root, ignore_errors=True)
        if root.exists():
            return {"success": False, "message": "卸载失败"}
        removed = str(root)
        while removed in sys.path:
            sys.path.remove(removed)
        for name in [module for module in list(sys.modules) if module == IMPORT_NAME or module.startswith(IMPORT_NAME + ".")]:
            sys.modules.pop(name, None)
        _clear_install_error()
        global _runtime_import_error
        _runtime_import_error = ""
        _set_state(status="not_installed", progress=0, message="已卸载", log_tail="")
        return {"success": True, "message": "已卸载高级包装组件"}
    except Exception as exc:  # noqa: BLE001
        logger.error("卸载高级包装组件失败: %s", type(exc).__name__)
        return {"success": False, "message": "卸载失败"}
