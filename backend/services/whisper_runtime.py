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
- 所有对 mlx_whisper / huggingface_hub 的 import 都延迟到函数内部，避免构建期
  依赖扫描把它们当成缺失依赖而让打包失败。
"""

import os
import sys
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 要安装的运行时包（faster-whisper 带上 ctranslate2、onnxruntime、av、huggingface_hub 等，
# 不含 PyTorch）
WHISPER_PACKAGES = ["faster-whisper"]
# 运行时核心模块（用于探测是否已装）
WHISPER_IMPORT_NAME = "faster_whisper"


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


def ensure_on_path() -> None:
    """把运行时目录加入 sys.path，并把模型缓存目录收口到 HF_HOME。"""
    install_dir = str(get_install_dir())
    if install_dir not in sys.path:
        sys.path.insert(0, install_dir)
    # 模型统一缓存到数据目录，便于管理/卸载
    os.environ.setdefault("HF_HOME", str(get_models_dir()))
    # mlx-whisper 解码音频要用 ffmpeg：把内置 ffmpeg 所在目录并入 PATH
    ffmpeg_path = os.getenv("AUTOCLIP_FFMPEG_PATH")
    if ffmpeg_path:
        ffmpeg_dir = str(Path(ffmpeg_path).parent)
        if ffmpeg_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def is_installed() -> bool:
    """运行时是否已就绪（mlx_whisper 可被导入）。"""
    ensure_on_path()
    try:
        import importlib.util
        return importlib.util.find_spec(WHISPER_IMPORT_NAME) is not None
    except Exception:
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
    # 没在安装时，用实际探测结果覆盖
    if st["status"] not in ("installing",):
        st["status"] = "installed" if is_installed() else "not_installed"
        if st["status"] == "installed":
            st["progress"] = 100
    st["platform_supported"] = True  # faster-whisper 跨平台
    st["packages"] = WHISPER_PACKAGES
    return st


def _do_install(index_url: Optional[str]) -> None:
    install_dir = get_install_dir()
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--upgrade",
        "--target", str(install_dir),
        *WHISPER_PACKAGES,
    ]
    if index_url:
        cmd += ["--index-url", index_url]
    logger.info(f"开始安装 Whisper 运行时: {' '.join(cmd)}")
    _set_state(status="installing", progress=5, message="正在准备安装…", log_tail="")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        lines: list[str] = []
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            lines.append(line)
            lines[:] = lines[-40:]
            # 粗粒度进度：根据 pip 的阶段词推进，纯属观感
            low = line.lower()
            if low.startswith("collecting") or "downloading" in low:
                _bump_progress(min_v=10, max_v=70, message=line)
            elif "installing collected packages" in low or "building" in low:
                _bump_progress(min_v=70, max_v=95, message="正在安装依赖…")
            _set_state(log_tail="\n".join(lines[-12:]))
        proc.wait()
        if proc.returncode == 0 and is_installed():
            _set_state(status="installed", progress=100, message="安装完成")
            logger.info("Whisper 运行时安装完成")
        else:
            _set_state(status="error", message=f"安装失败（pip 退出码 {proc.returncode}）")
            logger.error(f"Whisper 运行时安装失败，pip 退出码 {proc.returncode}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"安装 Whisper 运行时异常: {e}", exc_info=True)
        _set_state(status="error", message=f"安装异常: {e}")


def _bump_progress(min_v: int, max_v: int, message: str) -> None:
    with _state_lock:
        cur = _state.get("progress", 0)
        _state["progress"] = max(min_v, min(max_v, cur + 2))
        _state["message"] = message


def start_install(index_url: Optional[str] = None) -> Dict[str, Any]:
    with _state_lock:
        if _state["status"] == "installing":
            return {"started": False, "message": "正在安装中"}
    if is_installed():
        _set_state(status="installed", progress=100, message="已安装")
        return {"started": False, "message": "已安装"}
    # 默认走环境变量里的 pip 源（构建脚本/桌面默认清华），否则 PyPI
    idx = index_url or os.getenv("PIP_INDEX_URL")
    threading.Thread(target=_do_install, args=(idx,), name="whisper-install", daemon=True).start()
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
        _set_state(status="not_installed", progress=0, message="已卸载")
        return {"success": True, "message": "已卸载 Whisper 运行时"}
    except Exception as e:  # noqa: BLE001
        logger.error(f"卸载 Whisper 运行时失败: {e}")
        return {"success": False, "message": str(e)}
