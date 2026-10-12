"""
Whisper 运行时管理（桌面模式，按需安装）

桌面安装包默认不带 Whisper（运行时 + 模型有体积，没必要让所有用户都背）。用户在设置页
里可以自己决定是否安装、以及下载哪个模型。后端用 faster-whisper（CTranslate2，不依赖
PyTorch，运行时 ~200-400MB，比官方 whisper 快数倍，跨平台）。

设计要点：
- 安装到「用户可写目录」`<data_dir>/whisper-runtime`，而不是 .app 包内
  （/Applications 通常只读，且写入会破坏代码签名）。
- 用「当前正在跑后端的便携 Python」(sys.executable) 的 pip 安装，保证解释器一致。
- 模型缓存放 `<data_dir>/whisper-models`（通过 HF_HOME 收口）。
- 所有对 faster_whisper / huggingface_hub 的 import 都延迟到函数内部，避免构建期
  依赖扫描把它们当成缺失依赖而让打包失败。
"""

import os
import sys
import shutil
import logging
import threading
import subprocess
import queue
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 要安装的运行时包（faster-whisper 带上 ctranslate2、onnxruntime、av、huggingface_hub 等，
# 不含 PyTorch）
# PyAV 19 removed av.open(metadata_errors=...), still used by faster-whisper.
#
# 只装预编译 wheel（--only-binary=:all:）。不限版本时，镜像或官方源某个包的页面拿不到、
# 下载中断，pip 会回溯到很老的版本，而那些版本在 cp313 上只有源码包，于是开始现场编译
# av（要 FFmpeg 开发库）、tokenizers（要 Rust），在 Windows 上空转一个多小时后退出码 1
# （1.5.7 Windows 验收）。Windows 上把带原生代码的包钉在已确认有 cp313 win_amd64 wheel
# 的版本；其他平台只限上界，由 --only-binary 挑出本机能用的最新 wheel（老 macOS 会选到
# 较老但有 wheel 的 av / onnxruntime）。
WHISPER_PACKAGES = [
    "faster-whisper==1.2.1",
    "av>=11,<19",
    'av==18.1.0; sys_platform == "win32"',
    'ctranslate2==4.8.2; sys_platform == "win32"',
    'onnxruntime==1.31.0; sys_platform == "win32"',
    'tokenizers==0.23.3; sys_platform == "win32"',
]
# pip 参数、源顺序、时长和静默超时都在 pip_install 里，和人物识别组件共用。
from backend.services import pip_install  # noqa: E402
from backend.services.pip_install import (  # noqa: E402,F401
    PIP_FLAGS as WHISPER_PIP_FLAGS, PIP_MIRROR_TIMEOUT_SECONDS, PIP_OFFICIAL_TIMEOUT_SECONDS,
    PIP_STALL_SECONDS, NO_WHEEL_EXIT, SOURCE_BUILD_EXIT, TIMEOUT_EXIT,
)
# 运行时核心模块（用于探测是否已装）
WHISPER_IMPORT_NAME = "faster_whisper"
_runtime_import_error = ""


def _data_dir() -> Path:
    try:
        from backend.core.desktop_config import get_desktop_data_dir
        return Path(get_desktop_data_dir())
    except Exception:
        return Path(os.getenv("AUTOCLIP_DATA_DIR", str(Path.home() / "Library/Application Support/AutoClip")))


def get_install_dir() -> Path:
    d = _data_dir() / "whisper-runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_models_dir() -> Path:
    d = _data_dir() / "whisper-models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _install_error_path() -> Path:
    return _data_dir() / "whisper-install-error.txt"


def _read_install_error() -> str:
    """上次安装失败的一句说明。进程重启后内存状态会丢，设置页仍要能显示「重试安装」。"""
    try:
        return _install_error_path().read_text(encoding="utf-8").strip()[:500]
    except Exception:
        return ""


def _write_install_error(message: str) -> None:
    try:
        path = _install_error_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((message or "安装失败")[:500], encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"记录 Whisper 安装失败原因失败: {e}")


def _clear_install_error() -> None:
    try:
        _install_error_path().unlink(missing_ok=True)
    except Exception:
        pass


def ensure_on_path() -> None:
    """把运行时目录加入 sys.path，并把模型缓存目录收口到 HF_HOME。"""
    install_dir = str(get_install_dir())
    if install_dir not in sys.path:
        # 人物识别目录（framing-runtime）要排在前面：两边各带一份 numpy，混用会让 cv2 导入失败（PYTHON-FASTAPI-40）。
        framing_dir = str(_data_dir() / "framing-runtime")
        index = sys.path.index(framing_dir) + 1 if framing_dir in sys.path else 0
        sys.path.insert(index, install_dir)
    # 模型统一缓存到数据目录，便于管理/卸载
    os.environ.setdefault("HF_HOME", str(get_models_dir()))
    # 桌面端 stdout 往往不是控制台；tqdm 写 \r 进度条会 OSError / BrokenPipe
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ.setdefault("TQDM_DISABLE", "1")
    # faster-whisper 解码音频要用 ffmpeg：把内置 ffmpeg 所在目录并入 PATH
    ffmpeg_path = os.getenv("AUTOCLIP_FFMPEG_PATH")
    if ffmpeg_path:
        ffmpeg_dir = str(Path(ffmpeg_path).parent)
        if ffmpeg_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def is_installed() -> bool:
    """运行时是否已就绪（faster_whisper 可被导入）。"""
    global _runtime_import_error
    ensure_on_path()
    try:
        import importlib
        importlib.import_module(WHISPER_IMPORT_NAME)
        _runtime_import_error = ""
        return True
    except Exception as exc:
        missing_package = isinstance(exc, ModuleNotFoundError) and exc.name == WHISPER_IMPORT_NAME
        if not missing_package and not _runtime_import_error:
            logger.warning("Whisper 运行时导入失败: %s", type(exc).__name__)  # 状态轮询会反复调用：只记第一次
        # 异常名只进日志，不进设置页文案（RC156 #11）。
        _runtime_import_error = "" if missing_package else (
            "Whisper 运行时依赖加载失败。请重新安装 Whisper 后重启 AutoClip。"
        )
        return False


# ---- 安装状态（供前端轮询）----
_state_lock = threading.Lock()
_state: Dict[str, Any] = {
    "status": "unknown",   # not_installed | installing | installed | error
    "progress": 0,         # 粗粒度百分比
    "message": "",
    "log_tail": "",
}


def _set_state(**kw) -> None:
    with _state_lock:
        _state.update(kw)


def get_status() -> Dict[str, Any]:
    with _state_lock:
        st = dict(_state)
    # 安装进行中不打断。装完后以能否导入为准。
    # 失败必须留下 error：否则每次轮询都盖成 not_installed，设置页的「重试安装」永远不会出现。
    if st["status"] != "installing":
        if is_installed():
            st["status"] = "installed"
            st["progress"] = 100
        elif st["status"] == "error":
            pass
        else:
            remembered = _runtime_import_error or _read_install_error()
            if remembered:
                st["status"] = "error"
                st["message"] = remembered
            else:
                st["status"] = "not_installed"
    st["platform_supported"] = True  # faster-whisper 跨平台
    st["packages"] = WHISPER_PACKAGES
    return st


def pip_command(index_url: Optional[str]) -> list[str]:
    return pip_install.command(WHISPER_PACKAGES, str(get_install_dir()), index_url)


def index_plan(index_url: Optional[str]) -> list[tuple[str, Optional[str]]]:
    return pip_install.index_plan(index_url)


def _stream(cmd: list[str], timeout: float, stall_timeout: float, label: str = "") -> tuple[int, list[str]]:
    progress = pip_install.PipProgress(label)
    if label:
        _set_state(message=f"正在连接{pip_install.SOURCE_NAMES.get(label, label)}…")

    def on_line(line: str, lines: list[str]) -> None:
        step = progress.feed(line)
        if step:
            _set_state(progress=step[0], message=step[1])
        _set_state(log_tail="\n".join(lines[-12:]))

    return pip_install.stream(cmd, timeout, stall_timeout, on_line, owner="whisper")


def _failure_message(code: int, failures: list[str]) -> str:
    message = pip_install.failure_message(code, failures, " Whisper ")
    if code == NO_WHEEL_EXIT:
        message = message.removesuffix("。") + "，或改用带字幕的视频。"
    return message


def _do_install(index_url: Optional[str]) -> None:
    _set_state(status="installing", progress=5, message="正在准备安装…", log_tail="", error_code="")
    try:
        code, failures = pip_install.run_plan(
            index_plan(index_url), pip_command,
            lambda cmd, timeout, stall, label: _stream(cmd, timeout, stall, label=label)[0],
            on_switch=lambda _old, new, _why: _set_state(message=f"官方源没有装好，改用{pip_install.SOURCE_NAMES.get(new, new)}…"),
            what="Whisper 运行时",
        )
        if code == 0 and is_installed():
            _clear_install_error()
            _set_state(status="installed", progress=100, message="安装完成")
            logger.info("Whisper 运行时安装完成")
            return
        if code == pip_install.CANCEL_EXIT:
            _set_state(status="not_installed", progress=0, message="安装已取消")
            logger.info("Whisper 运行时安装已取消")
            return
        message = _failure_message(code, failures) if code != 0 else "安装结束，但 Whisper 运行时仍不可用"
        _set_state(error_code=pip_install.error_code(code, failures) if code != 0 else "not_usable")
        _write_install_error(message)
        _set_state(status="error", message=message)
        logger.error("Whisper 运行时安装失败: %s", "; ".join(failures) or message)
    except Exception as e:  # noqa: BLE001
        logger.error(f"安装 Whisper 运行时异常: {e}", exc_info=True)
        message = f"安装异常: {e}"
        _write_install_error(message)
        _set_state(status="error", message=message)


def _bump_progress(min_v: int, max_v: int, message: str) -> None:
    with _state_lock:
        cur = _state.get("progress", 0)
        _state["progress"] = max(min_v, min(max_v, cur + 2))
        _state["message"] = message


def start_install(index_url: Optional[str] = None) -> Dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "正在安装中"}
        _state.update(status="installing", progress=0, message="正在检查运行时…", log_tail="")
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return {"started": False, "message": "已安装"}
    # None 交给 index_plan：auto 先官方再镜像；设置了 PIP_INDEX_URL 时只用它。
    threading.Thread(target=_do_install, args=(index_url,), name="whisper-install", daemon=True).start()
    return {"started": True, "message": "已开始安装"}


def uninstall() -> Dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"success": False, "message": "正在安装中，无法卸载"}
    install_dir = get_install_dir()
    try:
        shutil.rmtree(install_dir, ignore_errors=True)
        # 从 sys.modules 里剔除，避免本进程仍能 import
        for mod in [m for m in list(sys.modules) if m.startswith("faster_whisper") or m.startswith("ctranslate2")]:
            sys.modules.pop(mod, None)
        p = str(install_dir)
        if p in sys.path:
            sys.path.remove(p)
        _clear_install_error()
        _set_state(status="not_installed", progress=0, message="已卸载")
        return {"success": True, "message": "已卸载 Whisper 运行时"}
    except Exception as e:  # noqa: BLE001
        logger.error(f"卸载 Whisper 运行时失败: {e}")
        return {"success": False, "message": str(e)}


def cancel_install() -> bool:
    """Stop a running install (kills pip). The install thread then records "安装已取消"."""
    from backend.services import pip_install
    return pip_install.cancel("whisper") > 0
