"""Changed-frame capture and an ffv1 overlay that is replaced only after a full encode."""
import asyncio
import subprocess
from pathlib import Path

import pytest

from backend.core.sentry_setup import before_send
from backend.services.studio import packaging_html as html


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


def _png(folder: Path) -> Path:
    png = folder / 'frame.png'
    subprocess.run([
        'ffmpeg', '-hide_banner', '-y', '-f', 'lavfi', '-i', 'color=c=red@0.5:s=16x16:d=0.04,format=rgba',
        '-frames:v', '1', '-update', '1', str(png),
    ], check=True, capture_output=True)
    return png


def test_ffv1_overlay_keeps_alpha_and_drops_the_listing(tmp_path):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    png = _png(tmp_path)
    dest = tmp_path / 'overlay.mkv'
    html.encode_ffv1([(png, 2), (png, 1)], dest, fps=30, timeout=30)
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,pix_fmt',
        '-of', 'csv=p=0', str(dest),
    ], check=True, capture_output=True, text=True)
    assert probe.stdout.strip() == 'ffv1,yuva444p'
    assert 'ffv1' in html.ffv1_args() and 'yuva444p' in html.ffv1_args()
    assert list(tmp_path.glob('*.ffconcat')) == []
    assert list(tmp_path.glob('*.partial')) == []


def test_a_quoted_frame_path_round_trips_through_concat(tmp_path):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    folder = tmp_path / "it's a"
    folder.mkdir()
    png = _png(folder)
    quoted = html.concat_quote(png)
    assert "\\'" in quoted
    dest = tmp_path / 'quoted.mkv'
    html.encode_ffv1([(png, 1)], dest, fps=30, timeout=30)
    assert dest.is_file() and dest.stat().st_size > 0


def test_encode_failure_deletes_the_partial_and_leaves_dest_absent(tmp_path):
    dest = tmp_path / 'overlay.mkv'
    png = tmp_path / 'frame.png'
    png.write_bytes(b'png')

    class Proc:
        returncode = 1
        stderr = 'encode failed /home/user/secret.mkv'

    def run(cmd):
        Path(cmd[-1]).write_bytes(b'partial-bytes')
        return Proc()

    with pytest.raises(html.OverlayEncodeError) as caught:
        html.encode_ffv1([(png, 1)], dest, fps=30, timeout=5, run=run)
    assert str(caught.value) == 'encode'
    assert not dest.exists()
    assert not dest.with_name(dest.name + '.partial').exists()
    assert list(tmp_path.glob('*.ffconcat')) == []


def test_encode_timeout_deletes_the_partial(tmp_path):
    dest = tmp_path / 'overlay.mkv'
    png = tmp_path / 'frame.png'
    png.write_bytes(b'png')

    def run(cmd):
        Path(cmd[-1]).write_bytes(b'partial-bytes')
        raise subprocess.TimeoutExpired(cmd, 1)

    with pytest.raises(html.OverlayEncodeError) as caught:
        html.encode_ffv1([(png, 1)], dest, fps=30, timeout=1, run=run)
    assert str(caught.value) == 'timeout'
    assert not dest.exists()
    assert not dest.with_name(dest.name + '.partial').exists()


def test_a_non_positive_budget_does_not_start_ffmpeg(tmp_path):
    dest = tmp_path / 'overlay.mkv'
    with pytest.raises(html.OverlayEncodeError) as caught:
        html.encode_ffv1([(tmp_path / 'frame.png', 1)], dest, fps=30, timeout=0, run=lambda _cmd: (_ for _ in ()).throw(AssertionError('ffmpeg')))
    assert str(caught.value) == 'timeout'
    assert not dest.exists()


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
