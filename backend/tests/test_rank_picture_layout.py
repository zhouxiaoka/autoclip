"""Rank skips the HTML overlay. It does not switch a selected full-bleed picture to the interview window.

Classic imports keep that window. Burned-in captions keep it too. A simulated fit point is not a
real multi-person or slide detection; it only checks the track is not stripped.
"""
import pytest

from backend.services.studio import jobs


def _drafts(scores):
    drafts = []
    for index, (source_id, score) in enumerate(scores):
        start = float(index * 3)
        drafts.append({
            'id': source_id,
            'title': source_id,
            'scenes': [{'id': source_id, 'label': 'S', 'start': start, 'end': start + 2.0}],
            jobs.SCORE_KEY: score,
        })
    return drafts


def _arm(monkeypatch, drafts, *, burned=False, installed=True, portrait_style='auto', speaker=None):
    monkeypatch.delenv('AUTOCLIP_FLAGS', raising=False)
    monkeypatch.setattr(jobs.store, 'read', lambda _pid, **_k: {'generation': {'portrait_style': portrait_style}})
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_a, **_k: burned)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_a, **_k: drafts)
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_a, **_k: {})
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _pid, value, *_a, **_k: value)
    from backend.services.studio import framing
    monkeypatch.setattr(framing, 'is_installed', lambda: installed)
    if speaker is not None:
        monkeypatch.setattr(jobs, '_speaker_framing', speaker)


def _derive(template, platforms):
    generation = {'features': {'pkg_templates_v1': True}, 'output_captions': False, 'portrait_style': 'auto'}
    if template:
        generation['html_template'] = template
    drafts, variants, _events, _coverage = jobs._initial_derive(
        'p-rank', {}, 'video.mp4', generation, list(platforms), {'outro_enabled': False}, [],
    )
    by_id = {draft['id']: draft for draft in drafts}
    rows = []
    for variant in variants:
        draft = by_id[variant['draft_id']]
        rows.append((draft['scenes'][0]['id'], draft, variant))
    return rows


def _speaker_crop(value, video, *, window=None, wait_sec=120, scans=None, cues=None):
    del video, window, wait_sec, scans, cues
    scenes = [{**scene, 'crop_x': 0.7, 'crop_track': [{'start': 0.0, 'crop_x': 0.7, 'mode': 'crop'}]} for scene in value['scenes']]
    return scenes, 'speaker'


def _speaker_with_fit(value, video, *, window=None, wait_sec=120, scans=None, cues=None):
    """Simulated detector return. Not a real face scan."""
    del video, window, wait_sec, scans, cues
    track = [
        {'start': 0.0, 'crop_x': 0.7, 'mode': 'crop'},
        {'start': 1.0, 'crop_x': 0.5, 'mode': 'fit'},
    ]
    scenes = [{**scene, 'crop_x': 0.7, 'crop_track': track} for scene in value['scenes']]
    return scenes, 'speaker'


def test_shuffled_scores_keep_rank_pictures_on_the_9x16_crop(monkeypatch):
    scores = [('low0', 1), ('low1', 2), ('low2', 3), ('mid', 40), ('s70', 70), ('s60', 60), ('s50', 50), ('top80', 80), ('top90', 90), ('top100', 100)]
    _arm(monkeypatch, _drafts(scores), speaker=_speaker_crop)
    rows = _derive('editorial', ['douyin', 'bilibili'])
    douyin = [(source, draft, variant) for source, draft, variant in rows if variant['strategy_id'] == 'douyin']
    assert [source for source, _draft, variant in douyin if variant.get('html_template') == 'editorial'] == ['top100', 'top90', 'top80']
    assert [source for source, _draft, _variant in douyin[:3]] == ['top100', 'top90', 'top80']
    for source, draft, variant in douyin:
        assert draft['layout'] == 'crop'
        assert draft['scenes'][0]['crop_track'][0]['mode'] == 'crop'
        if source in {'top100', 'top90', 'top80'}:
            assert variant['html_template'] == 'editorial'
            assert 'html_fallback' not in variant
        else:
            assert 'html_template' not in variant
            assert variant['html_fallback'] == 'rank'
            assert variant['requested_template'] == 'editorial'
            assert variant['framing'] == 'speaker'
    landscape = [row for row in rows if row[2]['strategy_id'] == 'bilibili']
    assert landscape and all(draft['layout'] == 'fit' and 'html_template' not in variant and 'html_fallback' not in variant for _source, draft, variant in landscape)


def test_missing_detector_rank_stays_full_bleed_and_classic_import_stays_window(monkeypatch):
    scores = [('a', 3), ('b', 2), ('c', 1), ('d', 0)]
    _arm(monkeypatch, _drafts(scores), installed=False)
    html_rows = [row for row in _derive('editorial', ['douyin', 'tiktok']) if row[2]['strategy_id'] == 'douyin']
    assert html_rows[3][2]['html_fallback'] == 'rank'
    assert html_rows[3][2]['framing'] == 'full_frame_pending'
    assert html_rows[3][1]['layout'] == 'crop'
    assert not html_rows[3][1]['scenes'][0].get('crop_track')
    tiktok_rank = [row for row in _derive('editorial', ['tiktok']) if row[2].get('html_fallback') == 'rank']
    assert tiktok_rank[0][1]['layout'] == 'blur'
    assert tiktok_rank[0][2]['framing'] == 'full_frame_pending'
    classic = [row for row in _derive(None, ['douyin'])]
    assert classic[0][1]['layout'] == 'window'
    assert 'html_fallback' not in classic[0][2]
    assert classic[0][2]['framing'] == 'full_frame_pending'


def test_burned_captions_keep_the_interview_window_for_rank_and_html(monkeypatch):
    scores = [('a', 3), ('b', 2), ('c', 1), ('d', 0)]
    _arm(monkeypatch, _drafts(scores), burned=True, speaker=lambda *_a, **_k: pytest.fail('captions must not detect'))
    rows = [row for row in _derive('editorial', ['douyin'])]
    assert {variant.get('framing') for _source, _draft, variant in rows} == {'full_frame_captions'}
    assert {draft['layout'] for _source, draft, _variant in rows} == {'window'}


def test_simulated_fit_track_survives_on_a_rank_crop(monkeypatch):
    scores = [('a', 3), ('b', 2), ('c', 1), ('d', 0)]
    _arm(monkeypatch, _drafts(scores), speaker=_speaker_with_fit)
    _source, draft, variant = [row for row in _derive('editorial', ['douyin']) if row[2].get('html_fallback') == 'rank'][0]
    assert draft['layout'] == 'crop'
    assert [point['mode'] for point in draft['scenes'][0]['crop_track']] == ['crop', 'fit']
    assert variant['framing'] == 'speaker'


def test_explicit_interview_without_an_html_template_stays_window(monkeypatch):
    _arm(monkeypatch, _drafts([('a', 1)]), portrait_style='interview', speaker=_speaker_crop)
    _source, draft, variant = _derive(None, ['douyin'])[0]
    assert draft['layout'] == 'window'
    assert 'html_fallback' not in variant
