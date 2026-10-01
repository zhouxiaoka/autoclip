"""Install a wheel outside the checkout and exercise its real portrait detector.

Run with the base requirements, OpenCV and FFmpeg available. No provider/model
requests are made; the ONNX model must come from the installed wheel itself.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def verify_installed(args):
    import backend
    from backend.services.studio import framing, jobs

    root = Path(args.installed_root).resolve()
    assert Path(backend.__file__).resolve().is_relative_to(root), "checkout backend imported"
    assert framing.MODEL.resolve().is_relative_to(root), "checkout ONNX model used"
    assert framing.MODEL.is_file(), f"wheel is missing face detector: {framing.MODEL.name}"
    license_path = framing.MODEL.parent / "face_detection_yunet-LICENSE.txt"
    assert license_path.is_file(), "wheel is missing YuNet license"
    assert "MIT License" in license_path.read_text(encoding="utf-8")
    assert framing.is_installed(), "OpenCV is required for the wheel acceptance check"

    # Font presence alone is insufficient: CoreText can reject a family while
    # FFmpeg exits successfully and renders missing-glyph boxes.
    from backend.services.publish_export import _escape_filter_path
    from backend.services.studio import packaging_render
    from backend.services.studio.models import Packaging, Scene
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    assert packaging_render.FONT_DIR.resolve().is_relative_to(root)
    scene = Scene(id="font", start=0, end=1)
    packaging = Packaging(template="podcast_en", audience_language="zh",
                          title_lines=["中文字体测试"],
                          cues=[{"start":0, "end":1, "text":"字幕应显示中文"}])
    ass = Path(args.report).parent / "font.ass"
    ass.write_text(packaging_render.scene_ass(packaging, [scene], 0), encoding="utf-8")
    graph = (f"ass='{_escape_filter_path(ass)}':"
             f"fontsdir='{_escape_filter_path(packaging_render.FONT_DIR)}'")
    font_check = subprocess.run([
        get_ffmpeg_path(), "-v", "verbose", "-f", "lavfi", "-i",
        "color=black:s=1080x1920:d=1", "-vf", graph, "-frames:v", "1", "-f", "null", "-",
    ], capture_output=True, text=True, timeout=30, check=True)
    selections = "\n".join(line for line in font_check.stderr.splitlines() if "fontselect:" in line)
    assert "NotoSansSC" in selections, selections
    assert "failed to find any fallback" not in selections, selections

    # Scan actual frame pairs, not stored tracks from a previously completed job.
    value = {
        "id": "wheel-framing", "title": "Wheel portrait acceptance",
        "aspect": "portrait", "layout": "crop",
        "scenes": [{"id": "speaker", "start": args.start, "end": args.start + args.length}],
    }
    scans = {}
    results = []
    for name, window in (("podcast", None), ("interview", jobs.INTERVIEW_WINDOW)):
        scenes, mode = jobs._speaker_framing(
            value, Path(args.video), window=window, wait_sec=0, scans=scans,
        )
        assert mode == "speaker", f"{name} unexpectedly fell back: {mode}"
        assert scenes and any(
            point["mode"] == "crop" for scene in scenes for point in scene["crop_track"]
        ), f"{name} has no speaker crop"
        results.append({"style": name, "framing": mode, "scenes": scenes})
    detected = next(iter(scans.values()))
    return {
        "status": "passed", "backend_version": backend.__version__,
        "model_sha256": hashlib.sha256(framing.MODEL.read_bytes()).hexdigest(),
        "model_license": "MIT", "faces": sum(scan["faces"] for scan in detected),
        "samples": sum(scan["samples"] for scan in detected), "styles": results,
        "cjk_font": "passed", "paid_model_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", nargs="?", help="built wheel to install and verify")
    parser.add_argument("--video", required=True, help="local video with a visible speaker")
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--length", type=float, default=5)
    parser.add_argument("--opencv-dir", help="optional existing on-demand OpenCV installation")
    parser.add_argument("--report", help="save the acceptance report as JSON")
    parser.add_argument("--installed-root", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.installed_root:
        result = verify_installed(args)
        Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "styles"}))
        return
    if not args.wheel:
        parser.error("wheel is required")
    wheel = Path(args.wheel).resolve()
    video = Path(args.video).resolve()
    assert wheel.is_file() and video.is_file(), "wheel and input video must exist"
    with tempfile.TemporaryDirectory(prefix="ac-wheel-acceptance-") as temp:
        folder = Path(temp)
        installed = folder / "installed"
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
            "--target", str(installed), str(wheel),
        ], check=True, cwd=folder)
        paths = [str(installed)]
        if args.opencv_dir:
            paths.append(str(Path(args.opencv_dir).resolve()))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(paths),
                   AUTOCLIP_DATA_DIR=str(folder / "data"), AUTOCLIP_APP_DIR=str(folder / "data"),
                   DATABASE_URL="sqlite:///" + str(folder / "isolated.sqlite"), SENTRY_DSN="")
        report = folder / "report.json"
        subprocess.run([
            sys.executable, str(Path(__file__).resolve()), "--installed-root", str(installed),
            "--video", str(video), "--start", str(args.start), "--length", str(args.length),
            "--report", str(report),
        ], check=True, cwd=folder, env=env)
        if args.report:
            Path(args.report).write_bytes(report.read_bytes())


if __name__ == "__main__":
    main()
