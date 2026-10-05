"""Best-effort pause detection must survive unavailable/foreign-encoded stderr."""
from types import SimpleNamespace
import subprocess
import sys

import pytest

from backend.services.studio import boundaries
from backend.services import render_limits
from backend.utils import ffmpeg_utils

pytestmark = pytest.mark.stdlib_only


@pytest.fixture
def capture(monkeypatch):
    monkeypatch.setattr(ffmpeg_utils, 'get_ffmpeg_path', lambda: 'fixture-ffmpeg')
    monkeypatch.setattr(render_limits, 'low_priority', lambda cmd: (cmd, {}))
    return boundaries.audio_silences('公开素材.mp4')


@pytest.mark.parametrize('stderr', [None, 0, [], {}, object()],
                         ids=['missing', 'integer', 'list', 'dict', 'opaque'])
def test_unavailable_stderr_keeps_best_effort_pause_fallback(monkeypatch, capture, stderr):
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stderr=stderr))
    assert capture(5.0, 7.0) == []


@pytest.mark.parametrize('container', [bytes, bytearray])
def test_binary_stderr_retains_actual_silence_offsets(monkeypatch, capture, container):
    log = container(b'\xff filename\n[silencedetect] silence_start: 0.5\n[silencedetect] silence_end: 1.5 | silence_duration: 1.0\n')
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stderr=log))
    assert capture(5.0, 7.0) == [(5.5, 6.5)]


def test_non_ascii_child_stderr_ignores_locale_and_replaces_invalid_bytes(monkeypatch, capture):
    # A real child process, with the restrictive default codec used as a stand-in
    # for a Windows code page. This is not a native Windows/media acceptance test.
    monkeypatch.setattr(subprocess, '_text_encoding', lambda: 'ascii')
    run = subprocess.run
    payload = ('素材 Ω\n[silencedetect] silence_start: 0.5\n'
               '[silencedetect] silence_end: 1.5 | silence_duration: 1.0\n').encode('utf-8') + b'\xff\n'
    calls = []

    def child(_cmd, **kwargs):
        calls.append(kwargs)
        return run([sys.executable, '-c', f'import os; os.write(2, {payload!r})'], **kwargs)

    monkeypatch.setattr(subprocess, 'run', child)
    assert capture(5.0, 7.0) == [(5.5, 6.5)]
    assert calls[0]['encoding'] == 'utf-8'
    assert calls[0]['errors'] == 'replace'
    assert calls[0]['capture_output'] is True
    assert calls[0]['text'] is True
    assert calls[0]['timeout'] == 60
    assert calls[0]['check'] is False


@pytest.mark.parametrize('log, expected', [
    ('warning: no measurable pauses\n', []),
    ('silence_start: 0.5\n', []),
    ('silence_start: 0.5\nsilence_end: 1.5 | silence_duration: 1.0\n', [(5.5, 6.5)]),
])
def test_existing_text_pause_semantics_remain(monkeypatch, capture, log, expected):
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stderr=log))
    assert capture(5.0, 7.0) == expected


@pytest.mark.parametrize('error', [OSError('synthetic missing binary'),
                                  subprocess.TimeoutExpired('fixture-ffmpeg', 60)])
def test_existing_subprocess_failure_fallback_remains(monkeypatch, capture, error):
    def unavailable(*args, **kwargs):
        raise error
    monkeypatch.setattr(subprocess, 'run', unavailable)
    assert capture(5.0, 7.0) == []
