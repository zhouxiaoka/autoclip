#!/usr/bin/env python3
"""Measure a 70s editorial overlay: frame capture versus encode.

This is the M0 timing probe (T0.2). It does not render a shipping template and it does not
touch release tags. The fixture matches the product plan's 70-second 9:16 magazine clip:

  * baseline is every frame, one page, 720p capture, then a two-pass libx264 encode
  * reuse captures one overlay for two Chinese 9:16 platforms
  * changed frames call renderFrame and skip a screenshot when the state hash is unchanged
  * 720p is scaled to 1080x1920 at encode time; a second page can capture in parallel
  * the fast path uses one encode with backend.services.video_encoder.h264_args

    python scripts/packaging_frame_benchmark.py --install-runtime \\
        --out benchmarks/packaging/reports/linux.json

macOS (worker cursor-agent-worker-114e0e00e2, Charlie MacBook Pro): run `uname -m` first and
record arm64 or x86_64, then the same command.

Windows (Tencent Cloud acceptance machine, run by AutoClip PM): the same command from a
checkout of this branch. Do not treat a missing local number as a result.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "benchmarks" / "packaging" / "editorial"
FPS = 30
DURATION_S = 70.0
FRAME_COUNT = 2100
WORD_FRAMES = 10
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
DOCKER_IMAGE = "mcr.microsoft.com/playwright/python:v1.55.0-noble"

# 抓帧次数、编码次数。编码次数大于 1 表示两条平台成片各编一次；复用只省抓帧。
ROW_SPECS = (
    ("基线·单条：720p 全帧、单页、两遍 x264", "serial_all_720", "two_pass", 1, 1),
    ("优化1·双平台不复用（对照）", "serial_all_720", "two_pass", 2, 2),
    ("优化1·双平台叠加层复用", "serial_all_720", "two_pass", 1, 2),
    ("优化2·只抓变化帧（单条，两遍编码）", "changed_720", "two_pass", 1, 1),
    ("优化3·1080p 全帧单页（对照，两遍编码）", "serial_all_1080", "two_pass", 1, 1),
    ("优化3·720p 全帧 + 2 页并行（单条，两遍编码）", "parallel_all_720", "two_pass", 1, 1),
    ("优化4·单遍 h264_args（单条，全帧抓取）", "serial_all_720", "one_pass", 1, 1),
    ("组合·单条：变化帧 + 2 页并行 + 单遍", "parallel_changed_720", "one_pass", 1, 1),
    ("组合·双平台：复用 + 变化帧并行 + 单遍", "parallel_changed_720", "one_pass", 1, 2),
)

UNMEASURED_PLATFORMS = (
    {
        "platform": "macOS",
        "status": "未测",
        "owner": "cursor-agent-worker-114e0e00e2",
        "machine": "Charlie MacBook Pro",
        "note": "先运行 uname -m，确认 arm64 或 x86_64，再在该机器上执行本脚本。",
    },
    {
        "platform": "Windows",
        "status": "未测",
        "owner": "AutoClip PM",
        "machine": "腾讯云 Windows 验收机",
        "note": "脚本可直接复跑。本任务没有在 Windows 上执行。",
    },
)

_SOURCE = (
    "今天我们把声音里真正有用的那一句留下来不靠夸张的形容词也不把对方没说过的数字说满"
    "杂志风要的是留白衬线和一句能站住的判断说话的人在画面中间字幕只在词换掉的时候才变"
    "同一段中文竖屏抖音和小红书共用这一层不必抓两次数字只滚动讲者亲口说出来的那一个"
    "术语卡像脚注短而且让开脸七十秒够把一件事讲清楚如果包装组件没有装上就退回经典字幕"
    "出片不能停下来这是一次技术验证测的是抓帧和编码不是把模板放进正式版画面保持九比十六"
    "先在七百二十乘一千二百八十上画完再放大到成片尺寸两页同时抓只是为了把没有变化的等待摊薄"
    "硬件编码能用就用不能用就回到软件编码而且只走一遍基线仍是每一帧都抓再做两遍软件编码"
    "讲者说到具体的数屏幕上的数字才跟着跳不会每一帧都重新画脚注出现的时候让开眼睛和嘴"
    "句子结束就收回我们要的是安静的版面而不是把所有动效都打开留白本身就是信息"
)


def frame_index(t: float, fps: int = FPS) -> int:
    return int(t * fps + 1e-4)


def _tokens(count: int) -> list[str]:
    chars = [char for char in _SOURCE if not char.isspace()]
    if not chars:
        raise RuntimeError("editorial fixture text is empty")
    while len(chars) < count * 2:
        chars.extend(chars)
    return ["".join(chars[i * 2:(i + 1) * 2]) for i in range(count)]


def _aligned(frame_count: int, ratio: float, word_frames: int) -> int:
    return (int(frame_count * ratio) // word_frames) * word_frames


def build_fill(frame_count: int = FRAME_COUNT, fps: int = FPS, word_frames: int = WORD_FRAMES) -> dict:
    """70s magazine timeline. Word spans sit on whole frames so the hash is stable."""
    if frame_count < word_frames:
        raise ValueError("need at least one word of frames")
    word_count = frame_count // word_frames
    words = []
    for index, text in enumerate(_tokens(word_count)):
        start = index * word_frames
        end = frame_count if index + 1 == word_count else (index + 1) * word_frames
        words.append({
            "text": text,
            "start": start / fps,
            "end": end / fps,
            "start_frame": start,
            "end_frame": end,
            "emphasis": "强调" if index % 17 == 0 else "",
        })

    def card(start_ratio: float, end_ratio: float, ident: str, title: str, body: str) -> dict:
        start = _aligned(frame_count, start_ratio, word_frames)
        end = max(_aligned(frame_count, end_ratio, word_frames), start + word_frames)
        end = min(end, frame_count)
        return {
            "id": ident, "title": title, "body": body,
            "start": start / fps, "end": end / fps, "start_frame": start, "end_frame": end,
        }

    hook_until = min(frame_count, word_frames * 8)
    number_start = _aligned(frame_count, 0.55, word_frames)
    step_frames = max(1, word_frames // 2)
    steps = 8
    number_end = min(frame_count, number_start + steps * step_frames)
    hold_until = min(frame_count, number_end + word_frames * 6)
    return {
        "hook": {"text": "一句判断", "until": hook_until / fps, "until_frame": hook_until},
        "kicker": "访谈 · 杂志",
        "words": words,
        "gloss": [
            card(0.12, 0.20, "g1", "留白", "版面只留一句能站住的话"),
            card(0.36, 0.44, "g2", "词边界", "字幕在换词时才重画"),
            card(0.74, 0.82, "g3", "退回", "没装组件就用经典模板"),
        ],
        "number": {
            "value": 3200,
            "unit": "万",
            "steps": steps,
            "start": number_start / fps,
            "end": number_end / fps,
            "hold_until": hold_until / fps,
            "start_frame": number_start,
            "end_frame": number_end,
            "hold_frame": hold_until,
        },
        "fps": fps,
        "frame_count": frame_count,
        "duration_s": frame_count / fps,
    }


def state_at(fill: dict, t: float) -> dict:
    index = frame_index(t, int(fill["fps"]))
    hook = fill["hook"]["text"] if index < fill["hook"]["until_frame"] else ""
    word = -1
    emphasis = ""
    for position, item in enumerate(fill["words"]):
        if item["start_frame"] <= index < item["end_frame"]:
            word = position
            emphasis = item.get("emphasis") or ""
            break
    gloss = ""
    for card in fill["gloss"]:
        if card["start_frame"] <= index < card["end_frame"]:
            gloss = card["id"]
            break
    step = -1
    number = fill["number"]
    if number["start_frame"] <= index < number["end_frame"]:
        span = number["end_frame"] - number["start_frame"]
        step = min(number["steps"] - 1, (index - number["start_frame"]) * number["steps"] // span)
    elif number["end_frame"] <= index < number["hold_frame"]:
        step = number["steps"] - 1
    digest = "|".join((hook, str(word), emphasis, gloss, str(step)))
    return {"hash": digest, "word": word, "emphasis": emphasis, "gloss": gloss, "hook": hook, "number_step": step}


def unique_state_count(fill: dict) -> int:
    last = None
    count = 0
    fps = int(fill["fps"])
    for index in range(int(fill["frame_count"])):
        digest = state_at(fill, index / fps)["hash"]
        if digest != last:
            count += 1
            last = digest
    return count


def page_html() -> str:
    html = (FIXTURE / "index.html").read_text(encoding="utf-8")
    script = (FIXTURE / "template.js").read_text(encoding="utf-8")
    return html.replace('<script src="template.js"></script>', "<script>\n" + script + "\n</script>")


def split_indices(frame_count: int, pages: int) -> list[list[int]]:
    pages = max(1, pages)
    size = (frame_count + pages - 1) // pages
    return [list(range(start, min(frame_count, start + size))) for start in range(0, frame_count, size)]


def ffconcat_text(frames: list[dict], fps: int) -> str:
    if not frames:
        raise ValueError("no overlay frames")
    lines = ["ffconcat version 1.0"]
    for frame in frames:
        path = Path(frame["path"]).resolve().as_posix().replace("'", r"'\''")
        lines.append(f"file '{path}'")
        lines.append(f"duration {frame['count'] / fps:.6f}")
    last = Path(frames[-1]["path"]).resolve().as_posix().replace("'", r"'\''")
    lines.append(f"file '{last}'")
    return "\n".join(lines) + "\n"


def filter_graph(width: int, height: int, fps: int) -> str:
    return (
        f"[0:v]scale={width}:{height}:flags=bilinear,fps={fps},format=yuv420p[base];"
        f"[1:v]scale={width}:{height}:flags=lanczos,fps={fps},format=rgba[ov];"
        f"[base][ov]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]"
    )


def baseline_bitrate(width: int, height: int, fps: int = FPS) -> int:
    from backend.services.video_encoder import _bitrate
    return _bitrate(width, height, fps)


def _inputs(concat: Path, fps: int, duration: float) -> list[str]:
    return [
        "-f", "lavfi", "-i", f"testsrc=size=640x1136:rate={fps}:duration={duration:.3f}",
        "-f", "concat", "-safe", "0", "-i", str(concat),
    ]


def two_pass_commands(ffmpeg: str, concat: Path, output: Path, width: int, height: int, fps: int, duration: float, passlog: Path) -> list[list[str]]:
    rate = str(baseline_bitrate(width, height, fps))
    video = ["-c:v", "libx264", "-preset", "medium", "-b:v", rate, "-pix_fmt", "yuv420p"]
    shared = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        *_inputs(concat, fps, duration),
        "-filter_complex", filter_graph(width, height, fps), "-map", "[v]",
    ]
    return [
        [*shared, *video, "-pass", "1", "-passlogfile", str(passlog), "-an", "-f", "null", "-"],
        [*shared, *video, "-pass", "2", "-passlogfile", str(passlog), "-an", "-movflags", "+faststart", str(output)],
    ]


def single_pass_command(ffmpeg: str, concat: Path, output: Path, width: int, height: int, fps: int, duration: float, video_args: list[str]) -> list[str]:
    return [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        *_inputs(concat, fps, duration),
        "-filter_complex", filter_graph(width, height, fps), "-map", "[v]",
        *video_args, "-an", "-movflags", "+faststart", str(output),
    ]


def comparison_rows(captures: dict, encodes: dict) -> list[dict]:
    baseline_key = ROW_SPECS[0]
    base_capture = captures[baseline_key[1]]["seconds"] * baseline_key[3]
    base_encode = encodes[baseline_key[2]]["seconds"] * baseline_key[4]
    baseline_total = base_capture + base_encode
    rows = []
    for title, capture_key, encode_key, capture_times, encode_times in ROW_SPECS:
        if capture_key not in captures or encode_key not in encodes:
            continue
        capture = captures[capture_key]
        encode = encodes[encode_key]
        capture_s = capture["seconds"] * capture_times
        encode_s = encode["seconds"] * encode_times
        total = capture_s + encode_s
        rows.append({
            "name": title,
            "capture_s": round(capture_s, 3),
            "encode_s": round(encode_s, 3),
            "total_s": round(total, 3),
            "frames": int(capture["frames_shot"]) * capture_times,
            "capture_runs": capture_times,
            "encode_runs": encode_times,
            "vs_baseline": round(total / baseline_total, 3) if baseline_total else None,
        })
    return rows


def clock(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{seconds:.1f}s ({whole // 60}:{whole % 60:02d})"


def markdown_table(rows: list[dict]) -> str:
    lines = [
        "| 方案 | 抓帧耗时 | 编码耗时 | 总耗时 | 抓帧数 | 相对单条基线 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        ratio = f"{row['vs_baseline']:.2f}×" if row.get("vs_baseline") is not None else "—"
        lines.append(
            f"| {row['name']} | {clock(row['capture_s'])} | {clock(row['encode_s'])} | "
            f"{clock(row['total_s'])} | {row['frames']} | {ratio} |"
        )
    return "\n".join(lines)


def platform_notes(docker_status: str) -> list[dict]:
    notes = [dict(item) for item in UNMEASURED_PLATFORMS]
    if docker_status != "measured":
        notes.append({
            "platform": "Docker",
            "status": "未测",
            "note": docker_status,
        })
    return notes


def _ffmpeg() -> str:
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    return get_ffmpeg_path()


def _run_ffmpeg(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=1800, check=False)


def encode_outputs(fill: dict, frames: list[dict], work: Path) -> dict:
    from backend.services.video_encoder import encoder, h264_args, run_with_fallback

    ffmpeg = _ffmpeg()
    fps = int(fill["fps"])
    duration = float(fill["duration_s"])
    concat = work / "overlay.ffconcat"
    concat.write_text(ffconcat_text(frames, fps), encoding="utf-8")
    chosen = encoder()
    passes = two_pass_commands(
        ffmpeg, concat, work / "baseline-two-pass.mp4", OUTPUT_WIDTH, OUTPUT_HEIGHT, fps, duration, work / "x264pass",
    )
    started = time.perf_counter()
    logs = []
    for command in passes:
        proc = _run_ffmpeg(command, work)
        logs.append((proc.stderr or "")[-1500:])
        if proc.returncode != 0:
            raise RuntimeError(f"two-pass x264 failed: {logs[-1]}")
    two_pass_s = time.perf_counter() - started

    attempts: list[str] = []

    def build(name: str) -> list[str]:
        attempts.append(name)
        return single_pass_command(
            ffmpeg, concat, work / f"one-pass-{name}.mp4", OUTPUT_WIDTH, OUTPUT_HEIGHT, fps, duration,
            h264_args(OUTPUT_WIDTH, OUTPUT_HEIGHT, name),
        )

    started = time.perf_counter()
    proc = run_with_fallback(build, lambda command: _run_ffmpeg(command, work))
    one_pass_s = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError(f"single-pass encode failed: {(proc.stderr or '')[-1500:]}")
    return {
        "two_pass": {
            "seconds": two_pass_s,
            "encoder": "libx264",
            "passes": 2,
            "preset": "medium",
            "bitrate": baseline_bitrate(OUTPUT_WIDTH, OUTPUT_HEIGHT, fps),
        },
        "one_pass": {
            "seconds": one_pass_s,
            "encoder": attempts[-1] if attempts else chosen,
            "attempts": attempts,
            "passes": 1,
            "probe_encoder": chosen,
        },
    }


def _host_info() -> dict:
    ffmpeg = _ffmpeg()
    try:
        version = subprocess.check_output([ffmpeg, "-version"], text=True, timeout=20).splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        version = ffmpeg
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "ffmpeg": version,
    }


async def _launch(playwright, options: dict) -> tuple[object, dict]:
    note = {"no_sandbox": "--no-sandbox" in options.get("args", []), "retried_without_sandbox": False}
    try:
        browser = await playwright.chromium.launch(**options)
        return browser, note
    except Exception:
        if note["no_sandbox"]:
            raise
        retried = {**options, "args": [*options.get("args", []), "--no-sandbox", "--disable-gpu"]}
        browser = await playwright.chromium.launch(**retried)
        note["retried_without_sandbox"] = True
        note["no_sandbox"] = True
        return browser, note


async def _prepare(page, html: str, fill: dict) -> None:
    await page.set_content(html, wait_until="load")
    await page.evaluate("(data) => window.setData(data)", fill)


async def _check_hashes(page, fill: dict) -> None:
    fps = int(fill["fps"])
    expected = [state_at(fill, index / fps)["hash"] for index in range(int(fill["frame_count"]))]
    bad = await page.evaluate(
        """({expected, fps}) => {
            const bad = [];
            for (let i = 0; i < expected.length; i++) {
              const hash = window.renderFrame(i / fps);
              if (hash !== expected[i]) bad.push([i, hash, expected[i]]);
              if (bad.length >= 6) break;
            }
            return bad;
        }""",
        {"expected": expected, "fps": fps},
    )
    if bad:
        raise RuntimeError(f"renderFrame hash diverged from Python: {bad}")


async def _shoot(page, indices: list[int], fps: int, skip_unchanged: bool, save_dir: Path | None) -> dict:
    frames: list[dict] = []
    last = None
    started = time.perf_counter()
    for index in indices:
        digest = await page.evaluate("(t) => window.renderFrame(t)", index / fps)
        if skip_unchanged and frames and digest == last:
            frames[-1]["count"] += 1
            continue
        png = await page.screenshot(type="png", omit_background=True, animations="disabled", caret="hide")
        path = None
        if save_dir is not None:
            path = save_dir / f"f{index:05d}.png"
            path.write_bytes(png)
        frames.append({"index": index, "hash": digest, "count": 1, "path": str(path) if path else None})
        last = digest
    return {
        "seconds": time.perf_counter() - started,
        "frames_shot": sum(1 for _ in frames),
        "output_frames": sum(frame["count"] for frame in frames),
        "frames": frames,
    }


async def _capture(playwright, html: str, fill: dict, options: dict, width: int, height: int, pages: int, skip_unchanged: bool, save_dir: Path | None) -> dict:
    started = time.perf_counter()
    browser, launch_note = await _launch(playwright, options)
    context = await browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
    chunks = split_indices(int(fill["frame_count"]), pages)

    async def one(chunk: list[int], ordinal: int) -> dict:
        page = await context.new_page()
        await _prepare(page, html, fill)
        directory = save_dir if save_dir is not None and ordinal == 0 else None
        return await _shoot(page, chunk, int(fill["fps"]), skip_unchanged, directory)

    results = await asyncio.gather(*[one(chunk, ordinal) for ordinal, chunk in enumerate(chunks)])
    version = browser.version
    await browser.close()
    frames = [frame for result in results for frame in result["frames"]]
    return {
        "seconds": time.perf_counter() - started,
        "frames_shot": sum(result["frames_shot"] for result in results),
        "output_frames": sum(result["output_frames"] for result in results),
        "shoot_s": max(result["seconds"] for result in results),
        "pages": pages,
        "width": width,
        "height": height,
        "skip_unchanged": skip_unchanged,
        "launch": launch_note,
        "browser_version": version,
        "frames": frames,
    }


def _launch_options(flag: str) -> dict:
    from backend.services.packaging_runtime import chromium_args, find_system_browser, is_installed, launch_kwargs

    if flag == "chrome":
        return {"headless": True, "channel": "chrome", "args": chromium_args()}
    if flag == "msedge":
        return {"headless": True, "channel": "msedge", "args": chromium_args()}
    if flag == "shell":
        return {"headless": True, "args": chromium_args()}
    if is_installed():
        return launch_kwargs()
    found = find_system_browser()
    if found:
        return {"headless": True, "channel": found["channel"], "args": chromium_args()}
    return {"headless": True, "args": chromium_args()}


async def measure(args, work: Path) -> dict:
    from playwright.async_api import async_playwright

    frame_count = int(round(args.seconds * args.fps))
    fill = build_fill(frame_count, args.fps)
    html = page_html()
    options = _launch_options(args.browser)
    captures: dict = {}
    async with async_playwright() as playwright:
        browser, launch_note = await _launch(playwright, options)
        page = await browser.new_page(viewport={"width": 720, "height": 1280}, device_scale_factor=1)
        await _prepare(page, html, fill)
        await _check_hashes(page, fill)
        browser_version = browser.version
        await browser.close()
        jobs = [
            ("serial_all_720", 720, 1280, 1, False, None),
            ("changed_720", 720, 1280, 1, True, work / "frames"),
            ("parallel_all_720", 720, 1280, 2, False, None),
            ("parallel_changed_720", 720, 1280, 2, True, None),
        ]
        if not args.skip_1080 and frame_count >= FRAME_COUNT:
            jobs.append(("serial_all_1080", 1080, 1920, 1, False, None))
        for name, width, height, pages, skip, save in jobs:
            if save is not None:
                save.mkdir(parents=True, exist_ok=True)
            print(f"capture {name}", flush=True)
            result = await _capture(playwright, html, fill, options, width, height, pages, skip, save)
            saved = result.pop("frames")
            if name == "changed_720":
                result["saved_frames"] = saved
            captures[name] = result
            print(f"  {result['frames_shot']} frames in {result['seconds']:.1f}s", flush=True)
        print("encode", flush=True)
        encodes = await asyncio.to_thread(encode_outputs, fill, captures["changed_720"].pop("saved_frames"), work)
    summary = {
        key: {field: value[field] for field in ("seconds", "frames_shot", "output_frames", "shoot_s", "pages", "width", "height", "skip_unchanged", "browser_version")}
        for key, value in captures.items()
    }
    rows = comparison_rows(summary, encodes)
    return {
        "schema": 1,
        "status": "measured",
        "label": args.label or platform.system().lower(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": _host_info(),
        "browser": {
            "launch": options,
            "version": browser_version,
            "sandbox_retry": launch_note,
        },
        "fixture": {
            "template": "editorial",
            "duration_s": fill["duration_s"],
            "fps": fill["fps"],
            "frames": fill["frame_count"],
            "unique_states": unique_state_count(fill),
            "capture_size": [720, 1280],
            "output_size": [OUTPUT_WIDTH, OUTPUT_HEIGHT],
        },
        "captures": summary,
        "encodes": encodes,
        "rows": rows,
        "markdown": markdown_table(rows),
        "unmeasured_platforms": list(platform_notes("pending-docker" if args.docker else "本机未跑 Docker")),
        "notes": [
            "抓帧耗时含浏览器冷启动、renderFrame 和 PNG 截图。全帧方案不把 2100 张图落盘；变化帧方案会把唯一帧写进临时目录供编码使用。",
            "双平台行的第二次抓帧或第二次编码是同一次实测的倍数：两条中文 9:16 成片内容相同，复用只把抓帧次数从 2 降到 1，编码仍按每条成片各一次计。",
            "基线编码是两遍 libx264 medium，码率与产品 video_encoder 的像素预算一致。单遍编码调用 h264_args()，硬件不可用时回退 libx264 veryfast crf 20。",
            "720p 抓取后在编码时放大到 1080x1920。1080p 行只比较抓帧，编码仍使用 720p 变化帧，避免把两套像素混进编码差。",
            "计划里的 5–5.5 分钟还包含底层成片和质检。本表只有叠加层抓帧和这一次编码，不能直接当成全流程耗时。",
        ],
    }


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = path.with_suffix(".md")
    body = [
        f"# 包装模板 M0 测速（{payload.get('label') or 'run'}）",
        "",
        f"状态：{payload.get('status')}",
        "",
        payload.get("markdown") or "（没有对比表）",
        "",
    ]
    if payload.get("notes"):
        body.extend(["## 说明", "", *[f"- {note}" for note in payload["notes"]], ""])
    if payload.get("unmeasured_platforms"):
        body.append("## 未测平台")
        body.append("")
        for item in payload["unmeasured_platforms"]:
            body.append(f"- {item.get('platform')}：{item.get('status')}。{item.get('note', '')}")
        body.append("")
    markdown.write_text("\n".join(body), encoding="utf-8")


def _docker_available() -> str:
    binary = shutil.which("docker")
    if not binary:
        return ""
    try:
        proc = subprocess.run([binary, "info"], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return binary if proc.returncode == 0 else ""


def run_docker(args, host_report: Path) -> dict:
    binary = _docker_available()
    if not binary:
        return {"status": "未测", "reason": "本机没有可用的 Docker 守护进程"}
    output = host_report.resolve().with_name(host_report.stem + "-docker.json")
    mounts = ["-v", f"{ROOT}:{ROOT}"]
    if output.parent != ROOT and ROOT not in output.parents:
        output.parent.mkdir(parents=True, exist_ok=True)
        mounts += ["-v", f"{output.parent}:{output.parent}"]
    script = " ".join([
        "apt-get update",
        "&&", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", "-y", "--no-install-recommends", "ffmpeg",
        "&&", "python", "scripts/packaging_frame_benchmark.py",
        "--browser", "shell",
        "--label", "docker",
        "--seconds", str(args.seconds),
        "--fps", str(args.fps),
        "--out", str(output),
        *(["--skip-1080"] if args.skip_1080 else []),
    ])
    command = [
        binary, "run", "--rm",
        *mounts,
        "-w", str(ROOT),
        "-e", f"PYTHONPATH={ROOT}",
        args.docker_image,
        "bash", "-lc", script,
    ]
    print("docker " + args.docker_image, flush=True)
    proc = subprocess.run(command, text=True, timeout=7200, check=False)
    if proc.returncode != 0 or not output.exists():
        return {"status": "未测", "reason": f"docker 退出码 {proc.returncode}", "image": args.docker_image}
    payload = json.loads(output.read_text(encoding="utf-8"))
    return {"status": "measured", "image": args.docker_image, "report": str(output), "rows": payload.get("rows", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "benchmarks" / "packaging" / "reports" / "latest.json")
    parser.add_argument("--seconds", type=float, default=DURATION_S)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--install-runtime", action="store_true")
    parser.add_argument("--browser", choices=("auto", "chrome", "msedge", "shell"), default="auto")
    parser.add_argument("--label", default="")
    parser.add_argument("--skip-1080", action="store_true")
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--docker-image", default=DOCKER_IMAGE)
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args(argv)
    if args.install_runtime:
        from backend.services.packaging_runtime import install_blocking
        status = install_blocking()
        print(json.dumps({"install": status["status"], "browser": status.get("browser"), "message": status.get("message")}, ensure_ascii=False), flush=True)
        if status["status"] != "installed":
            _write(args.out, {"schema": 1, "status": "error", "error": status.get("message") or "install failed", "label": args.label})
            return 1
    work = Path(tempfile.mkdtemp(prefix="autoclip-packaging-bench-"))
    try:
        payload = asyncio.run(measure(args, work))
    except Exception as exc:  # noqa: BLE001 - the report has to exist even when the probe fails
        payload = {
            "schema": 1,
            "status": "error",
            "label": args.label or platform.system().lower(),
            "error": f"{type(exc).__name__}: {exc}",
            "host": _host_info(),
            "unmeasured_platforms": list(platform_notes("未跑到编码或抓帧")),
        }
        _write(args.out, payload)
        print(payload["error"], file=sys.stderr, flush=True)
        return 1
    finally:
        if not args.keep_workdir:
            shutil.rmtree(work, ignore_errors=True)
    if args.docker:
        docker = run_docker(args, args.out)
        payload["docker"] = {key: value for key, value in docker.items() if key != "rows"}
        payload["unmeasured_platforms"] = list(platform_notes(docker["status"]))
        if docker["status"] == "measured":
            payload["docker_markdown"] = markdown_table(docker["rows"])
    else:
        payload["docker"] = {"status": "未测", "reason": "这次没有加 --docker"}
        payload["unmeasured_platforms"] = list(platform_notes(payload["docker"]["reason"]))
    _write(args.out, payload)
    print(payload.get("markdown", ""), flush=True)
    return 0 if payload.get("status") == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
