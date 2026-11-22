"""Editor re-export keeps the HTML template recorded on the automatic variant.

Automatic production already passes html_template / safe area (or the rank fallback)
into export. The editor route used to drop those fields, so a magazine or street
clip was redrawn as the classic interview style with captions on or off.
"""
from types import SimpleNamespace

import pytest

from backend.services.studio import jobs, store
from backend.services.studio.models import Draft, Packaging, Scene
from backend.services.studio.template_choice import recorded_style
from backend.tests.test_studio import client, root, source  # noqa: F401 - shared API fixtures


def test_template_export_kwargs_matches_automatic_production():
    assert jobs.template_export_kwargs(None) == {}
    assert jobs.template_export_kwargs('editorial') == {}
    assert jobs.template_export_kwargs({}) == {}
    for area in ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts'):
        assert jobs.template_export_kwargs({'html_template': 'editorial', 'strategy_id': area}) == {
            'html_template': 'editorial', 'safe_area': area,
        }
        assert jobs.template_export_kwargs({'html_template': 'street', 'strategy_id': area}) == {
            'html_template': 'street', 'safe_area': area,
        }
    assert jobs.template_export_kwargs({'html_template': 'street', 'strategy_id': 'youtube_long'}) == {
        'html_template': 'street', 'safe_area': 'xiaohongshu',
    }
    assert jobs.template_export_kwargs({'html_template': 'editorial'}) == {
        'html_template': 'editorial', 'safe_area': 'xiaohongshu',
    }
    assert jobs.template_export_kwargs({'html_fallback': 'rank', 'requested_template': 'editorial'}) == {
        'html_fallback': 'rank', 'requested_template': 'editorial',
    }
    assert jobs.template_export_kwargs({'html_fallback': 'rank', 'requested_template': 'street'}) == {
        'html_fallback': 'rank', 'requested_template': 'street',
    }
    assert jobs.template_export_kwargs({'html_fallback': 'rank'}) == {'html_fallback': 'rank'}
    assert jobs.template_export_kwargs({'html_fallback': 'rank', 'requested_template': 'classic'}) == {'html_fallback': 'rank'}
    # A recorded HTML template wins over a fallback on the same variant, as production did.
    both = jobs.template_export_kwargs({
        'html_template': 'editorial', 'html_fallback': 'rank', 'strategy_id': 'douyin', 'requested_template': 'street',
    })
    assert both == {'html_template': 'editorial', 'safe_area': 'douyin'}


def _draft(captions):
    return Draft(
        id='d', title='edited', revision=2,
        scenes=[Scene(id='s', start=0, end=1)],
        subtitles=captions,
        packaging=Packaging(
            template='interview_zh', audience_language='zh',
            title_lines=['好的投资人'], captions_enabled=captions,
            cues=[{'start': 0.4, 'end': 2.0, 'text': '字幕正文'}],
        ),
    )


def _capture(monkeypatch):
    submitted = []
    seen = []
    real = jobs.template_export_kwargs

    def spy(variant):
        seen.append(real(variant))
        return seen[-1]

    monkeypatch.setattr(jobs, 'template_export_kwargs', spy)
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda *args, **kwargs: submitted.append((args, kwargs))))
    return submitted, seen


def _export(client, draft, variant):
    store.write('p1', {'drafts': [draft.model_dump()], 'jobs': [], 'output_variants': [variant]})
    result = client.post('/studio/p1/drafts/d/export', json={'revision': 2})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize('template,strategy,captions,safe_area', [
    ('editorial', 'douyin', True, 'douyin'),
    ('editorial', 'douyin', False, 'douyin'),
    ('street', 'tiktok', True, 'tiktok'),
    ('street', 'instagram_reels', False, 'instagram_reels'),
    ('editorial', 'youtube_long', False, 'xiaohongshu'),
    ('street', None, True, 'xiaohongshu'),
])
def test_editor_reexport_keeps_the_recorded_html_template(client, monkeypatch, template, strategy, captions, safe_area):
    submitted, seen = _capture(monkeypatch)
    variant = {
        'id': 'v', 'draft_id': 'd', 'branding': {'outro_enabled': True}, 'status': 'completed',
        'html_template': template,
    }
    if strategy:
        variant['strategy_id'] = strategy
    body = _export(client, _draft(captions), variant)
    assert seen == [{'html_template': template, 'safe_area': safe_area}]
    assert body['template'] == template and body['html_template'] == template
    assert body['html_safe_area'] == safe_area
    assert 'html_fallback' not in body
    kwargs = submitted[0][1]
    assert kwargs['html_template'] == template and kwargs['safe_area'] == safe_area
    assert 'html_fallback' not in kwargs
    stored = next(job for job in store.read('p1')['jobs'] if job['job_id'] == body['job_id'])
    assert stored['snapshot']['packaging']['captions_enabled'] is captions
    assert stored['snapshot']['subtitles'] is captions


@pytest.mark.parametrize('captions,requested', [(True, 'editorial'), (False, 'street')])
def test_editor_reexport_keeps_a_rank_fallback(client, monkeypatch, captions, requested):
    submitted, seen = _capture(monkeypatch)
    variant = {
        'id': 'v', 'draft_id': 'd', 'strategy_id': 'douyin', 'branding': {'outro_enabled': True},
        'status': 'completed', 'html_fallback': 'rank', 'requested_template': requested,
    }
    body = _export(client, _draft(captions), variant)
    assert seen == [{'html_fallback': 'rank', 'requested_template': requested}]
    # Rank fallback does not pass html_template, so the render stays classic.
    # The style label is whatever export already records for that requested name.
    assert body['template'] == recorded_style(None, requested)['template']
    assert body['requested_template'] == requested
    assert body['html_fallback'] == 'rank' and 'html_template' not in body
    kwargs = submitted[0][1]
    assert kwargs['html_fallback'] == 'rank' and kwargs['requested_template'] == requested
    assert 'html_template' not in kwargs
    stored = next(job for job in store.read('p1')['jobs'] if job['job_id'] == body['job_id'])
    assert stored['snapshot']['packaging']['captions_enabled'] is captions


@pytest.mark.parametrize('captions', [True, False])
def test_editor_reexport_without_a_recorded_template_stays_classic(client, monkeypatch, captions):
    submitted, seen = _capture(monkeypatch)
    variant = {
        'id': 'v', 'draft_id': 'd', 'strategy_id': 'douyin', 'branding': {'outro_enabled': True},
        'status': 'completed',
    }
    body = _export(client, _draft(captions), variant)
    assert seen == [{}]
    assert body['template'] == 'classic'
    assert 'html_template' not in body and 'html_fallback' not in body
    assert 'html_template' not in submitted[0][1] and 'html_fallback' not in submitted[0][1]
    stored = next(job for job in store.read('p1')['jobs'] if job['job_id'] == body['job_id'])
    assert stored['snapshot']['packaging']['captions_enabled'] is captions


def test_shared_draft_export_uses_the_named_variant(client, monkeypatch):
    submitted, seen = _capture(monkeypatch)
    editorial = {
        'id': 'v-edit', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'douyin',
        'html_template': 'editorial', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    street = {
        'id': 'v-street', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'tiktok',
        'html_template': 'street', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    store.write('p1', {'drafts': [_draft(True).model_dump()], 'jobs': [], 'output_variants': [editorial, street]})
    result = client.post('/studio/p1/drafts/d/export', json={'revision': 2, 'variant_id': 'v-street'})
    assert result.status_code == 200, result.text
    assert seen == [{'html_template': 'street', 'safe_area': 'tiktok'}]
    assert submitted[0][1]['html_template'] == 'street'


def test_shared_draft_without_an_id_does_not_take_the_first_template(client, monkeypatch):
    submitted, seen = _capture(monkeypatch)
    editorial = {
        'id': 'v-edit', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'douyin',
        'html_template': 'editorial', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    street = {
        'id': 'v-street', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'tiktok',
        'html_template': 'street', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    store.write('p1', {'drafts': [_draft(True).model_dump()], 'jobs': [], 'output_variants': [editorial, street]})
    result = client.post('/studio/p1/drafts/d/export', json={'revision': 2})
    assert result.status_code == 200, result.text
    # Comparing the two rows calls template_export_kwargs. Export itself must not.
    assert 'html_template' not in submitted[0][1]
    assert 'html_fallback' not in submitted[0][1]


def test_shared_draft_matches_the_draft_aspect_when_no_variant_is_named(client, monkeypatch):
    submitted, seen = _capture(monkeypatch)
    draft = _draft(True).model_copy(update={'aspect': 'portrait'})
    editorial = {
        'id': 'v-edit', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'douyin',
        'html_template': 'editorial', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    wide = {
        'id': 'v-wide', 'draft_id': 'd', 'draft_revision': 2, 'strategy_id': 'youtube_long',
        'html_template': 'street', 'branding': {'outro_enabled': True}, 'status': 'completed',
    }
    store.write('p1', {'drafts': [draft.model_dump()], 'jobs': [], 'output_variants': [wide, editorial]})
    result = client.post('/studio/p1/drafts/d/export', json={'revision': 2})
    assert result.status_code == 200, result.text
    assert seen == [{'html_template': 'editorial', 'safe_area': 'douyin'}]
    assert submitted[0][1]['html_template'] == 'editorial'


def test_automatic_dispatch_reuses_template_export_kwargs(root, monkeypatch):
    submitted = []
    seen = []
    real = jobs.template_export_kwargs

    def spy(variant):
        seen.append((variant['draft_id'], real(variant)))
        return seen[-1][1]

    monkeypatch.setattr(jobs, 'template_export_kwargs', spy)
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=lambda *args, **kwargs: submitted.append((args[2].id, kwargs))))
    branding = {'outro_enabled': False}
    specs = [
        ('d-edit', {'html_template': 'editorial'}, 'douyin'),
        ('d-street', {'html_template': 'street'}, 'youtube_shorts'),
        ('d-rank', {'html_fallback': 'rank', 'requested_template': 'editorial'}, 'tiktok'),
        ('d-classic', {}, 'xiaohongshu'),
    ]
    drafts = [
        Draft(id=draft_id, title=draft_id, scenes=[Scene(id='s', start=0, end=1)], subtitles=False).model_dump()
        for draft_id, _extra, _strategy in specs
    ]
    variants = [{
        'id': 'v-' + draft_id, 'draft_id': draft_id, 'draft_revision': 1,
        'strategy_id': strategy, 'strategy_version': 1, 'branding': branding, 'status': 'queued', **extra,
    } for draft_id, extra, strategy in specs]
    store.write('p1', {
        'schema_version': 2, 'drafts': drafts, 'events': [], 'jobs': [],
        'analysis': {'status': 'running'},
        'generation': {'auto_start': True, 'status': 'rendering'},
        'output_variants': variants,
    })
    jobs._dispatch_pending_variants('p1')
    assert seen == [
        ('d-edit', {'html_template': 'editorial', 'safe_area': 'douyin'}),
        ('d-street', {'html_template': 'street', 'safe_area': 'youtube_shorts'}),
        ('d-rank', {'html_fallback': 'rank', 'requested_template': 'editorial'}),
        ('d-classic', {}),
    ]
    by_draft = dict(submitted)
    assert by_draft['d-edit']['html_template'] == 'editorial' and by_draft['d-edit']['safe_area'] == 'douyin'
    assert by_draft['d-street']['html_template'] == 'street' and by_draft['d-street']['safe_area'] == 'youtube_shorts'
    assert by_draft['d-rank']['html_fallback'] == 'rank' and by_draft['d-rank']['requested_template'] == 'editorial'
    assert 'html_template' not in by_draft['d-rank'] and 'html_template' not in by_draft['d-classic']
    stored = {job['draft_id']: job for job in store.read('p1')['jobs']}
    assert stored['d-edit']['html_template'] == 'editorial' and stored['d-edit']['html_safe_area'] == 'douyin'
    assert stored['d-street']['html_safe_area'] == 'youtube_shorts'
    assert stored['d-rank']['html_fallback'] == 'rank' and 'html_template' not in stored['d-rank']
    assert stored['d-rank']['requested_template'] == 'editorial'
    assert stored['d-rank']['template'] == recorded_style(None, 'editorial')['template']
    assert 'html_template' not in stored['d-classic']


@pytest.mark.parametrize('choice', ['editorial', 'street', 'news', 'cinema', 'classic', None])
def test_confirmed_manual_choice_survives_save_and_export(client, monkeypatch, choice):
    submitted, _ = _capture(monkeypatch)
    raw = _draft(True).model_copy(update={'aspect': 'portrait', 'packaging': None,
                                          'origin': 'subtitle-highlight'}).model_dump()
    # A resumed manual production uses the already confirmed plan, with no platform variant.
    overrides = {'html_template': choice} if choice else {}
    state = {'drafts': [], 'jobs': [], 'plan': {'overrides': overrides}, 'output_variants': []}
    jobs._add_confirmed_drafts(state, [raw])
    store.write('p1', state)
    saved = client.put('/studio/p1/drafts/d', json={**state['drafts'][0], 'subtitle_style': 'accent'})
    assert saved.status_code == 200
    result = client.post('/studio/p1/drafts/d/export', json={'revision': saved.json()['revision']})
    assert result.status_code == 200
    assert result.json()['requested_template'] == (choice or 'classic')
    assert submitted[0][1].get('html_template') == (choice if choice != 'classic' else None)
    assert saved.json().get('html_template') == choice


def test_shared_snapshot_different_design_renders_separately(client, monkeypatch):
    submitted, _ = _capture(monkeypatch)
    draft = _draft(True)
    store.write('p1', {'jobs': [], 'drafts': [draft.model_dump()]})
    first = jobs.export('p1', draft, html_template='editorial', safe_area='douyin')
    second = jobs.export('p1', draft, html_template='street', safe_area='tiktok')
    repeat = jobs.export('p1', draft, html_template='street', safe_area='tiktok')
    assert first['job_id'] != second['job_id'] == repeat['job_id']
    assert len(submitted) == 2


def test_legacy_draft_inherits_only_its_own_confirmed_plan(root):
    drafts = [{'id': 'old'}, {'id': 'owned'}, {'id': 'explicit', 'html_template': 'classic'}]
    store.write('p1', {'drafts': drafts, 'plan': {'id': 'p', 'overrides': {'html_template': 'news'}},
                       'attempts': [{'kind': 'production', 'plan_id': 'old-plan', 'draft_ids': ['old']},
                                    {'kind': 'production', 'plan_id': 'p', 'draft_ids': ['owned', 'explicit']}]})
    assert [d.get('html_template') for d in store.read('p1')['drafts']] == [None, 'news', 'classic']


def test_old_manual_draft_can_select_design_after_recovery(client, monkeypatch):
    submitted, _ = _capture(monkeypatch)
    raw = _draft(True).model_copy(update={'aspect': 'portrait', 'packaging': None}).model_dump()
    raw.pop('html_template')
    store.write('p1', {'drafts': [raw], 'jobs': [], 'output_variants': []})
    response = client.put('/studio/p1/drafts/d', json={**raw, 'html_template': 'editorial'})
    assert response.status_code == 200
    edited = response.json()
    edited.pop('html_template')  # a pre-upgrade editor only sends fields it knows
    response = client.put('/studio/p1/drafts/d', json={**edited, 'subtitle_style': 'accent'})
    assert response.status_code == 200 and response.json()['html_template'] == 'editorial'
    job = client.post('/studio/p1/drafts/d/export', json={'revision': response.json()['revision']})
    assert job.status_code == 200 and submitted[0][1]['html_template'] == 'editorial'


def test_remake_freezes_composition_until_confirmation_and_export(client, monkeypatch, source):
    from backend.services.studio import planning
    submitted, _ = _capture(monkeypatch)
    old = _draft(True).model_copy(update={'aspect': 'portrait', 'origin': 'subtitle-highlight',
        'layout': 'blur', 'revision': 2}).model_dump()
    old['id'] = 'first'
    store.write('p1', {'drafts': [old], 'jobs': [], 'analysis': {'status': 'running'}, 'output_variants': []})
    monkeypatch.setattr(planning, 'recommend', lambda *args: {'preferences': {'duration': 15}, 'overrides': {'html_template': 'editorial'}})
    monkeypatch.setattr(jobs, 'mark_project', lambda *args, **kw: None)
    from backend.services.studio.models import ImportOptions
    jobs._inspect('p1', ImportOptions(duration=15, auto_start=False), None, None)
    pending = store.read('p1')
    assert pending['analysis']['status'] == 'awaiting_confirmation' and len(pending['drafts']) == 1
    new = {**old, 'id': 'next', 'layout': 'crop', 'revision': 1}
    jobs._add_confirmed_drafts(pending, [new, {**new, 'id': 'horizontal', 'aspect': 'landscape', 'layout': 'fit'}])
    assert [d['layout'] for d in pending['drafts']] == ['blur', 'blur', 'fit']
    store.write('p1', pending)
    response = client.post('/studio/p1/drafts/next/export', json={'revision': 1})
    assert response.status_code == 200
    exported = next(j for j in store.read('p1')['jobs'] if j['draft_id'] == 'next')
    assert exported['snapshot']['layout'] == 'blur' and submitted


@pytest.mark.parametrize(('scene', 'layout'), [
    ({'id': 's', 'start': 0, 'end': 1}, 'blur'),
    ({'id': 's', 'start': 0, 'end': 1, 'crop_x': .25}, 'crop'),
])
def test_manual_portrait_highlight_needs_a_subject_position_to_auto_crop(scene, layout):
    state = {'drafts': [], 'plan': {}}
    raw = _draft(True).model_dump()
    jobs._add_confirmed_drafts(state, [{**raw, 'origin': 'subtitle-highlight', 'aspect': 'portrait',
                                       'layout': 'crop', 'scenes': [scene]}])
    assert state['drafts'][0]['layout'] == layout


def test_existing_project_can_remake_after_old_version_already_lost_the_edit():
    base = {'origin': 'subtitle-highlight', 'aspect': 'portrait', 'scenes': [{'id': 's', 'start': 0, 'end': 1}]}
    first = {**base, 'id': 'v1', 'revision': 2, 'layout': 'blur'}
    second = {**base, 'id': 'v2', 'revision': 1, 'layout': 'crop'}
    state = {'drafts': [first, second], 'attempts': [
        {'kind': 'production', 'draft_ids': ['v1']}, {'kind': 'production', 'draft_ids': ['v2']} ]}
    assert jobs._remake_layouts(state) == {'subtitle-highlight:portrait': 'blur'}
    second.update(revision=2, layout='fit')
    assert jobs._remake_layouts(state) == {'subtitle-highlight:portrait': 'fit'}
