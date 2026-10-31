"""S5: unavailable vision is optional only when the user chose AUTO."""
import subprocess

import httpx
import pytest

from backend.services import ai_model_settings as ai
from backend.services.studio import intelligence, jobs, planning, readiness, store
from backend.services.studio.models import ImportOptions
from backend.tests.test_studio import client, root


FALLBACK_CODE = 'vision_unavailable_subtitle_fallback'
FALLBACK_MESSAGE = '视觉服务暂不可用，已切换为字幕分析继续制作。'
SUBTITLES = b'1\n00:00:00,000 --> 00:00:10,000\nSynthetic subtitle\n'


@pytest.fixture(autouse=True)
def isolated_offline_settings(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}')
    original_send = httpx.Client.send

    def deny(*_args, **_kwargs):
        pytest.fail('Unexpected external request')

    def send(session, request, *args, **kwargs):
        if request.url.host == 'testserver':
            return original_send(session, request, *args, **kwargs)
        return deny()

    monkeypatch.setattr(httpx.Client, 'send', send)
    monkeypatch.setattr(httpx.AsyncClient, 'send', deny)
    monkeypatch.setattr('requests.Session.send', deny)
    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', deny)


@pytest.fixture
def source(root):
    raw = root / 'raw'
    raw.mkdir()
    video = raw / 'input.mp4'
    subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=160x90:r=1:d=21',
        '-y', str(video),
    ], check=True)
    (raw / 'input.srt').write_bytes(SUBTITLES)
    return video


def configure(monkeypatch, failure, mode='auto'):
    ai.save(ai.ModelSettings(
        connections=[
            ai.Connection(id='analysis', name='Analysis', provider='ollama', validation_status='ok'),
            ai.Connection(id='vision', name='Vision', provider='openai',
                          validation_status='failed' if failure == 'validation_failed' else 'ok'),
        ],
        analysis=ai.Assignment(connection_id='analysis', model='local-text', capability='text'),
        vision=ai.Assignment(connection_id='vision', model='gpt-4o', capability='multimodal'),
        analysis_mode=mode,
        allow_visual_screening=True,
    ))

    def unavailable(*_args, **_kwargs):
        raise intelligence.VisionRequestError('connection', '视觉连接不可用')

    monkeypatch.setattr(intelligence, 'vision_call', unavailable)
    monkeypatch.setattr(intelligence, 'sample', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(jobs, 'analyze', lambda *_a, **_k: pytest.fail('Unexpected visual production'))
    return ai.path().read_bytes()


@pytest.mark.parametrize('failure', ['validation_failed', 'unavailable'])
def test_auto_vision_failure_recommends_subtitles_with_fixed_reason(source, monkeypatch, failure):
    original = configure(monkeypatch, failure)
    plan = planning.recommend(source, ImportOptions())
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan.get('degrade_reason') == FALLBACK_CODE
    assert FALLBACK_MESSAGE in plan['reason']
    assert plan['local_evidence']['subtitle_status'] == 'available'
    assert ai.path().read_bytes() == original


@pytest.mark.parametrize('failure', ['validation_failed', 'unavailable'])
def test_auto_vision_failure_import_continues_to_subtitle_clips(client, source, monkeypatch, failure):
    original = configure(monkeypatch, failure)
    calls = []

    class Immediate:
        def submit(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)

    def run_content(project_id, video):
        # The selected analysis connection remains authoritative after degradation.
        settings = ai.load()
        assert settings.analysis.connection_id == 'analysis'
        assert settings.connections[0].provider == 'ollama'
        assert (video.parent / 'input.srt').read_bytes() == SUBTITLES
        calls.append(project_id)
        return [{'start_time': '00:00:00,000', 'end_time': '00:00:10,000',
                 'generated_title': 'Synthetic clip', 'final_score': 1}]

    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(jobs, 'run_content', run_content)
    response = client.post('/studio/import', files={
        'video': ('fixture.mp4', source.read_bytes(), 'video/mp4'),
        'subtitle': ('fixture.srt', SUBTITLES, 'application/x-subrip'),
    })
    assert response.status_code == 200
    pid = response.json()['project_id']
    state = client.get('/studio/' + pid).json()
    assert state['analysis']['status'] == 'awaiting_confirmation'
    plan = state['plan']
    assert plan['recommended_analysis'] == 'subtitle'
    assert plan.get('degrade_reason') == FALLBACK_CODE
    assert FALLBACK_MESSAGE in plan['reason']
    response = client.post('/studio/' + pid + '/start', json={
        'plan_id': plan['id'], 'goals': ['highlight'], 'analysis_mode': 'subtitle',
    })
    assert response.status_code == 200
    state = client.get('/studio/' + pid).json()
    assert state['analysis']['status'] == 'completed'
    assert state['analysis']['result_count'] == 1
    assert state['plan']['confirmed_analysis'] == 'subtitle'
    assert state['plan']['degrade_reason'] == FALLBACK_CODE
    assert state['drafts'][0]['origin'] == 'subtitle-highlight'
    assert calls == [pid]
    assert ai.path().read_bytes() == original


def test_auto_failed_vision_does_not_block_import_readiness(monkeypatch):
    configure(monkeypatch, 'validation_failed')
    monkeypatch.setattr(readiness, '_ffmpeg', lambda: {'ok': True})
    monkeypatch.setattr(readiness, '_transcription', lambda _settings: {'ok': True})
    assert readiness.report()['ready'] is True


@pytest.mark.parametrize('mode', ['auto', 'visual'])
def test_manual_vision_selection_still_blocks_failed_connection(client, monkeypatch, mode):
    original = configure(monkeypatch, 'validation_failed', mode)
    store.write('p1', {
        'analysis': {'status': 'awaiting_confirmation'},
        'plan': {'id': 'plan', 'recommended_analysis': 'subtitle', 'preferences': {}},
    })
    before = store.read('p1')
    monkeypatch.setattr(jobs.executor, 'submit', lambda *_a, **_k: pytest.fail('Blocked choice dispatched'))
    response = client.post('/studio/p1/start', json={
        'plan_id': 'plan', 'goals': ['highlight'], 'analysis_mode': 'visual',
    })
    assert response.status_code == 422
    assert '未通过校验' in response.json()['detail']
    assert store.read('p1') == before
    assert ai.path().read_bytes() == original
