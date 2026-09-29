#!/usr/bin/env python3
"""Windows 安装后冒烟：用安装目录里自带的 Python 跑，验证用户实际拿到的运行时。

不需要网络和模型 key。覆盖：
- 后端能以桌面模式启动并通过 /health
- 来源守卫：自家 Origin 放行，其他网页的写请求被拒
- 内置 ffmpeg 能生成、切片、探测视频（Windows 上最常出问题的环节）
- yt-dlp 能拿到内置 ffmpeg 的路径（链接导入合并音视频依赖它）

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
args = parser.parse_args()
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

step("桌面后端启动")
proc = subprocess.Popen([sys.executable, "-B", "-m", "backend.desktop_main"], cwd=resources, env=os.environ.copy(),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
lines, port = [], {}


def pump():
    for line in proc.stdout:
        lines.append(line.rstrip())
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
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

print(json.dumps(report, ensure_ascii=False, indent=2))
if args.report:
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
