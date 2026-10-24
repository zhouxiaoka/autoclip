"""The global burn-captions switch is snapshotted onto a generation and honored by both derive paths."""
import logging
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.studio import call
from backend.services import output_captions
from backend.services.studio import jobs, store
from backend.services.studio.models import Scene
from backend.tests import attempt_flow as flow


def test_settings_api_defaults_to_on_and_persists_off():
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as api:
        assert api.get('/settings/output-captions').json() == {'enabled': True}
        assert api.put('/settings/output-captions', json={'enabled': False}).json() == {'enabled': False}
        assert api.get('/settings/output-captions').json() == {'enabled': False}
        assert api.put('/settings/output-captions', json={'enabled': 'true'}).status_code == 422
    assert output_captions.load_settings().enabled is False


def test_unreadable_captions_file_stays_on_and_logs_once(caplog):
    path = output_captions.settings_path()
    output_captions._unreadable_logged = False
    path.write_text('{', encoding='utf-8')
    with caplog.at_level(logging.WARNING, logger='backend.services.output_captions'):
        assert output_captions.load_settings().enabled is True
        assert call(output_captions.load_settings).enabled is True
        path.write_text('{"enabled":"yes"}', encoding='utf-8')
        assert output_captions.load_settings().enabled is True
    assert [record.message for record in caplog.records if record.name == 'backend.services.output_captions'] == [
        'output-captions.json is unreadable; captions stay on',
    ]
    path.write_text('{"enabled":false}', encoding='utf-8')
    assert output_captions.load_settings().enabled is False


def _clip(template):
    return {
        'template': template, 'audience_language': 'zh' if template == 'interview_zh' else 'en',
        'title_lines': ['标题还在'],
        'cues': [{'start': 0.2, 'end': 2.0, 'text': '字幕正文', 'original': 'caption line'}],
    }


def test_landscape_title_is_unchanged_when_captions_are_off():
    scenes = [{'id': 's', 'label': 's', 'start': 0.0, 'end': 4.0}]
    base = {'id': 'd', 'title': 't', 'hook': '横版标题', 'scenes': scenes}
    off = jobs._apply_strategy(base, 'youtube_long', output_captions=False)
    on = jobs._apply_strategy(base, 'youtube_long', output_captions=True)
    assert off.hook == on.hook == '横版标题'
    assert off.title_style == on.title_style == 'editorial'
    assert off.title_template_version == on.title_template_version
    assert off.subtitles is False and on.subtitles is True
    assert off.packaging is None and on.packaging is None


def test_apply_strategy_off_clears_both_caption_flags_and_leaves_titles():
    scenes = [{'id': 's', 'label': 's', 'start': 0.0, 'end': 4.0}]
    base = {'id': 'd', 'title': 't', 'scenes': scenes}
    landscape = jobs._apply_strategy(base, 'youtube_long', output_captions=False)
    assert landscape.subtitles is False and landscape.packaging is None
    for strategy_id, template in (('douyin', 'interview_zh'), ('tiktok', 'podcast_en')):
        draft = jobs._apply_strategy({**base, 'packaging': _clip(template)}, strategy_id, output_captions=False)
        assert draft.subtitles is False
        assert draft.packaging.captions_enabled is False
        assert draft.packaging.title_lines == ['标题还在']
        assert draft.packaging.cues[0].text == '字幕正文'
    still_on = jobs._apply_strategy({**base, 'packaging': _clip('interview_zh')}, 'douyin')
    assert still_on.subtitles is True and still_on.packaging.captions_enabled is True


def test_templated_output_has_no_caption_lines_when_off():
    from backend.services.studio import packaging_render as pr
    scenes = [Scene(id='s', label='s', start=0, end=4)]
    for strategy_id, template in (('douyin', 'interview_zh'), ('tiktok', 'podcast_en')):
        off = jobs._apply_strategy(
            {'id': 'd', 'title': 't', 'scenes': [{'id': 's', 'label': 's', 'start': 0.0, 'end': 4.0}], 'packaging': _clip(template)},
            strategy_id, output_captions=False)
        ass = pr.scene_ass(off.packaging, scenes, 0)
        assert '字幕正文' not in ass and 'caption line' not in ass
        assert '标题还在' not in ass  # the cover owns the title; the clip does not burn it
        on = jobs._apply_strategy(
            {'id': 'd', 'title': 't', 'scenes': [{'id': 's', 'label': 's', 'start': 0.0, 'end': 4.0}], 'packaging': _clip(template)},
            strategy_id, output_captions=True)
        burned = pr.scene_ass(on.packaging, scenes, 0)
        assert '字幕正文' in burned
        assert '标题还在' not in burned


def _package(_project, value, strategy_id, *_rest):
    from backend.services.platform_strategy import platform_strategy
    template = platform_strategy(strategy_id).template
    if template not in ('interview_zh', 'podcast_en'):
        return value
    return {**value, 'packaging': _clip(template)}


def _arm_derive(monkeypatch, state):
    monkeypatch.setattr(store, 'read', lambda _pid, **kwargs: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    monkeypatch.setattr(jobs, 'source', lambda _pid: 'video.mp4')
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_: False)
    monkeypatch.setattr(jobs, '_apply_framing', lambda _p, value, *_: (value, 'full_frame'))
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *_: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_: {})
    monkeypatch.setattr(jobs, '_apply_packaging', _package)
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda *_: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_: None)


def _content():
    return {'id': 'd0', 'title': '一次完整的话', 'scenes': [{'id': 's0', 'label': 'x', 'start': 0.0, 'end': 210.0}]}


def test_first_generation_uses_the_snapshot_not_the_live_switch(monkeypatch):
    output_captions.save_settings(output_captions.CaptionSettings(enabled=True))
    state = {
        'generation': {'status': 'production', 'auto_start': True, 'output_captions': False,
                       'requested_platforms': ['youtube_long', 'douyin', 'tiktok'], 'branding': {'outro_enabled': False}},
        'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run'},
        'jobs': [], 'drafts': [], 'output_variants': [],
    }
    _arm_derive(monkeypatch, state)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: [_content()])
    monkeypatch.setattr(jobs, 'export', lambda *_a, **_k: {'job_id': 'j', 'status': 'queued'})
    jobs._auto_generate('p1', {})
    by_strategy = {variant['strategy_id']: next(d for d in state['drafts'] if d['id'] == variant['draft_id'])
                   for variant in state['output_variants']}
    assert set(by_strategy) == {'youtube_long', 'douyin', 'tiktok'}
    landscape = by_strategy['youtube_long']
    assert landscape['subtitles'] is False and landscape.get('packaging') is None
    for strategy_id, template in (('douyin', 'interview_zh'), ('tiktok', 'podcast_en')):
        draft = by_strategy[strategy_id]
        assert draft['subtitles'] is False
        assert draft['packaging']['captions_enabled'] is False
        assert draft['packaging']['template'] == template
        assert draft['packaging']['title_lines'] == ['标题还在']


def test_on_demand_variant_uses_the_snapshot_not_the_live_switch(monkeypatch):
    output_captions.save_settings(output_captions.CaptionSettings(enabled=False))
    raw = _content()
    state = {
        'generation': {'status': 'completed', 'output_captions': True},
        'drafts': [raw],
        'output_variants': [{'id': 'v1', 'draft_id': 'd0', 'strategy_id': 'douyin', 'status': 'on_demand'}],
    }
    _arm_derive(monkeypatch, state)
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *args, **kwargs: fn(*args))
    jobs.produce_variant('p1', 'v1')
    draft = state['drafts'][0]
    assert draft['subtitles'] is True
    assert draft['packaging']['captions_enabled'] is True
    assert draft['packaging']['title_lines'] == ['标题还在']

    output_captions.save_settings(output_captions.CaptionSettings(enabled=True))
    state['generation']['output_captions'] = False
    state['drafts'] = [_content()]
    state['output_variants'] = [{'id': 'v2', 'draft_id': 'd0', 'strategy_id': 'tiktok', 'status': 'on_demand'}]
    state['generation']['status'] = 'completed'
    jobs.produce_variant('p1', 'v2')
    drafted = state['drafts'][0]
    assert drafted['subtitles'] is False and drafted['packaging']['captions_enabled'] is False
    assert drafted['packaging']['title_lines'] == ['标题还在']


def test_import_snapshots_the_switch_and_a_later_change_does_not_rewrite_it(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    output_captions.save_settings(output_captions.CaptionSettings(enabled=False))
    pid = flow.new_project()
    flow.auto_import(pid)
    assert store.read(pid)['generation']['output_captions'] is False
    output_captions.save_settings(output_captions.CaptionSettings(enabled=True))
    assert store.read(pid)['generation']['output_captions'] is False


def test_captions_over_face_follows_the_packaging_switch():
    from backend.services.studio.qa import record
    off = record._context('p', {'subtitles': True, 'packaging': {'title_lines': ['标题'], 'captions_enabled': False}}, {}, 'douyin')
    assert off.captions is False and off.title is True and off.packaged is True
    on = record._context('p', {'subtitles': False, 'packaging': {'title_lines': ['标题'], 'captions_enabled': True}}, {}, 'douyin')
    assert on.captions is True and on.title is True
    missing = record._context('p', {'subtitles': False, 'packaging': {'title_lines': ['标题']}}, {}, 'douyin')
    assert missing.captions is True
    landscape = record._context('p', {'subtitles': True}, {}, 'youtube_long')
    assert landscape.captions is True and landscape.packaged is False
    assert record._context('p', {'subtitles': False}, {}, 'youtube_long').captions is False
