"""C2: local Whisper has its own wall clock, separate from the clip-job budget.

The production/render cap stays paused for this CPU work. A transcribe that
never calls an LLM still has to stop, and segment progress still moves.
"""
import threading
import time
from types import SimpleNamespace

import pytest

from backend.core.failure_codes import user_visible_error
from backend.core.job_budget import bound_clip_job, ensure_clip_job_budget
from backend.core.sentry_setup import studio_error_code
from backend.pipeline.failures import failure_from_speech_error
from backend.tests.test_whisper_local_subtitle import _install_fake_whisper, _recognizer
from backend.utils import speech_recognizer, transcription_progress
from backend.utils.speech_recognizer import (
    WHISPER_MIN_BUDGET_SEC,
    WHISPER_TIMEOUT_MESSAGE,
    WHISPER_UNKNOWN_DURATION_BUDGET_SEC,
    SpeechRecognitionConfig,
    SpeechRecognitionError,
    local_whisper_budget_seconds,
)


def test_budget_is_three_times_duration_with_a_floor_unless_the_caller_set_one():
    assert local_whisper_budget_seconds(0, 100) == 300
    assert local_whisper_budget_seconds(0, 10) == WHISPER_MIN_BUDGET_SEC
    assert local_whisper_budget_seconds(0, None) == WHISPER_UNKNOWN_DURATION_BUDGET_SEC
    assert local_whisper_budget_seconds(0, 0) == WHISPER_UNKNOWN_DURATION_BUDGET_SEC
    # A positive timeout is the caller's cap: not raised to the floor or to 3×.
    assert local_whisper_budget_seconds(25, 100) == 25
    assert local_whisper_budget_seconds(500, 10) == 500


def test_timeout_phrase_is_a_studio_timeout_and_not_a_setup_error():
    failure = failure_from_speech_error(WHISPER_TIMEOUT_MESSAGE)
    assert failure.code == "timeout"
    assert failure.stage == "SUBTITLE"
    assert studio_error_code(failure) == "timeout"
    visible = user_visible_error(failure)
    assert "时间上限" in visible
    assert "已停止" in visible
    # Nearby timeout copy must keep its own code. Only the Whisper cap phrase maps here.
    sense = failure_from_speech_error("SenseVoice 转写超时，请缩短视频或增加转写超时时间")
    assert sense.code == "subtitle_setup"
    assert failure_from_speech_error("音频提取超时").code == "subtitle_setup"


def _video(tmp_path, monkeypatch, model, *, probe=10.0):
    monkeypatch.delenv("AUTOCLIP_WHISPER_DEVICE", raising=False)
    _install_fake_whisper(monkeypatch, model)
    monkeypatch.setattr(speech_recognizer, "probe_media_duration", lambda _path: probe)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    return video


def _clock(monkeypatch):
    now = {"t": 1_000.0}
    monkeypatch.setattr(speech_recognizer.time, "monotonic", lambda: now["t"])
    return now


def _segment(end, text="片段"):
    return SimpleNamespace(start=max(0.0, end - 1), end=end, text=text, words=[])


class _Model:
    def __init__(self, *args, **kwargs):
        pass


def test_timeout_zero_stops_near_three_times_duration(tmp_path, monkeypatch):
    """timeout=0 uses ~3× duration, not the short-clip floor and not unlimited."""
    now = _clock(monkeypatch)
    yielded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                for index in range(20):
                    now["t"] += 100
                    yielded.append(index)
                    yield _segment(100 * (index + 1))
            return lazy(), SimpleNamespace(duration=200, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=200)
    with pytest.raises(SpeechRecognitionError) as caught:
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", SpeechRecognitionConfig())
    assert "时间上限" in str(caught.value)
    # 3×200s = 600s, step 100s → a handful of segments. The 180s floor would stop sooner.
    assert 5 <= len(yielded) <= 9
    assert not (tmp_path / "out.srt").exists()


def test_floor_keeps_a_short_clip_from_being_cut_at_three_times(tmp_path, monkeypatch):
    now = _clock(monkeypatch)
    yielded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                for index in range(20):
                    now["t"] += 30
                    yielded.append(index)
                    yield _segment(float(index + 1))
            return lazy(), SimpleNamespace(duration=10, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=10)
    with pytest.raises(SpeechRecognitionError) as caught:
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", SpeechRecognitionConfig())
    assert "时间上限" in str(caught.value)
    # 3×10s = 30s, but the floor is 180s. Step 30s → several segments, not one.
    assert 6 <= len(yielded) <= 8


def test_explicit_timeout_is_not_inflated_to_three_times_duration(tmp_path, monkeypatch):
    now = _clock(monkeypatch)
    yielded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                for index in range(12):
                    now["t"] += 25
                    yielded.append(index)
                    yield _segment(25 * (index + 1))
            return lazy(), SimpleNamespace(duration=200, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=200)
    config = SpeechRecognitionConfig(timeout=50)
    with pytest.raises(SpeechRecognitionError) as caught:
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", config)
    assert str(caught.value) == WHISPER_TIMEOUT_MESSAGE
    # 50s cap, step 25s. 3×200s would have allowed the whole iterator.
    assert 2 <= len(yielded) <= 4
    failure = failure_from_speech_error(str(caught.value))
    assert failure.code == "timeout"
    assert studio_error_code(failure) == "timeout"


def test_known_duration_replaces_the_unknown_provisional_cap(tmp_path, monkeypatch):
    now = _clock(monkeypatch)
    yielded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                for index in range(8):
                    now["t"] += 60
                    yielded.append(index)
                    yield _segment(float(index + 1))
            return lazy(), SimpleNamespace(duration=20, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=None)
    with pytest.raises(SpeechRecognitionError):
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", SpeechRecognitionConfig())
    # Probe missed the length. _info.duration=20 replaces the 30min fallback
    # with the 180s floor. Step 60s cannot walk the whole 30 minutes.
    assert 3 <= len(yielded) <= 5


def test_stuck_decode_between_segments_fails_without_waiting_for_it(tmp_path, monkeypatch):
    release = threading.Event()
    entered = threading.Event()

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                entered.set()
                release.wait(30)
                yield _segment(1.0)
            return lazy(), SimpleNamespace(duration=30, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=30)
    config = SpeechRecognitionConfig(timeout=1)
    started = time.perf_counter()
    try:
        with pytest.raises(SpeechRecognitionError) as caught:
            _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", config)
    finally:
        release.set()
    elapsed = time.perf_counter() - started
    assert entered.is_set()
    assert "时间上限" in str(caught.value)
    assert failure_from_speech_error(str(caught.value)).code == "timeout"
    # The blocked next() is abandoned at the cap. It must not sit on the 30s wait.
    assert elapsed < 3
    assert not (tmp_path / "out.srt").exists()


def test_slow_segments_stop_on_the_cap_and_do_not_spend_the_clip_budget(tmp_path, monkeypatch):
    yielded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                from backend.core import job_budget
                budget = job_budget._current.get()
                assert budget is not None and budget.pause_depth >= 1 and budget.paused_at is not None
                for index in range(40):
                    time.sleep(0.05)
                    yielded.append(index)
                    yield _segment(float(index + 1), text="慢")
            return lazy(), SimpleNamespace(duration=30, language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=30)
    config = SpeechRecognitionConfig(timeout=1)
    from backend.core.job_budget import _current
    with bound_clip_job(0.4):
        before = _current.get().remaining()
        with pytest.raises(SpeechRecognitionError) as caught:
            _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", config)
        drop = before - _current.get().remaining()
        ensure_clip_job_budget()
    assert "时间上限" in str(caught.value)
    assert 0 < len(yielded) < 40
    # The ~1s of Whisper work ran inside pause_clip_job_budget, so the 0.4s
    # production cap is still intact and barely moved.
    assert drop < 0.25


def test_model_download_stays_outside_the_whisper_clock(tmp_path, monkeypatch):
    """Download is paused from the provider budget, and not cut by the transcribe cap."""
    from backend.core.job_budget import _current
    from backend.services.whisper_model_manager import WhisperModelManager

    downloaded = []

    class Model(_Model):
        def transcribe(self, path, **kwargs):
            return [_segment(1.0, text="已下载")], SimpleNamespace(duration=10, language="zh")

    def ensure(self, name):
        time.sleep(0.35)
        downloaded.append(name)
        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()
        return snapshot

    video = _video(tmp_path, monkeypatch, Model, probe=10)
    monkeypatch.setattr(WhisperModelManager, "ensure_downloaded", ensure)
    output = tmp_path / "out.srt"
    config = SpeechRecognitionConfig()
    config.timeout = 0.05  # shorter than the download; the transcribe itself is instant
    with bound_clip_job(0.5):
        before = _current.get().remaining()
        _recognizer()._generate_subtitle_whisper_local(video, output, config)
        drop = before - _current.get().remaining()
        ensure_clip_job_budget()
    assert downloaded == ["base"]
    assert "已下载" in output.read_text(encoding="utf-8")
    # 0.35s of download must not land on the 0.5s clip budget.
    assert drop < 0.2


def test_missing_info_duration_still_reports_against_the_probed_length(tmp_path, monkeypatch):
    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                yield _segment(4.0)
                yield _segment(8.0)
            return lazy(), SimpleNamespace(language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=8.0)
    seen = []
    with transcription_progress.reporting(seen.append):
        _recognizer()._generate_subtitle_whisper_local(video, tmp_path / "out.srt", SpeechRecognitionConfig())
    assert seen[0] == pytest.approx(0.5)
    assert seen[-1] == pytest.approx(1.0)
    assert "片段" in (tmp_path / "out.srt").read_text(encoding="utf-8")


def test_unknown_length_keeps_a_heartbeat_while_the_next_segment_is_blocked(tmp_path, monkeypatch):
    class Model(_Model):
        def transcribe(self, path, **kwargs):
            def lazy():
                yield _segment(1.0, text="先")
                time.sleep(0.8)
                yield _segment(2.0, text="后")
            return lazy(), SimpleNamespace(language="zh")

    video = _video(tmp_path, monkeypatch, Model, probe=None)
    seen = []
    with transcription_progress.reporting(seen.append):
        _recognizer()._generate_subtitle_whisper_local(
            video, tmp_path / "out.srt", SpeechRecognitionConfig(timeout=5),
        )
    assert any(0 < value < 1 for value in seen)
    assert seen[-1] == pytest.approx(1.0)
