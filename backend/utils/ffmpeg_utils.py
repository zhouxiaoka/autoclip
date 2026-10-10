"""
FFmpeg 可执行路径解析工具

优先顺序：
1) 环境变量 AUTOCLIP_FFMPEG_PATH / AUTOCLIP_FFPROBE_PATH / FFMPEG_PATH / FFPROBE_PATH
2) 安装包或仓库里的 resources/ffmpeg（桌面应用没把环境变量传出来时）
3) 系统 PATH 中的 ffmpeg/ffprobe

用途：统一为后端所有调用点提供 ffmpeg/ffprobe 路径，便于在桌面安装包内置二进制并实现零依赖。
应用外直接跑脚本时，桌面壳不会设置 AUTOCLIP_FFMPEG_PATH，所以要自己找到安装目录里的二进制。
"""

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
_reported_missing: set[str] = set()


def _resolve_from_env(var_names: list[str]) -> Optional[str]:
    for var in var_names:
        value = os.getenv(var)
        if value and os.path.exists(value):
            return value
    return None


def tool_filename(base: str, platform_name: str | None = None) -> str:
    system = os.name if platform_name is None else platform_name
    return f"{base}.exe" if system == "nt" else base


def bundled_candidates(base: str, executable: str | None = None, platform_name: str | None = None) -> list[Path]:
    """安装包 resources/ffmpeg，以及源码仓库里的同一位置。

    便携 Python 在 resources/python/（Windows）或 resources/python/bin/（macOS / Linux），
    ffmpeg 在旁边的 resources/ffmpeg/。桌面壳启动时会把这个路径写进环境变量；
    应用外跑测速脚本时没有这个变量。
    """
    filename = tool_filename(base, platform_name)
    exe = Path(executable or sys.executable)
    try:
        exe = exe.resolve()
    except OSError:
        pass
    found: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = os.path.normcase(str(path))
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    for parent in exe.parents:
        if parent.name == "python":
            add(parent.parent / "ffmpeg" / filename)
        if parent.name == "resources":
            add(parent / "ffmpeg" / filename)
            break
    here = Path(__file__).resolve()
    if len(here.parents) >= 3:
        add(here.parents[2] / "resources" / "ffmpeg" / filename)
    return found


def missing_ffmpeg_message(name: str = "ffmpeg") -> str:
    env = f"AUTOCLIP_{name.upper()}_PATH / {name.upper()}_PATH"
    return (
        f"找不到 {name}。查找顺序是：环境变量 {env}，"
        "安装目录或仓库里的 resources/ffmpeg，然后是系统 PATH。"
        f"这些位置都没有可用的 {name}。"
        "请安装 ffmpeg（含 ffprobe），或设置 AUTOCLIP_FFMPEG_PATH 和 AUTOCLIP_FFPROBE_PATH。"
    )


def _report_missing(name: str) -> None:
    if name in _reported_missing:
        return
    _reported_missing.add(name)
    message = missing_ffmpeg_message(name)
    logger.warning("%s", message)
    print(message, file=sys.stderr, flush=True)


def _locate(base: str, env_names: list[str]) -> Optional[str]:
    env_path = _resolve_from_env(env_names)
    if env_path:
        return env_path
    for candidate in bundled_candidates(base):
        if candidate.is_file():
            return str(candidate)
    which = shutil.which(base)
    if which:
        return which
    return None


def get_ffmpeg_path() -> str:
    """返回 ffmpeg 可执行文件路径（或命令名）。"""
    found = _locate("ffmpeg", ["AUTOCLIP_FFMPEG_PATH", "FFMPEG_PATH"])
    if found:
        return found
    _report_missing("ffmpeg")
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """返回 ffprobe 可执行文件路径（或命令名）。"""
    found = _locate("ffprobe", ["AUTOCLIP_FFPROBE_PATH", "FFPROBE_PATH"])
    if found:
        return found
    _report_missing("ffprobe")
    return "ffprobe"




JS_RUNTIMES = ("deno", "node", "bun", "quickjs")


def ytdlp_js_runtimes() -> dict:
    """YouTube 现在要先解 JS 校验（yt-dlp-ejs）才能拿到视频流。

    yt-dlp 默认只启用 deno，用户机器上多半没有；装了 node / bun / quickjs 也会被当成不可用，
    报 "The page needs to be reloaded"。把本机能找到的运行时都交给它，按顺序择优使用。
    """
    found = {name: {"path": path} for name in JS_RUNTIMES if (path := shutil.which(name))}
    return {"js_runtimes": found} if found else {}


def ytdlp_ffmpeg_options() -> dict:
    """给 yt-dlp 的外部工具选项：ffmpeg 位置，以及可用的 JS 运行时。

    yt-dlp 只在 PATH 里找 ffmpeg，不读 AUTOCLIP_FFMPEG_PATH。桌面安装包的 ffmpeg 不在 PATH 上，
    Windows 上合并 bestvideo+bestaudio、转字幕格式都会失败，导入就卡住或找不到 mp4。
    只有解析到真实文件时才传，否则交给 yt-dlp 自己找。
    """
    options = ytdlp_js_runtimes()
    path = get_ffmpeg_path()
    if os.path.isabs(path) and os.path.exists(path):
        options["ffmpeg_location"] = path
    return options
