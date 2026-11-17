"""An editor translation retry is a bounded suggestion, never a new generation/export."""
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import studio
from backend.core import job_budget
from backend.services.studio import caption_translation, intelligence, packaging, store
from backend.services.studio.models import Draft, Packaging, Scene


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(studio, 'project_or_404', lambda *_: None)
    monkeypatch.setattr(studio.jobs, 'source', lambda *_: tmp_path / 'source.mp4')
    monkeypatch.setattr(intelligence, '_probe', lambda *_: {'duration': 20})
    monkeypatch.setattr(caption_translation, 'model_fingerprint', lambda: 'test-model')
    entries = [{'start_time': f'00:00:{i:02d},000', 'end_time': f'00:00:{i+1:02d},000', 'text': f'Idea number {i}.'} for i in range(10)]
    monkeypatch.setattr('backend.services.publish_export._load_srt_entries', lambda *_: entries)
    store.directory('translation').mkdir(parents=True)
    draft = Draft(id='d', title='Keep this title', scenes=[Scene(id='s', start=0, end=10)],
                  packaging=Packaging(template='interview_zh', source_language='en', audience_language='zh',
                                      title_lines=['保留用户标题'], palette='mint', style='boxed',
                                      fallback=True, translation_status='source_fallback'))
    draft = Draft.model_validate(store.save_draft('translation', draft, create=True))
    output = store.directory('translation') / 'old.mp4'
    output.write_bytes(b'previous immutable output')
    app = FastAPI(); app.include_router(studio.router)
    app.dependency_overrides[studio.get_db] = lambda: None
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, draft=draft, output=output)


def test_retry_returns_only_new_captions_and_keeps_project_and_old_output(recovery, monkeypatch):
    before = store.read('translation')
    digest = hashlib.sha256(recovery.output.read_bytes()).digest()
    calls = []
    def translate(_prompt, data, **kwargs):
        calls.append(data)
        assert data['task'] == 'translate_captions'  # no decoration, selection, post-copy or render
        return {'lines': [{'id': row['id'], 'text': f"这是第{row['id']}个想法。"} for row in data['lines']]}
    monkeypatch.setattr(caption_translation, '_request', translate)
    reply = recovery.client.post('/translation/retry-translation', json=recovery.draft.model_dump())
    assert reply.status_code == 200, reply.text
    result = Packaging.model_validate(reply.json())
    assert result.translation_status == 'complete' and result.translated_rows == 10
    assert result.title_lines == ['保留用户标题'] and result.palette == 'mint' and result.style == 'boxed'
    assert store.read('translation') == before
    assert hashlib.sha256(recovery.output.read_bytes()).digest() == digest
    assert len(calls) == 10
    # Repeated request uses the durable cache without model calls or another output.
    assert recovery.client.post('/translation/retry-translation', json=recovery.draft.model_dump()).json() == reply.json()
    assert len(calls) == 10


@pytest.mark.parametrize('change,status', [('revision', 409), ('missing', 404), ('range', 422)])
def test_invalid_editor_snapshot_is_rejected_before_model_calls(recovery, monkeypatch, change, status):
    monkeypatch.setattr(packaging, 'retry_translation', lambda *_: pytest.fail('must not call model'))
    payload = recovery.draft.model_dump()
    if change == 'revision': payload['revision'] += 1
    if change == 'missing': payload['id'] = 'missing'
    if change == 'range': payload['scenes'][0]['end'] = 30
    assert recovery.client.post('/translation/retry-translation', json=payload).status_code == status


def test_retry_deadline_returns_partial_cache_without_mutating_saved_draft(recovery, monkeypatch):
    now, count = [100.], [0]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    def translate(_prompt, data, **kwargs):
        count[0] += 1
        if count[0] == 2:
            now[0] += 121
            raise job_budget.JobDurationExceeded()
        return {'lines': [{'id': row['id'], 'text': f"这是第{row['id']}个想法。"} for row in data['lines']]}
    monkeypatch.setattr(caption_translation, '_request', translate)
    reply = recovery.client.post('/translation/retry-translation', json=recovery.draft.model_dump())
    assert reply.status_code == 200, reply.text
    assert reply.json()['translated_rows'] == 1 and reply.json()['translation_status'] == 'partial'
    assert store.read('translation')['drafts'][0]['packaging']['translation_status'] == 'source_fallback'


def test_retry_and_initial_translation_share_units_and_durable_cache(recovery, monkeypatch):
    from backend.services.platform_strategy import platform_strategy
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:03,000', 'text': 'We must not'},
               {'start_time': '00:00:03,800', 'end_time': '00:00:08,000', 'text': 'forget the original purpose.'}]
    monkeypatch.setattr('backend.services.publish_export._load_srt_entries', lambda *_: entries)
    calls = []
    def translate(_prompt, data):
        calls.append(data)
        assert data['lines'] == [{'id': 0, 'text': 'We must not forget the original purpose.'}]
        return {'lines': [{'id': 0, 'text': '我们不能忘记最初的目的。'}]}
    monkeypatch.setattr(caption_translation, '_request', translate)
    lines = packaging.draft_lines(entries, [scene.model_dump() for scene in recovery.draft.scenes])
    first = packaging.build_packaging(recovery.draft.model_dump(), lines, platform_strategy('douyin'),
        call=translate, translation_cache=store.directory('translation') / 'metadata/caption-translations', model_key='test-model')
    response = recovery.client.post('/translation/retry-translation', json=recovery.draft.model_dump())
    assert response.status_code == 200
    assert response.json()['translation_total_rows'] == 1
    assert response.json()['cues'] == first['cues']
    assert sum(call.get('task') == 'translate_captions' for call in calls) == 1
