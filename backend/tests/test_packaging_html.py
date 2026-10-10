"""Changed-frame capture, ffv1 alpha, and an encoder fallback that cannot fail the export."""
import asyncio
import subprocess
from pathlib import Path

import pytest

from backend.core.sentry_setup import before_send
from backend.services.studio import packaging_html as html
from backend.services.video_encoder import SOFTWARE


def test_only_changed_frames_are_captured_and_pages_run_together():
    hashes = ['a', 'a', 'a', 'b', 'b', 'c']
    shots = []

    async def render(page, time):
        return hashes[int(round(time * 30))]

    async def shoot(page, index):
        shots.append((page, index))
        return b'png'

    frames = asyncio.run(html.capture_changed(len(hashes), 30, render, shoot, pages=2))
    assert html.split_indices(6, 2) == [[0, 1, 2], [3, 4, 5]]
    assert {page for page, _index in shots} == {0, 1}
    assert [(frame['index'], frame['count']) for frame in frames] == [(0, 3), (3, 2), (5, 1)]
    assert sum(frame['count'] for frame in frames) == 6
    assert len(shots) == 3


def test_a_repeated_hash_collapses_to_one_hold():
    runs = html.collapse_hashes(['hook', 'hook', 'word', 'word', 'word'])
    assert [(run['index'], run['count']) for run in runs] == [(0, 2), (2, 3)]


def test_flag_off_skips_the_overlay_without_calling_it_a_failure():
    event = html.skipped_event('flag_off', flow_id='t-abc123def456', strategy_id='douyin')
    assert event['downgrade_reason'] == 'flag_off'
    assert event['downgraded'] is False
    assert event['failure_reason'] == 'none'
    assert event['template'] == 'classic'
    assert html.templates_requested({'pkg_templates_v1': False}) is False
    assert html.templates_requested({'pkg_templates_v1': True}) is True
    assert html.templates_requested(None) is False


def test_probe_tries_every_hardware_encoder_and_a_failed_probe_uses_libx264(monkeypatch):
    html.reset_encoder_cache()
    seen = []

    def works(_ffmpeg, name):
        seen.append(name)
        return name == 'h264_qsv'

    monkeypatch.setattr('backend.services.video_encoder._works', works)
    assert html.choose_encoder() == 'h264_qsv'
    assert seen == ['h264_nvenc', 'h264_qsv']

    html.reset_encoder_cache()
    monkeypatch.setattr('backend.services.video_encoder._works', lambda *_args: False)
    assert html.choose_encoder() == SOFTWARE

    html.reset_encoder_cache()
    def boom(*_args):
        raise OSError('device node /dev/dri/secret')

    monkeypatch.setattr('backend.services.video_encoder._works', boom)
    assert html.choose_encoder() == SOFTWARE


def test_hardware_encode_failure_falls_back_to_libx264_veryfast(monkeypatch, tmp_path):
    html.reset_encoder_cache()
    monkeypatch.setattr(html, 'choose_encoder', lambda: 'h264_nvenc')
    calls = []

    class Proc:
        def __init__(self, code):
            self.returncode = code
            self.stderr = 'nvenc failed on /tmp/private.mp4'

    def run(cmd):
        calls.append(cmd)
        return Proc(0 if SOFTWARE in cmd else 1)

    result = html.encode_picture(tmp_path / 'base.mp4', tmp_path / 'overlay.mkv', tmp_path / 'out.mp4', 320, 568, grade="eq=contrast=1.04", run=run)
    assert result['ok'] is True
    assert result['encoder'] == SOFTWARE
    assert result['failure_reason'] == 'none'
    assert result['os'] == 'linux'
    assert isinstance(result['cpu_count'], int) and result['cpu_count'] >= 1
    assert 'private' not in str(result)
    software = calls[-1]
    assert SOFTWARE in software and 'veryfast' in software
    assert 'h264_nvenc' in calls[0]


def test_a_timeout_on_hardware_still_retries_software(monkeypatch, tmp_path):
    html.reset_encoder_cache()
    monkeypatch.setattr(html, 'choose_encoder', lambda: 'h264_videotoolbox')

    class Proc:
        returncode = 0
        stderr = ''

    def run(cmd):
        if 'h264_videotoolbox' in cmd:
            raise subprocess.TimeoutExpired(cmd, 1)
        return Proc()

    result = html.encode_picture(tmp_path / 'a.mp4', tmp_path / 'b.mkv', tmp_path / 'c.mp4', 64, 64, run=run)
    assert result['ok'] is True and result['encoder'] == SOFTWARE


def test_software_encode_failure_is_reported_without_failing_closed_on_the_encoder_name(monkeypatch, tmp_path):
    html.reset_encoder_cache()
    monkeypatch.setattr(html, 'choose_encoder', lambda: SOFTWARE)

    class Proc:
        returncode = 1
        stderr = 'filter error /home/user/secret.mp4'

    result = html.encode_picture(tmp_path / 'a.mp4', tmp_path / 'b.mkv', tmp_path / 'c.mp4', 64, 64, run=lambda _cmd: Proc())
    assert result['ok'] is False
    assert result['failure_reason'] == 'encode'
    assert result['encoder'] == SOFTWARE
    assert 'secret' not in str(result)
    with pytest.raises(html.OverlayEncodeError) as caught:
        raise html.OverlayEncodeError('encode')
    assert str(caught.value) == 'encode'


def test_ffv1_overlay_keeps_alpha(tmp_path):
    png = tmp_path / 'frame.png'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.5:s=16x16:d=0.04,format=rgba',
        '-frames:v', '1', '-update', '1', str(png),
    ], check=True, capture_output=True)
    dest = tmp_path / 'overlay.mkv'
    html.encode_ffv1([(png, 2), (png, 1)], dest, fps=30)
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,pix_fmt',
        '-of', 'csv=p=0', str(dest),
    ], check=True, capture_output=True, text=True)
    assert probe.stdout.strip() == 'ffv1,yuva444p'
    assert 'ffv1' in html.ffv1_args() and 'yuva444p' in html.ffv1_args()


def test_packaging_html_sentry_phase_drops_paths_and_captions(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    event = {
        'tags': {'area': 'studio', 'phase': 'packaging_html', 'error_code': 'unexpected', 'path': str(tmp_path / 'secret.mp4')},
        'exception': {'values': [{'type': 'RuntimeError', 'value': f'failed {tmp_path}/clip.mp4 原话字幕'}]},
    }
    clean = before_send(event)
    assert clean['tags']['phase'] == 'packaging_html'
    blob = str(clean)
    assert 'secret' not in blob and '原话' not in blob and 'clip.mp4' not in blob
