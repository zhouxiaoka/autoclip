"""发布导出：SRT 切片、预设、ffmpeg 真导出一条（有 ffmpeg 才跑）"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(d))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(d))
    d.mkdir()
    return d


def test_slice_srt_shifts_to_zero():
    from backend.services.publish_export import slice_srt
    entries = [
        {"start_time": "00:00:08,000", "end_time": "00:00:10,000", "text": "前"},
        {"start_time": "00:00:12,000", "end_time": "00:00:14,500", "text": "中"},
        {"start_time": "00:00:20,000", "end_time": "00:00:22,000", "text": "后"},
    ]
    body = slice_srt(entries, 10.0, 16.0)
    assert "中" in body and "前" not in body and "后" not in body
    assert "00:00:02,000 --> 00:00:04,500" in body


def test_list_presets_has_vertical_and_horizontal():
    from backend.services.publish_export import list_presets
    keys = {p["key"] for p in list_presets()}
    assert keys == {"douyin", "xiaohongshu", "shorts", "bilibili", "original", "1080p60"}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="本机没有 ffmpeg")
def test_export_original_reencodes_and_is_idempotent(data_dir, tmp_path):
    from backend.core.path_utils import get_project_directory
    from backend.services.publish_export import ExportRequest, export_clip

    pid, cid = "exp1", "1"
    pdir = get_project_directory(pid)
    raw = pdir / "raw"
    raw.mkdir(parents=True)
    video = raw / "input.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=3",
         "-f", "lavfi", "-i", "sine=f=440:d=3", "-shortest", "-y", str(video)],
        check=True,
    )
    (pdir / "metadata").mkdir(parents=True, exist_ok=True)
    (pdir / "metadata" / "clips_metadata.json").write_text(json.dumps([
        {"id": cid, "generated_title": "测试片", "start_time": "00:00:00,500", "end_time": "00:00:02,500"}
    ]), encoding="utf-8")
    (pdir / "raw" / "input.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n你好世界\n\n2\n00:00:02,000 --> 00:00:03,000\n第二句\n",
        encoding="utf-8",
    )

    req = ExportRequest(pid, cid, preset="original", subtitles=True, title_card=False)
    r1 = export_clip(req)
    assert r1["ok"] and Path(r1["path"]).exists() and Path(r1["path"]).stat().st_size > 0
    assert r1.get("cached") is False
    r2 = export_clip(req)
    assert r2.get("cached") is True and r2["path"] == r1["path"]


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='本机没有 ffmpeg')
def test_1080p60_actual_file_and_cache_keep_spec(data_dir, tmp_path, monkeypatch):
    from backend.services import publish_export as export
    video = tmp_path / '24fps portrait.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=180x320:rate=24:duration=1',
                    '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac',str(video)], check=True)
    monkeypatch.setattr(export, 'find_source_video', lambda _:video)
    monkeypatch.setattr(export, 'load_clip_meta', lambda *_:{'id':'1','title':'spec','start_time':'00:00:00,000','end_time':'00:00:01,000'})
    original = export.export_clip(export.ExportRequest('spec','1','original',False,False))
    assert original['fps'] == 24 and original['width'] == 180
    req = export.ExportRequest('spec','1','1080p60',False,False)
    output = export.export_clip(req)
    assert output['path'] != original['path']
    assert (output['width'], output['height'], output['fps'], output['video_codec']) == (1920,1080,60,'h264')
    streams = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',output['path']]))['streams']
    assert next(s for s in streams if s['codec_type']=='audio')['codec_name'] == 'aac'
    assert int(next(s for s in streams if s['codec_type']=='video')['nb_frames']) == 60
    again = export.export_clip(req)
    assert again['cached'] and again['fps'] == 60 and again['width'] == 1920
    with pytest.raises(ValueError, match='固定横屏'):
        export.export_clip(export.ExportRequest('spec','1','1080p60',layout='none'))


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='本机没有 ffmpeg')
def test_studio_1080p60_reencodes_final_file_without_double_text(data_dir, tmp_path, monkeypatch):
    from backend.services import publish_export as export
    video = tmp_path / 'studio final.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=size=320x180:rate=30:duration=1',
                    '-c:v','libx264',str(video)],check=True)
    monkeypatch.setattr(export,'load_clip_meta',lambda *_:{'source_type':'studio','video_path':str(video),'title':'finished','duration_sec':1})
    def forbidden(*_):
        pytest.fail('must retain Studio rendered text instead of loading raw subtitles')
    monkeypatch.setattr(export,'find_source_video',forbidden)
    monkeypatch.setattr(export,'_load_srt_entries',forbidden)
    output=export.export_clip(export.ExportRequest('spec','studio-1','1080p60'))
    assert (output['width'],output['height'],output['fps']) == (1920,1080,60)
    assert '不重复烧录' in output['warnings'][0]
