"""Closure regressions for remaining 1.5.9-rc P0 sub-items (relay thinking guard + #580 layout/ASS)."""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from backend.core import llm_providers as lp
from backend.services.studio import jobs, packaging_render as pr
from backend.services.studio.models import Packaging, Scene


@pytest.mark.parametrize('base,model,key', [
    ('https://api.apimart.ai/v1', 'qwen3.8-flash', 'enable_thinking'),
    ('https://api.88api.ai/v1', 'qwen3.8-max', 'enable_thinking'),
    ('https://api.siliconflow.cn/v1', 'Qwen/qwen3.5-plus', 'enable_thinking'),
    ('https://api.apimart.ai/v1', 'deepseek-v4-flash', 'thinking'),
    ('https://openrouter.ai/api/v1', 'deepseek/deepseek-chat', 'thinking'),
])
def test_known_relays_disable_thinking_for_qwen_and_deepseek_models(base, model, key):
    sent = lp.guarded_chat_kwargs(base, {'model': model, 'messages': []})
    extra = sent.get('extra_body') or {}
    if key == 'enable_thinking':
        assert extra.get('enable_thinking') is False
    else:
        assert extra.get('thinking') == {'type': 'disabled'}
        assert sent.get('max_tokens') == lp.DEEPSEEK_COMPLETION_TOKEN_CAP


def test_unknown_relay_and_reasoner_models_stay_untouched():
    req = {'model': 'qwen3.8-flash', 'messages': []}
    assert lp.guarded_chat_kwargs('https://proxy.example.com/v1', req) is req
    r1 = {'model': 'deepseek-r1', 'messages': []}
    assert lp.guarded_chat_kwargs('https://api.apimart.ai/v1', r1) is r1


def test_openai_provider_strips_thinking_param_and_retries_once_on_relay_400(monkeypatch):
    calls = []

    class BadRequestError(Exception):
        status_code = 400

    class Completions:
        def create(self, **kwargs):
            calls.append(dict(kwargs))
            if len(calls) == 1:
                raise BadRequestError('Unknown parameter: enable_thinking')
            usage = SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='ok'), finish_reason='stop')],
                usage=usage,
            )

    class Client:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    mod = types.ModuleType('openai')
    mod.OpenAI = Client
    monkeypatch.setitem(sys.modules, 'openai', mod)
    monkeypatch.delenv('OPENAI_BASE_URL', raising=False)

    resp = lp.OpenAIProvider(
        api_key='sk-test',
        model_name='qwen3.8-flash',
        base_url='https://api.apimart.ai/v1',
    ).call('挑片')
    assert resp.content == 'ok'
    assert len(calls) == 2
    assert (calls[0].get('extra_body') or {}).get('enable_thinking') is False
    assert 'enable_thinking' not in (calls[1].get('extra_body') or {})


def test_rank_fallback_faceless_shot_uses_blur_instead_of_blind_crop(monkeypatch, tmp_path):
    """When detector runs and finds no face (framing='full_frame'), rank_fallback keeps full width on blur backdrop."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    monkeypatch.setattr(jobs.store, 'read', lambda _pid, **_k: {'generation': {'portrait_style': 'auto'}})
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_a, **_k: False)
    drafts = [
        {'id': sid, 'title': sid, 'scenes': [{'id': sid, 'label': 'S', 'start': float(i * 3), 'end': float(i * 3 + 2)}], jobs.SCORE_KEY: score}
        for i, (sid, score) in enumerate([('a', 90), ('b', 80), ('c', 70), ('d', 60)])
    ]
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_a, **_k: drafts)
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_a, **_k: {})
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _pid, value, *_a, **_k: value)
    from backend.services.studio import framing
    monkeypatch.setattr(framing, 'is_installed', lambda: True)
    # Detector ran and returned no face track (scenes=None, framing='full_frame')
    monkeypatch.setattr(jobs, '_speaker_framing', lambda *_a, **_k: (None, 'full_frame'))

    derived, variants, _, _ = jobs._initial_derive(
        'p-580-faceless', {}, 'video.mp4',
        {'features': {'pkg_templates_v1': True}, 'html_template': 'editorial', 'output_captions': False, 'portrait_style': 'auto'},
        ['douyin'], {'outro_enabled': False}, [],
    )
    by_id = {d['id']: d for d in derived}
    rank_variant = next(v for v in variants if v.get('html_fallback') == 'rank')
    rank_draft = by_id[rank_variant['draft_id']]
    assert rank_variant['framing'] == 'full_frame'
    assert rank_draft['layout'] == 'blur'


def test_scene_ass_respects_crop_layout_safe_area_for_interview_zh():
    """Full-bleed 9:16 crop clips must not push interview_zh nameplate/tags into bottom dead-zone (y > 1600)."""
    pack = Packaging(
        template='interview_zh',
        audience_language='zh',
        captions_enabled=True,
        tags_enabled=True,
        cues=[{'start': 0.2, 'end': 1.8, 'text': '这是一条竖屏测试字幕'}],
        speakers=[{'at': 0.5, 'name': '张三', 'role': '主理人'}],
        tags=[{'at': 0.6, 'text': '核心观点'}],
    )
    scenes = [Scene(id='s1', start=0.0, end=3.0)]

    window_ass = pr.scene_ass(pack, scenes, 0, layout='window')
    crop_ass = pr.scene_ass(pack, scenes, 0, layout='crop')

    # Classic 4:3 window preserves historical coordinates (below WIN_Y + WIN_H = 1364)
    assert '1734' in window_ass or str(pr.WIN_Y + pr.WIN_H + 370) in window_ass
    # Full-bleed 9:16 crop moves nameplate and tags into safe portrait zone (<= 1560)
    assert str(pr.WIN_Y + pr.WIN_H + 370) not in crop_ass
    assert str(pr.WIN_Y + pr.WIN_H + 260) not in crop_ass
    assert '\\pos(540,1420)' in crop_ass
    assert '1180' in crop_ass
    assert '1280' in crop_ass


def test_verified_dashscope_allowlist_survives_text_only_modalities_and_multimodal_generation_endpoint():
    """Exact verified official DashScope IDs must not be knocked out of vision/cover slots by boilerplate /models metadata."""
    from backend.core import model_registry as registry
    from backend.core.model_recovery import pick_available_vision_model
    from backend.core.provider_model_fetch import _page_models
    from backend.services import ai_model_settings as ai

    conn = ai.Connection(id='bailian', name='Bailian', provider='dashscope', api_key='fixture')
    raw = [
        {'id': 'qwen4-max', 'input_modalities': ['text'], 'architecture': {'input_modalities': ['text']}},
        {'id': 'qwen-image-2.1-pro', 'supported_endpoint_types': ['multimodal-generation'], 'output_modalities': ['text']},
        {'id': 'qwen-image-edit', 'supported_endpoint_types': ['multimodal-generation']},
        {'id': 'unknown-text-model', 'input_modalities': ['text']},
        {'id': 'unknown-mm-model', 'supported_endpoint_types': ['multimodal-generation']},
    ]
    rows = {row['id']: row for row in registry._records(conn, raw, {})}

    # Exact verified official allowlist entries survive non-empty provider metadata
    assert rows['qwen4-max']['capability'] == 'multimodal'
    assert rows['qwen-image-2.1-pro']['image'] is True
    assert rows['qwen-image-2.1-pro']['kind'] == 'image'
    assert rows['qwen-image-2.1-pro']['analysis'] is False

    # Edit-only and unknown IDs remain strictly bounded
    assert rows['qwen-image-edit']['image'] is False
    assert rows['unknown-text-model']['capability'] == 'text'
    assert rows['unknown-mm-model']['image'] is False

    # Recovery path (_page_models -> pick_available_vision_model) also keeps qwen4-max eligible
    ids, caps = _page_models({'data': raw}, 'openai-completions', 'dashscope')
    assert pick_available_vision_model('dashscope', ids, capabilities=caps) == 'qwen4-max'

