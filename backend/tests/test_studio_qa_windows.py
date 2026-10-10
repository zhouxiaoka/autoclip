"""Packaged Windows Python must actually run the QA child.

A desktop host can be autoclip-backend.exe. Spawning that binary with -m makes
every checker skip, and the skip is easy to miss. This case junctions the real
interpreter into resources/python and runs one short clip through _spawn.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='packaged Windows runtime')


def test_packaged_runtime_spawn_skips_under_30_percent(tmp_path, monkeypatch):
    from backend.services.studio.qa import report
    from backend.services.studio.qa import schedule as qa_schedule
    from backend.utils.ffmpeg_utils import get_ffmpeg_path

    real = Path(sys.executable).resolve()
    resources = tmp_path / 'resources'
    link = resources / 'python'
    host = resources / 'autoclip-backend.exe'
    resources.mkdir()
    host.write_bytes(b'MZ')
    linked = False
    try:
        created = subprocess.run(
            ['cmd', '/c', 'mklink', '/J', str(link), str(real.parent)],
            capture_output=True, text=True, check=False,
        )
        if created.returncode != 0 or not (link / 'python.exe').is_file():
            pytest.fail(created.stderr or created.stdout or 'mklink failed')
        linked = True
        monkeypatch.setattr(qa_schedule.sys, 'executable', str(host))
        cmd, kwargs = qa_schedule._command()
        assert Path(cmd[0]) == link / 'python.exe'
        assert kwargs['creationflags'] & 0x08000000
        video = tmp_path / 'clip.mp4'
        subprocess.run([
            get_ffmpeg_path(), '-y', '-v', 'error',
            '-f', 'lavfi', '-i', 'color=c=0x202020:s=320x568:r=8:d=8',
            '-f', 'lavfi', '-i', 'anoisesrc=color=white:sample_rate=48000:duration=8:amplitude=0.2',
            '-shortest', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '36', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-ac', '1', str(video),
        ], check=True, timeout=120)
        payload = {
            'output': str(video), 'source': str(video),
            'scenes': [{'start': 0.0, 'end': 8.0, 'points': []}],
            'width': 320, 'height': 568, 'strategy_id': 'original',
            'words': [{'start': 6.0, 'end': 7.4, 'text': 'done.'}],
            'captions': False, 'title': False, 'packaged': False, 'title_y': 0.12,
            'limits': report.checker_limits(8),
        }
        body = qa_schedule._spawn(payload)
        skips = [row for row in body['checks'] if row['outcome'] == 'skip']
        summary = {
            'skip_rate': len(skips) / len(body['checks']),
            'checks': [
                {key: row[key] for key in ('checker', 'outcome', 'bucket', 'duration_ms')}
                for row in body['checks']
            ],
        }
        assert len(body['checks']) == len(report.CHECKERS)
        assert len(skips) / len(body['checks']) < 0.30, json.dumps(summary)
    finally:
        if linked:
            subprocess.run(['cmd', '/c', 'rmdir', str(link)], check=False)
