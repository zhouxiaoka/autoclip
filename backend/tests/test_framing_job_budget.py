"""Local face detection must not consume the production model-request budget."""
from types import SimpleNamespace

import pytest

from backend.core import job_budget
from backend.services import publish_export
from backend.services.studio import framing, jobs


@pytest.fixture
def clock(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(jobs, 'monotonic', lambda: now[0])
    monkeypatch.setattr(jobs, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def _draft():
    return {'id': 'draft', 'title': 'fixture', 'scenes': [
        {'id': 'scene', 'label': 'fixture', 'start': 0, 'end': 10},
    ]}


@pytest.mark.parametrize('scan_fails', [False, True])
def test_local_scan_preserves_budget_for_next_model_request(clock, monkeypatch, scan_fails):
    monkeypatch.setattr(framing, 'is_installed', lambda: True)
    monkeypatch.setattr(publish_export, '_probe', lambda _video: {'width': 1920, 'height': 1080})
    monkeypatch.setattr(jobs, '_project_strategy', lambda *_a: SimpleNamespace(aspect='portrait', template='interview_zh'))
    monkeypatch.setattr(jobs, '_framing_cues', lambda *_a: [])
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_a: None)

    def scan(*_a):
        clock[0] += 300  # CPU decoding/detection after 1,000 seconds of model work.
        if scan_fails:
            raise RuntimeError('synthetic detector failure')
        return []

    monkeypatch.setattr(framing, 'scan_speakers', scan)
    monkeypatch.setattr(framing, 'auto_frame', lambda *_a, **_k: {'scenes': [{'id': 'scene', 'faces': 0}]})
    with job_budget.bound_clip_job(1200):
        clock[0] += 1000
        value, mode = jobs._apply_framing('fixture', _draft(), 'douyin', 'fixture.mp4', False, {})
        assert mode == 'full_frame'
        assert value['layout'] == 'window'
        assert job_budget.clip_job_read_timeout(600) == pytest.approx(200)
        clock[0] += 201  # The next provider call still has a real cap.
        with pytest.raises(job_budget.JobDurationExceeded):
            job_budget.ensure_clip_job_budget()


def test_install_wait_preserves_budget_and_keeps_its_own_deadline(clock, monkeypatch):
    monkeypatch.setattr(framing, 'is_installed', lambda: False)
    monkeypatch.setattr(framing, 'get_status', lambda: {'status': 'installing'})
    with job_budget.bound_clip_job(60):
        assert jobs._speaker_framing(_draft(), 'fixture.mp4', wait_sec=120) == (None, 'full_frame_pending')
        assert clock[0] == 220
        assert job_budget.clip_job_read_timeout(600) == pytest.approx(60)


def test_already_expired_budget_does_not_start_local_work(clock, monkeypatch):
    def unexpected():
        pytest.fail('An expired job must stop before loading the optional detector')

    monkeypatch.setattr(framing, 'is_installed', unexpected)
    with job_budget.bound_clip_job(60):
        clock[0] += 61
        with pytest.raises(job_budget.JobDurationExceeded):
            jobs._speaker_framing(_draft(), 'fixture.mp4')
