#!/usr/bin/env python3
"""Windows 安装后冒烟：用安装目录里自带的 Python 跑，验证用户实际拿到的运行时。

不需要网络和模型 key。覆盖：
- 后端能以桌面模式启动并通过 /health
- 来源守卫：自家 Origin 放行，其他网页的写请求被拒
- 内置 ffmpeg 能生成、切片、探测视频（Windows 上最常出问题的环节）
- yt-dlp 能拿到内置 ffmpeg 的路径（链接导入合并音视频依赖它）
- 保存 provider，上传真实公开访谈和 SRT，整条流水线完成并产出 H.264/AAC
  模型使用 loopback 协议 fixture，验证安装链路，不声称模型剪辑质量

用法（CI 在 NSIS 静默安装后调用）：
    "<安装目录>\\resources\\python\\python.exe" -B scripts\\verify_windows_install.py --resources "<安装目录>\\resources"
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
# CI 控制台默认 cp1252，打印中文会直接崩；桌面端由 Rust 注入 PYTHONUTF8，这里自己兜住
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

parser = argparse.ArgumentParser()
parser.add_argument("--resources", type=Path, required=True)
parser.add_argument("--report", type=Path)
parser.add_argument("--launch-desktop", action="store_true", help="通过安装后的桌面 exe 启动后端")
parser.add_argument('--source-video', type=Path, default=Path(__file__).resolve().parents[1] / 'backend/assets/example/source.mp4')
parser.add_argument('--source-srt', type=Path, default=Path(__file__).resolve().parents[1] / 'backend/assets/example/source.srt')
args = parser.parse_args()
if args.report:
    args.report = args.report.resolve()
args.source_video = args.source_video.resolve(strict=True)
args.source_srt = args.source_srt.resolve(strict=True)
resources = args.resources.resolve(strict=True)
if not Path(sys.executable).resolve().is_relative_to(resources / "python"):
    parser.error("必须用安装目录里的 python.exe 运行，而不是开发环境的 Python")

ffmpeg = resources / "ffmpeg" / "ffmpeg.exe"
ffprobe = resources / "ffmpeg" / "ffprobe.exe"
for required in (resources / "backend" / "desktop_main.py", ffmpeg, ffprobe):
    if not required.is_file():
        raise SystemExit(f"安装目录缺少文件: {required}")

root = Path(tempfile.mkdtemp(prefix="autoclip-win-smoke-"))
os.environ.update(
    AUTOCLIP_APP_DIR=str(root / "data"), AUTOCLIP_DATA_DIR=str(root / "data"),
    AUTOCLIP_DESKTOP_MODE="true", AUTOCLIP_MODE="desktop",
    DATABASE_URL="sqlite:///" + str(root / "smoke.sqlite").replace("\\", "/"),
    SENTRY_DSN="", PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
    AUTOCLIP_FFMPEG_PATH=str(ffmpeg), AUTOCLIP_FFPROBE_PATH=str(ffprobe),
)
(root / "data").mkdir()
(root / "data" / "privacy.json").write_text('{"crash_reports":false,"analytics":false}', encoding="utf-8")
os.chdir(resources)
sys.path.insert(0, str(resources))
report = {"python": sys.version.split()[0], "resources": str(resources)}


def step(name):
    print(f"==> {name}", flush=True)


step("内置 ffmpeg 生成、切片、探测")
source = root / "fixture.mp4"
subprocess.run([str(ffmpeg), "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)], check=True, timeout=60)
clip = root / "clip 中文 名.mp4"  # 非 ASCII 文件名曾导致 500（#189）
subprocess.run([str(ffmpeg), "-v", "error", "-ss", "1", "-i", str(source), "-t", "1", "-c", "copy", str(clip)],
               check=True, timeout=60)
probe = json.loads(subprocess.run([str(ffprobe), "-v", "error", "-show_format", "-of", "json", str(clip)],
                                  check=True, capture_output=True, text=True, encoding="utf-8").stdout)
assert 0.5 <= float(probe["format"]["duration"]) <= 1.6, probe
report["ffmpeg_clip"] = "passed"

step("yt-dlp 拿到内置 ffmpeg")
from backend.utils.ffmpeg_utils import ytdlp_ffmpeg_options  # noqa: E402
opts = ytdlp_ffmpeg_options()
assert Path(opts.get("ffmpeg_location", "")).resolve() == ffmpeg.resolve(), opts
report["ytdlp_ffmpeg"] = "passed"

step("桌面应用启动" if args.launch_desktop else "桌面后端启动")
if args.launch_desktop:
    apps = [p for p in resources.parent.glob('*.exe') if 'uninstall' not in p.name.lower()]
    assert len(apps) == 1, f"无法唯一定位安装后的应用: {apps}"
    command = [str(apps[0])]
    report['desktop_executable'] = apps[0].name
else:
    command = [sys.executable, "-B", "-m", "backend.desktop_main"]
proc = subprocess.Popen(command, cwd=resources, env=os.environ.copy(),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
lines, port = [], {}


def pump():
    for line in proc.stdout:
        lines.append(line.rstrip())
        if line.startswith('Backend output: '):
            line = line.removeprefix('Backend output: ')
        if line.startswith("PORT=") and "port" not in port:
            port["port"] = int(line.split("=", 1)[1])


threading.Thread(target=pump, daemon=True).start()
try:
    deadline = time.time() + 90
    while "port" not in port and time.time() < deadline and proc.poll() is None:
        time.sleep(0.5)
    if "port" not in port:
        print("\n".join(lines[-60:]))
        raise SystemExit("桌面后端没有在 90 秒内输出 PORT=")
    base = f"http://127.0.0.1:{port['port']}"
    with urlopen(base + "/health", timeout=10) as r:
        assert r.status == 200
    with urlopen(base + "/api/v1/projects/", timeout=15) as r:
        assert r.status == 200
    report["backend_health"] = "passed"
    if args.launch_desktop:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        windows = []
        @callback_type
        def inspect_window(handle, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value == proc.pid and user32.IsWindowVisible(handle):
                windows.append(handle)
            return True
        deadline = time.monotonic() + 15
        while not windows and time.monotonic() < deadline:
            user32.EnumWindows(inspect_window, 0)
            if not windows:
                time.sleep(.5)
        assert windows, "桌面程序没有创建可见窗口"
        report['desktop_window'] = 'passed'

    step("来源守卫")
    def post(origin):
        req = Request(base + "/api/v1/settings/privacy", method="PUT", data=b'{"crash_reports":false}',
                      headers={"Content-Type": "application/json", "Origin": origin})
        try:
            with urlopen(req, timeout=10) as r:
                return r.status
        except HTTPError as e:
            return e.code
    assert post("http://tauri.localhost") != 403, "Windows 自家界面的 Origin 被拦了"
    assert post("https://evil.example") == 403, "其他网页的写请求没被拦"
    report["origin_guard"] = "passed"

    step("保存 provider 并跑通真实本地视频（loopback 协议 fixture）")
    from installed_video_acceptance import run
    report["installed_video"] = run(base, root, resources, args.source_video, args.source_srt)
except BaseException:
    print("\n".join(lines[-120:]), flush=True)
    raise
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

print(json.dumps(report, ensure_ascii=False, indent=2))
if args.report:
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
