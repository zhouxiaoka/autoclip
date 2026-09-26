"""Cost boundaries at the real import/confirmation endpoints, without paid calls."""
import pytest
from backend.tests.test_studio import root, source, client
from backend.services.studio import analysis_preferences as ap, intelligence, jobs, planning, store
from backend.services.studio.models import ImportOptions

class Immediate:
    def submit(self, fn, *args):
        fn(*args)

@pytest.mark.parametrize('mode', ['subtitle', 'auto', 'visual'])
@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('subtitles', [False, True])
def test_unapproved_screening_never_calls_vision(source, monkeypatch, mode, configured, subtitles):
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode=mode))
    monkeypatch.setattr(intelligence, 'ready', lambda: configured)
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: pytest.fail('unapproved vision call'))
    if subtitles:
        (source.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nHello\n')
    result = planning.recommend(source, ImportOptions())
    assert result['mode'] != 'ai'
    assert result['analysis_preferences']['allow_visual_screening'] is False


def test_subtitle_confirm_uses_only_old_pipeline_and_freezes_route(client, source, monkeypatch):
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences())
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, 'vision_call', lambda *a, **k: pytest.fail('vision forbidden'))
    monkeypatch.setattr(jobs, 'analyze', lambda *a, **k: pytest.fail('visual analysis forbidden'))
    monkeypatch.setattr(jobs, 'executor', Immediate())
    calls = []
    monkeypatch.setattr(jobs, 'run_content', lambda *a: calls.append(a))
    response = client.post('/studio/import', files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 200
    pid = response.json()['project_id']
    state = store.read(pid)
    assert not calls and state['analysis']['status'] == 'awaiting_confirmation'
    # Changing global settings cannot upgrade an already screened plan.
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode='visual'))
    rejected = client.post(f'/studio/{pid}/start', json={'plan_id':state['plan']['id'], 'goals':['content'], 'analysis_mode':'visual'})
    assert rejected.status_code == 422
    assert store.read(pid)['analysis']['status'] == 'awaiting_confirmation'
    accepted = client.post(f'/studio/{pid}/start', json={'plan_id':state['plan']['id'], 'goals':['content']})
    assert accepted.status_code == 200 and len(calls) == 1
    assert store.read(pid)['plan']['confirmed_analysis'] == 'subtitle'


def test_settings_api_strict_contract(client):
    assert client.get('/studio/analysis-preferences').json()['analysis_mode'] == 'subtitle'
    assert client.put('/studio/analysis-preferences', json={'analysis_mode':'subtitle','allow_visual_screening':True}).status_code == 422
    assert client.put('/studio/analysis-preferences', json={'analysis_mode':'invented'}).status_code == 422
    assert client.put('/studio/analysis-preferences', json={'analysis_mode':'auto','allow_visual_screening':True}).status_code == 200
    assert client.get('/studio/analysis-preferences').json()['allow_visual_screening'] is True
