"""R19 #115 (Dong): outside the gate suites the gate still runs; conftest only simulates an installed Whisper."""
import pytest

from backend.services import whisper_runtime
from backend.services.studio import readiness


@pytest.mark.reads_whisper_stand_in
def test_conftest_simulates_installed_whisper_not_a_disabled_gate():
    assert whisper_runtime.get_status()['status'] == 'installed'
    assert readiness.ensure_local_transcription_for_import.__module__ == 'backend.services.studio.readiness'
    assert readiness.ensure_local_transcription_for_import.__name__ == 'ensure_local_transcription_for_import'


def test_gate_function_is_called_and_passes_in_a_non_gate_suite(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    calls = []
    real = readiness.ensure_local_transcription_for_import

    def spy(**kwargs):
        calls.append(kwargs)
        return real(**kwargs)  # the real gate decides
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', spy)
    video = tmp_path / 'v.mp4'; video.write_bytes(b'\x00' * 64)
    readiness.ensure_local_transcription_for_paths(video)  # no settings file -> default local Whisper
    assert calls and calls[0]['srt_available'] is False


def test_same_call_blocks_when_a_test_simulates_not_installed(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'missing'})
    monkeypatch.setattr(readiness, '_source_cannot_take_subtitle_route', lambda *a: False)
    video = tmp_path / 'v.mp4'; video.write_bytes(b'\x00' * 64)
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_paths(video)
