"""按需组件的 pip 安装：Whisper 运行时和人物识别组件共用。

- 源：沿用 packaging_runtime.pip_index_plan。显式参数 > AUTOCLIP_PIP_INDEX > PIP_INDEX_URL >
  auto（先官方 PyPI，再清华镜像）。
- 时长：官方源最多 15 分钟（后面还有镜像时），镜像 / 唯一的源最多 30 分钟；任何源 180 秒没有
  输出就停，换下一个源。
- 只装 wheel；输出里出现要编译的迹象立刻停，没有可用 wheel 单独报出来。
- 进度：解析 pip 的 Collecting / Downloading (大小) / Installing 行，给出百分比和一句阶段说明。
"""
from __future__ import annotations

import logging
import queue
import re
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PIP_FLAGS = [
    "--only-binary=:all:",
    "--disable-pip-version-check",
    # 单个套接字的超时和重试；整条命令的总时长和静默超时在 stream() 里兜底。
    "--timeout", "30",
    "--retries", "3",
]
PIP_OFFICIAL_TIMEOUT_SECONDS = 15 * 60
PIP_MIRROR_TIMEOUT_SECONDS = 30 * 60
PIP_STALL_SECONDS = 180
TIMEOUT_EXIT = 124
SOURCE_BUILD_EXIT = 125
NO_WHEEL_EXIT = 126
NETWORK_EXIT = 127
SOURCE_BUILD_MARKERS = (
    "building wheel for",
    "getting requirements to build wheel",
    "preparing metadata (pyproject.toml)",
    "installing build dependencies",
    "running setup.py",
)
# pip could not reach the index (W157-F2). A later "No matching distribution" after one of these
# means "nothing could be fetched", not "no wheel exists".
NETWORK_MARKERS = (
    "could not fetch url",
    "failed to establish a new connection",
    "newconnectionerror",
    "connecttimeouterror",
    "readtimeouterror",
    "connection refused",
    "connectionrefusederror",
    "connection reset",
    "connectionreseterror",
    "connection aborted",
    "connection broken",
    "remotedisconnected",
    "max retries exceeded",
    "timed out",
    "proxyerror",
    "cannot connect to proxy",
    "sslerror",
    "ssl: certificate_verify_failed",
    "temporary failure in name resolution",
    "name or service not known",
    "nodename nor servname provided",
    "getaddrinfo failed",
    "network is unreachable",
    "no route to host",
)
# --only-binary rejected every candidate: genuinely no wheel for this platform.
ONLY_BINARY_MARKERS = (
    "only-binary",
    "no matching distribution found",
    "could not find a version that satisfies",
)
NO_WHEEL_MARKERS = ONLY_BINARY_MARKERS
NETWORK_MESSAGE = "安装失败：网络连不上 pip 源。请检查网络或代理后重试；也可以设置环境变量 PIP_INDEX_URL 指定可用的源。"
SOURCE_NAMES = {"pypi": "官方 PyPI", "mirror": "清华镜像", "custom": "指定的 pip 源"}

Plan = list[tuple[str, Optional[str]]]
Progress = Callable[[int, str], None]


def index_plan(index_url: Optional[str] = None) -> Plan:
    from backend.services.packaging_runtime import pip_index_plan
    return list(pip_index_plan(index_url))


def command(packages: list[str], target: str, index_url: Optional[str]) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *PIP_FLAGS, "--target", target, *packages]
    if index_url:
        cmd += ["--index-url", index_url]
    return cmd


def budget(label: str, plan_size: int) -> float:
    return PIP_OFFICIAL_TIMEOUT_SECONDS if label == "pypi" and plan_size > 1 else PIP_MIRROR_TIMEOUT_SECONDS


_COLLECT = re.compile(r"^collecting\s+(\S+)", re.I)
_DOWNLOAD = re.compile(r"^downloading\s+(\S+)(?:\s+\(([\d.]+)\s*([kMG]?B)\))?", re.I)
_UNITS = {"b": 1 / 1024 / 1024, "kb": 1 / 1024, "mb": 1.0, "gb": 1024.0}


class PipProgress:
    """pip 输出 → (百分比, 阶段说明)。

    5–10 准备；10–30 解析依赖（每个 Collecting 推一点）；30–85 下载（按已下载包数 /
    已发现包数，大小写进说明）；85–95 安装；98 完成。只增不减。
    """

    def __init__(self, source: str = "", start: int = 5) -> None:
        self.source = SOURCE_NAMES.get(source, source)
        self.percent = start
        self.collected = 0
        self.downloaded = 0
        self.megabytes = 0.0

    def _where(self) -> str:
        return f"从{self.source}" if self.source else ""

    def _paren(self) -> str:
        return f"（{self.source}）" if self.source else ""

    def feed(self, line: str) -> Optional[tuple[int, str]]:
        text = line.strip()
        low = text.lower()
        message = None
        percent = self.percent
        match = _DOWNLOAD.match(text)
        if _COLLECT.match(text):
            self.collected += 1
            percent = max(percent, min(30, 10 + 2 * self.collected))
            message = f"正在{self._where()}解析依赖（{self.collected} 个包）…"
        elif match:
            self.downloaded += 1
            size = ""
            if match.group(2):
                mb = float(match.group(2)) * _UNITS.get(match.group(3).lower(), 1.0)
                self.megabytes += mb
                size = f"（{mb:.1f} MB）" if mb >= 0.1 else ""
            total = max(self.collected, self.downloaded, 1)
            percent = max(percent, 30 + int(55 * min(1.0, self.downloaded / total)))
            name = match.group(1).rsplit("/", 1)[-1].split("-", 1)[0]
            message = f"正在{self._where()}下载 {name}{size}… 已下载 {self.downloaded}/{total} 个包，共 {self.megabytes:.1f} MB"
        elif low.startswith("installing collected packages"):
            percent = max(percent, 88)
            message = f"正在安装依赖{self._paren()}…"
        elif low.startswith("successfully installed"):
            percent = max(percent, 98)
            message = f"正在完成安装{self._paren()}…"
        if message is None:
            return None
        self.percent = min(98, percent)
        return self.percent, message


_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def spawn_kwargs(env: Optional[dict] = None) -> dict:
    """How pip is started. Same isolation as ffmpeg / the QA worker on Windows.

    - stdin=DEVNULL: pip never reads the backend's stdin (the desktop shell's handle).
    - one merged stdout pipe, drained by a single reader thread: no two-pipe deadlock.
    - Windows: CREATE_NO_WINDOW (no console window in the desktop session) and
      CREATE_NEW_PROCESS_GROUP (console Ctrl events aimed at pip never reach the backend,
      and the backend's never reach pip). POSIX: its own session for the same reason.
    """
    import os
    kwargs: dict = dict(
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1, close_fds=True,
        env=env or {**os.environ, "PYTHONIOENCODING": "utf-8", "PIP_PROGRESS_BAR": "off"},
    )
    if os.name == "nt":
        kwargs["creationflags"] = (int(getattr(subprocess, "CREATE_NO_WINDOW", _CREATE_NO_WINDOW))
                                   | int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", _CREATE_NEW_PROCESS_GROUP)))
    from backend.services import child_guard
    kwargs.update(child_guard.popen_kwargs())  # POSIX: own session (+ Linux pdeathsig)
    return kwargs


CANCEL_EXIT = 130
_cancelled: set[str] = set()
_cancel_lock = threading.Lock()


def cancel(owner: str) -> int:
    """Stop `owner`'s running pip (install cancelled). Returns how many processes were killed."""
    from backend.services import child_guard
    with _cancel_lock:
        _cancelled.add(owner)
    return child_guard.kill(owner)


def _take_cancel(owner: str) -> bool:
    with _cancel_lock:
        if owner in _cancelled:
            _cancelled.discard(owner)
            return True
        return False


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except Exception:
        pass
    # Do not close proc.stdout here: the reader thread may hold its lock; killing pip closes
    # the write end, so the reader sees EOF and exits on its own.


def stream(cmd: list[str], timeout: float, stall_timeout: float,
           on_line: Optional[Callable[[str, list[str]], None]] = None, env: Optional[dict] = None,
           owner: str = "pip") -> tuple[int, list[str]]:
    """跑一次 pip。返回 (退出码, 最后几行)。超时 124，开始编译 125，没有可用 wheel 126，取消 130。"""
    from backend.services import child_guard
    logger.info("pip: %s", " ".join(cmd))
    _take_cancel(owner)  # a cancel only applies to the run that was live at the time
    proc = child_guard.track(subprocess.Popen(cmd, **spawn_kwargs(env)), owner)
    try:
        code, lines = _pump(proc, timeout, stall_timeout, on_line)
    finally:
        if proc.poll() is None:
            _stop(proc)
        child_guard.untrack(proc)
    if _take_cancel(owner):
        return CANCEL_EXIT, lines
    return code, lines


def _pump(proc: subprocess.Popen, timeout: float, stall_timeout: float,
          on_line: Optional[Callable[[str, list[str]], None]]) -> tuple[int, list[str]]:
    assert proc.stdout is not None
    out: "queue.Queue[Optional[str]]" = queue.Queue()

    def _read() -> None:
        try:
            for line in iter(proc.stdout.readline, ""):
                out.put(line)
        except Exception:
            pass
        finally:
            out.put(None)

    threading.Thread(target=_read, name="pip-output", daemon=True).start()
    started = last = time.monotonic()
    lines: list[str] = []
    no_wheel = False
    network = False
    while True:
        now = time.monotonic()
        wait = min(started + timeout - now, last + stall_timeout - now)
        if wait <= 0:
            _stop(proc)
            return TIMEOUT_EXIT, lines
        try:
            item = out.get(timeout=wait)
        except queue.Empty:
            _stop(proc)
            return TIMEOUT_EXIT, lines
        if item is None:
            break
        last = time.monotonic()
        line = item.rstrip()
        if not line:
            continue
        lines.append(line)
        lines[:] = lines[-40:]
        low = line.lower()
        if any(marker in low for marker in SOURCE_BUILD_MARKERS):
            logger.warning("pip 要从源码编译，已停止: %s", line[:200])
            _stop(proc)
            return SOURCE_BUILD_EXIT, lines
        if any(marker in low for marker in NETWORK_MARKERS):
            network = True
        elif any(marker in low for marker in NO_WHEEL_MARKERS):
            no_wheel = True
        if on_line:
            on_line(line, lines)
    code = proc.wait()
    if code != 0:
        return classify(code, lines, network=network, no_wheel=no_wheel), lines
    return code, lines


def classify(code: int, lines: list[str], *, network: Optional[bool] = None,
             no_wheel: Optional[bool] = None) -> int:
    """Exit code -> NETWORK_EXIT / NO_WHEEL_EXIT / code. Network errors win over "no matching
    distribution": when nothing could be fetched pip reports that too."""
    if code == 0:
        return 0
    lows = [line.lower() for line in lines]
    if network is None:
        network = any(m in low for low in lows for m in NETWORK_MARKERS)
    if no_wheel is None:
        no_wheel = any(m in low for low in lows for m in NO_WHEEL_MARKERS)
    if network:
        return NETWORK_EXIT
    if no_wheel:
        return NO_WHEEL_EXIT
    return code


def reason(code: int) -> str:
    return {TIMEOUT_EXIT: "超时", SOURCE_BUILD_EXIT: "需要源码编译", NO_WHEEL_EXIT: "没有可用 wheel",
            CANCEL_EXIT: "已取消", NETWORK_EXIT: "网络不通"}.get(code, f"退出码 {code}")


def run_plan(plan: Plan, command_for: Callable[[Optional[str]], list[str]],
             run: Callable[[list[str], float, float, str], int],
             on_switch: Optional[Callable[[str, str, str], None]] = None, what: str = "组件") -> tuple[int, list[str]]:
    """按 plan 逐个源尝试，返回 (最后的退出码, ["pypi: 超时", ...])。

    `run(cmd, timeout, stall, label)` 跑一次并返回退出码。官方源报“没有可用 wheel”时仍试镜像；
    镜像也没有就停。
    """
    failures: list[str] = []
    code = 1
    for i, (label, url) in enumerate(plan):
        if i:
            logger.warning("%s 从 %s 安装失败（%s），改用 %s", what, plan[i - 1][0], failures[-1], label)
            if on_switch:
                on_switch(plan[i - 1][0], label, failures[-1])
        code = run(command_for(url), budget(label, len(plan)), PIP_STALL_SECONDS, label)
        if code == 0:
            return 0, failures
        failures.append(f"{label}: {reason(code)}")
        if code == CANCEL_EXIT or (code == NO_WHEEL_EXIT and label != "pypi"):
            break
    return code, failures


def error_code(code: int, failures: list[str]) -> str:
    """Stable code for the UI (translated there): pip_network | pip_no_wheel | pip_source_build |
    pip_timeout | pip_cancelled | pip_failed."""
    if code == CANCEL_EXIT:
        return "pip_cancelled"
    if code == NETWORK_EXIT or (code == TIMEOUT_EXIT and any(f.endswith("网络不通") for f in failures)):
        return "pip_network"
    if code == NO_WHEEL_EXIT:
        return "pip_no_wheel"
    if code == SOURCE_BUILD_EXIT:
        return "pip_source_build"
    if code == TIMEOUT_EXIT:
        return "pip_timeout"
    return "pip_failed"


def failure_message(code: int, failures: list[str], what: str) -> str:
    if code == CANCEL_EXIT:
        return "安装已取消"
    if error_code(code, failures) == "pip_network":
        return NETWORK_MESSAGE
    if code == NO_WHEEL_EXIT:
        return f"安装失败：当前系统没有可用的{what}预编译包。请把 AutoClip 更新到最新版。"
    if code == SOURCE_BUILD_EXIT:
        return "安装失败：没有拿到预编译包，已停止从源码编译。请检查网络后重试。"
    if len(failures) > 1:
        return "安装失败：官方 PyPI 和国内镜像都没有装好。请检查网络后重试。"
    if code == TIMEOUT_EXIT:
        return "安装失败：下载超时。请检查网络后重试。"
    return f"安装失败（pip 退出码 {code}）"
