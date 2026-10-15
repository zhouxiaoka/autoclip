from types import SimpleNamespace

from backend.core import model_registry
from backend.services.ai_model_settings import Connection


def _conn():
    return SimpleNamespace(provider='api88', base_url='https://api.88api.ai/v1')


def _row(rows, name):
    return next(r for r in rows if r['id'] == name)


def test_gateway_endpoint_types_split_video_tts_task_from_language():
    chat = ['openai', 'openai-response', 'anthropic', 'gemini']
    raw = [
        {'id': 'claude-opus-5', 'owned_by': 'advanced_custom', 'supported_endpoint_types': chat},
        {'id': 'gpt-image-2', 'owned_by': 'openai', 'supported_endpoint_types': ['image-generation', 'openai']},
        {'id': 'veo-3.1', 'owned_by': 'task plugin', 'supported_endpoint_types': ['openai-video']},
        {'id': 'seedance-2.0', 'owned_by': 'task plugin', 'supported_endpoint_types': ['openai']},
        {'id': 'gemini-3.1-tts', 'owned_by': 'vertex-ai', 'supported_endpoint_types': ['gemini', 'openai']},
        {'id': 'gemini-3-stt', 'owned_by': 'google gemini', 'supported_endpoint_types': ['gemini', 'openai']},
    ]
    rows = model_registry._records(_conn(), raw, {})
    assert _row(rows, 'claude-opus-5')['kind'] == 'language' and _row(rows, 'claude-opus-5')['analysis']
    assert _row(rows, 'gpt-image-2')['kind'] == 'image' and not _row(rows, 'gpt-image-2')['analysis']
    assert _row(rows, 'veo-3.1')['kind'] == 'video' and not _row(rows, 'veo-3.1')['analysis']
    assert not _row(rows, 'seedance-2.0')['analysis']
    for name in ('gemini-3.1-tts', 'gemini-3-stt'):
        assert not _row(rows, name)['analysis'] and _row(rows, name)['kind'] == 'audio'


def test_enabled_model_ids_default_none_and_dedupe():
    assert Connection(id='c0', name='x', provider='openai').enabled_model_ids is None
    c = Connection(id='c1', name='88API', provider='openai', enabled_model_ids=[' claude-opus-5 ', 'claude-opus-5', ''])
    assert c.enabled_model_ids == ['claude-opus-5']
    assert Connection(id='c2', name='x', provider='openai', enabled_model_ids=[]).enabled_model_ids == []
