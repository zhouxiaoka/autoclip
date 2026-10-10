"""70 秒杂志风测速脚本的纯计算：帧哈希、两遍编码参数、对比表。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("packaging_frame_benchmark", ROOT / "scripts" / "packaging_frame_benchmark.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def test_default_fixture_is_seventy_seconds_at_thirty_fps():
    fill = bench.build_fill()
    assert fill["frame_count"] == 2100
    assert fill["duration_s"] == 70
    assert len(fill["words"]) == 210
    for index in range(2100):
        assert bench.frame_index(index / 30) == index
        assert bench.state_at(fill, index / 30)["word"] >= 0


def test_changed_frames_fall_in_the_planned_reduction_band():
    fill = bench.build_fill()
    unique = bench.unique_state_count(fill)
    ratio = unique / fill["frame_count"]
    assert unique > len(fill["words"])
    assert 0.08 <= ratio <= 0.20


def test_hash_changes_only_when_the_visible_state_changes():
    fill = bench.build_fill()
    first = bench.state_at(fill, 0)
    assert first["hook"] == "一句判断"
    assert first["hash"] == bench.state_at(fill, 9 / 30)["hash"]
    assert first["hash"] != bench.state_at(fill, 10 / 30)["hash"]


def test_two_pass_baseline_matches_the_product_bitrate_and_single_pass_uses_h264_args(tmp_path):
    concat = tmp_path / "overlay.ffconcat"
    output = tmp_path / "out.mp4"
    passes = bench.two_pass_commands("ffmpeg", concat, output, 1080, 1920, 30, 70, tmp_path / "pass")
    assert len(passes) == 2
    assert passes[0][passes[0].index("-pass") + 1] == "1"
    assert passes[1][passes[1].index("-pass") + 1] == "2"
    assert passes[0][passes[0].index("-c:v") + 1] == "libx264"
    assert passes[0][passes[0].index("-preset") + 1] == "medium"
    from backend.services.video_encoder import _bitrate, h264_args
    assert passes[0][passes[0].index("-b:v") + 1] == str(_bitrate(1080, 1920))
    video_args = h264_args(1080, 1920, "libx264")
    once = bench.single_pass_command("ffmpeg", concat, output, 1080, 1920, 30, 70, video_args)
    assert "-pass" not in once
    assert once[once.index("-c:v") + 1] == "libx264"
    assert video_args[video_args.index("-crf") + 1] == "20"


def test_comparison_table_scales_reuse_and_keeps_capture_plus_encode():
    captures = {
        "serial_all_720": {"seconds": 100, "frames_shot": 2100},
        "changed_720": {"seconds": 20, "frames_shot": 220},
        "parallel_all_720": {"seconds": 60, "frames_shot": 2100},
        "parallel_changed_720": {"seconds": 12, "frames_shot": 230},
        "serial_all_1080": {"seconds": 160, "frames_shot": 2100},
    }
    encodes = {"two_pass": {"seconds": 80}, "one_pass": {"seconds": 25}}
    rows = {row["name"]: row for row in bench.comparison_rows(captures, encodes)}
    baseline = rows["基线·单条：720p 全帧、单页、两遍 x264"]
    assert baseline["capture_s"] == 100
    assert baseline["encode_s"] == 80
    assert baseline["total_s"] == 180
    assert baseline["frames"] == 2100
    reused = rows["优化1·双平台叠加层复用"]
    doubled = rows["优化1·双平台不复用（对照）"]
    assert doubled["capture_s"] == 200 and doubled["frames"] == 4200
    assert reused["capture_s"] == 100 and reused["encode_s"] == 160
    assert reused["total_s"] < doubled["total_s"]
    changed = rows["优化2·只抓变化帧（单条，两遍编码）"]
    assert changed["frames"] == 220
    assert changed["total_s"] == 100
    combined = rows["组合·单条：变化帧 + 2 页并行 + 单遍"]
    assert combined["capture_s"] == 12 and combined["encode_s"] == 25
    assert combined["total_s"] == combined["capture_s"] + combined["encode_s"]
    table = bench.markdown_table(list(rows.values()))
    assert "基线·单条" in table and "抓帧数" in table


def test_ffconcat_holds_each_unique_frame_for_its_span(tmp_path):
    frame = tmp_path / "f.png"
    frame.write_bytes(b"png")
    text = bench.ffconcat_text([{"path": str(frame), "count": 10}, {"path": str(frame), "count": 5}], 30)
    assert text.startswith("ffconcat version 1.0")
    assert "duration 0.333333" in text
    assert "duration 0.166667" in text
    assert text.strip().splitlines()[-1].startswith("file ")


def test_unmeasured_platforms_stay_explicit():
    notes = bench.platform_notes("本机没有可用的 Docker 守护进程")
    by_name = {item["platform"]: item for item in notes}
    assert by_name["macOS"]["status"] == "未测"
    assert "cursor-agent-worker-114e0e00e2" in by_name["macOS"]["owner"]
    assert "uname -m" in by_name["macOS"]["note"]
    assert by_name["Windows"]["status"] == "未测"
    assert "腾讯云" in by_name["Windows"]["machine"]
    assert by_name["Docker"]["status"] == "未测"
