"""Output-card AI covers use the platform's publish kit, with one task and honest outcomes."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.services import cover
from backend.services.studio import jobs, publish_kit, store
from backend.tests.test_studio import client, root, source  # noqa: F401 - shared API fixtures


@pytest.fixture
def cover_state(monkeypatch):
    state = {'drafts': [], 'jobs': [], 'output_variants': [
        {'id': 'v', 'strategy_id': 'xiaohongshu', 'render_job_id': 'render', 'cover': 'design'}]}
    monkeypatch.setattr(store, 'read', lambda _: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _, fn: fn(state))
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))
    return state


def test_double_click_and_automatic_request_share_one_paid_task(cover_state, monkeypatch):
    submitted = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *args: submitted.append(args))
    first = jobs.request_ai_cover('p', 'v')
    assert jobs.request_ai_cover('p', 'v') == first
    assert len(submitted) == 1 and first['status'] == 'queued'
    assert 'instance' not in first


@pytest.mark.parametrize('made', [True, False])
def test_the_task_uses_the_exact_platform_and_reports_failure_without_losing_the_cover(cover_state, monkeypatch, made):
    received = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda fn, *args: fn(*args))
    monkeypatch.setattr(publish_kit, 'ai_cover', lambda *args: received.append(args) or made)
    result = jobs.request_ai_cover('p', 'v')
    assert received == [('p', 'render', 'xiaohongshu')]
    assert result['status'] == ('completed' if made else 'failed')
    assert cover_state['output_variants'][0]['cover'] == ('ai' if made else 'design')


def test_dispatch_failure_preserves_the_video_and_allows_retry(cover_state, monkeypatch):
    def rejected(*_):
        raise RuntimeError('shutting down')
    monkeypatch.setattr(jobs.cover_executor, 'submit', rejected)
    result = jobs.request_ai_cover('p', 'v')
    assert result['status'] == 'failed' and cover_state['output_variants'][0]['cover'] == 'design'
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_: None)
    assert jobs.request_ai_cover('p', 'v')['job_id'] != result['job_id']


def test_no_model_task_without_permission_to_send_the_frame(cover_state, monkeypatch):
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=False))
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_: pytest.fail('must not submit'))
    assert jobs.request_ai_cover('p', 'v') is None
    assert 'cover_job' not in cover_state['output_variants'][0]


def test_interrupted_cover_is_failed_and_can_be_requested_again(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'directory', lambda _: tmp_path)
    state = {'jobs': [], 'output_variants': [{'id': 'v', 'status': 'completed', 'cover': 'design',
             'cover_job': {'job_id': 'old', 'status': 'running', 'instance': 'previous-server'}}]}
    store.write('p', state)
    result = jobs.ai_cover_status('p', 'v')
    assert result['status'] == 'failed' and '重启' in result['error']
    assert store.read('p')['output_variants'][0]['status'] == 'completed'


def test_failed_atomic_cover_write_leaves_the_previous_cover_usable(tmp_path, monkeypatch):
    target = tmp_path / 'cover.jpg'
    target.write_bytes(b'previous-complete-image')
    def disk_error(*_):
        raise OSError('disk full')
    monkeypatch.setattr(publish_kit.os, 'replace', disk_error)
    with pytest.raises(OSError):
        publish_kit._atomic_write(target, b'new-image')
    assert target.read_bytes() == b'previous-complete-image'
    assert list(tmp_path.iterdir()) == [target]


def _completed_output():
    return {'jobs': [{'job_id': 'render', 'status': 'completed'}], 'output_variants': [
        {'id': 'v', 'strategy_id': 'xiaohongshu', 'render_job_id': 'render', 'status': 'completed', 'cover': 'design'}]}


def test_card_api_returns_and_polls_the_same_platform_cover_task(client, monkeypatch):
    store.write('p1', _completed_output())
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))
    submitted = []
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *args: submitted.append(args))
    started = client.post('/studio/p1/output-variants/v/cover/ai')
    assert started.status_code == 200
    assert client.post('/studio/p1/output-variants/v/cover/ai').json() == started.json()
    assert client.get('/studio/p1/output-variants/v/cover/ai').json() == started.json()
    assert len(submitted) == 1


def test_card_api_rejects_ai_when_frames_may_not_be_sent(client, monkeypatch):
    store.write('p1', _completed_output())
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=False))
    monkeypatch.setattr(jobs.cover_executor, 'submit', lambda *_: pytest.fail('must not submit'))
    assert client.post('/studio/p1/output-variants/v/cover/ai').status_code == 409


def test_kit_http_download_cleans_up_the_archive(client, root, monkeypatch):
    from pathlib import Path
    store.write('p1', _completed_output())
    output = root / 'output' / 'studio'
    output.mkdir(parents=True)
    (output / 'render.mp4').write_bytes(b'complete-video')
    monkeypatch.setattr(publish_kit, 'cover_file', lambda *_: (None, None))
    created = []
    original = publish_kit.kit_file
    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        created.append(Path(result[0]))
        return result
    monkeypatch.setattr(publish_kit, 'kit_file', capture)
    response = client.get('/studio/p1/output-variants/v/kit')
    assert response.status_code == 200 and response.content.startswith(b'PK')
    assert len(created) == 1 and not created[0].exists()
