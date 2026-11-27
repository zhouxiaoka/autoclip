"""Regression tests for Sentry PYTHON-FASTAPI-8A/8B (UnknownTimeZoneError) and PYTHON-FASTAPI-8K (audio.has_audio OSError)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.services.project_service import ProjectService
from backend.services.studio import audio, boundaries, jobs


def test_convert_utc_to_local_does_not_depend_on_pytz_zoneinfo(monkeypatch):
    """PYTHON-FASTAPI-8A/8B: _convert_utc_to_local must not fail when pytz zoneinfo is missing."""
    import sys

    class _BrokenPytz:
        def timezone(self, name):
            raise RuntimeError(f"UnknownTimeZoneError: {name}")

    monkeypatch.setitem(sys.modules, "pytz", _BrokenPytz())
    svc = ProjectService.__new__(ProjectService)
    naive_utc = datetime(2026, 11, 27, 4, 30, 0)
    converted = svc._convert_utc_to_local(naive_utc)
    assert converted is not None
    assert converted.utcoffset() == timedelta(hours=8)
    assert (converted.hour, converted.minute) == (12, 30)
    assert svc._convert_utc_to_local(None) is None
    # Aware UTC timestamp also converts cleanly
    aware = datetime(2026, 11, 27, 4, 30, 0, tzinfo=timezone.utc)
    assert svc._convert_utc_to_local(aware) == converted


def test_complete_thought_bounds_degrades_when_has_audio_raises_oserror(monkeypatch):
    """PYTHON-FASTAPI-8K: transient OSError in audio.has_audio must degrade to silences=None."""
    from backend.services import publish_export

    clips = [{"id": "1", "start_time": "00:00:00,000", "end_time": "00:00:30,000", "generated_title": "t"}]
    monkeypatch.setattr(
        publish_export,
        "_load_srt_entries",
        lambda _pid: [{"start_time": "00:00:00,000", "end_time": "00:00:30,000", "text": "hello"}],
    )
    monkeypatch.setattr(jobs, "source", lambda _pid: "video.mp4")

    def _boom(_video):
        raise OSError("ffprobe blocked on Windows")

    monkeypatch.setattr(audio, "has_audio", _boom)
    seen = {}

    def _fake_refine(rows, in_clips, call, silences):
        seen["silences"] = silences
        return in_clips

    monkeypatch.setattr(boundaries, "refine_clips", _fake_refine)
    out = jobs._complete_thought_bounds("p1", clips)
    assert out == clips
    assert seen["silences"] is None
