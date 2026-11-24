from pathlib import Path

from backend.services.studio import jobs


def shot(key, start, end, evidence='action_feedback'):
    return dict(id=key, title=key, origin='subtitle-highlight',
                scenes=[dict(id=key, label=key, start=start, end=end, evidence=evidence)])


def test_automatic_game_does_not_deliver_an_isolated_seven_second_shot(monkeypatch):
    short = shot('impact', 20, 27.5)
    monkeypatch.setattr(jobs, '_content_drafts', lambda *args: [short])
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *args: False)
    plan = dict(content_type='gameplay', preferences=dict(goal='highlight', duration=45))
    drafts, versions, events, _ = jobs._initial_derive('game', plan, Path('missing.mkv'), {}, ['original'], {}, [])
    assert not drafts and not versions
    assert events == short['scenes']


def test_montage_requires_distinct_nearby_shots_and_keeps_wins_separate(monkeypatch, tmp_path):
    from backend.services.studio import game_edits

    drafts = [shot('win', 0, 22, 'match_win · scoreboard'), shot('bridge', 50, 57.5),
              shot('skid', 70, 79), shot('different_chase', 400, 419)]
    edits = [{'shots': [{'id': 0}, {'id': 1}]}, {'shots': [{'id': 1}, {'id': 3}]},
             {'shots': [{'id': 2}, {'id': 2}]}, {'shots': [{'id': 2}, {'id': 1}]},
             {'shots': [{'id': 1}, {'id': 2}]}]
    monkeypatch.setattr(game_edits.intelligence, 'text_json', lambda *_: {'edits': edits})
    plan = dict(preferences=dict(duration=45), source_duration=440)
    cuts, originals = game_edits.assemble_game_edits(drafts, tmp_path / 'source.mkv', plan)
    assert [d['title'] for d in cuts] == ['win', 'bridge / skid', 'different_chase']
    assert [s['start'] for s in cuts[1]['scenes']] == [50, 70]
    assert originals == [d['scenes'][0] for d in drafts]


def test_context_uses_only_source_cues_allowed_in_import_window(monkeypatch, tmp_path):
    from backend.services.studio import game_edits

    (tmp_path / 'input.srt').write_text('1\n00:00:10,000 --> 00:00:14,000\nEarlier scene.\n\n'
                                       '2\n00:00:20,000 --> 00:00:26,000\nWatch the bridge.\n')
    plan = dict(preferences=dict(duration=30), source_duration=80, overrides={'source_window': {'start': 17, 'end': 45}})
    drafts = [shot('impact', 30, 37.5)]
    def choose(prompt, payload):
        import json
        cues = json.loads(payload)['events'][0]['cues']
        assert list(cues) == ['1']
        return {'edits': [{'shots': [{'id': 0, 'lead': 0}]}, {'shots': [{'id': 0, 'lead': 1}]}]}
    monkeypatch.setattr(game_edits.intelligence, 'text_json', choose)
    cuts, raw = game_edits.assemble_game_edits(drafts, tmp_path / 'source.mkv', plan)
    assert cuts[0]['scenes'][0]['start'] == 20
    assert raw[0]['start'] == 30


def test_adequate_duration_avoids_additional_review(tmp_path):
    from backend.services.studio import game_edits

    drafts = [shot('complete', 10, 25)]
    assert game_edits.assemble_game_edits(drafts, tmp_path / 'recording', {'preferences': {'duration': 45}})[0] == drafts
    explicit = [shot('short_request', 10, 20)]
    assert game_edits.assemble_game_edits(explicit, tmp_path / 'recording', {'preferences': {'duration': 10}})[0] == explicit


def test_visual_pair_needs_no_subtitle_provider(tmp_path, monkeypatch):
    from backend.services.studio import game_edits

    drafts = [dict(shot('turn', 5, 11), origin='visual-highlight'),
              dict(shot('finish', 14, 24), origin='visual-highlight')]
    monkeypatch.setattr(game_edits.intelligence, 'vision_call_at', lambda *_: {
        'edits': [{'shots': [{'id': 0}, {'id': 1}]}]})
    cuts, _ = game_edits.assemble_game_edits(drafts, tmp_path / 'source.mp4', {'preferences': {'duration': 30}})
    assert len(cuts) == 1 and cuts[0]['scenes'] == [d['scenes'][0] for d in drafts]


def test_candidate_only_run_persists_the_editable_source(tmp_path, monkeypatch):
    from backend.services.studio import store

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('game').mkdir(parents=True)
    short = shot('impact', 20, 27.5)
    plan = dict(content_type='gameplay', preferences=dict(goal='highlight', duration=45))
    store.change('game', lambda s: s.update(generation={'status': 'production', 'requested_platforms': ['original']},
                                            analysis={'phase': 'production', 'status': 'running'}, plan=plan))
    monkeypatch.setattr(jobs, 'source', lambda _: tmp_path / 'input.mp4')
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: [short])
    monkeypatch.setattr(jobs, 'mark_project', lambda *_: None)
    jobs._auto_generate('game', plan)
    workspace = store.read('game')
    assert workspace['events'] == short['scenes']
    assert workspace['generation']['status'] == 'failed'
    assert '已保存在下方片段列表中' in workspace['generation']['error']
    assert not workspace['output_variants'] and not workspace['jobs']


def test_unmerged_ten_second_highlight_still_publishes_standalone(tmp_path, monkeypatch):
    from backend.services.studio import game_edits

    clutch = dict(shot('clutch', 40, 50.5), origin='visual-highlight')
    monkeypatch.setattr(game_edits, '_propose_edits', lambda *a, **kw: [])
    cuts, originals = game_edits.assemble_game_edits([clutch], tmp_path / 'source.mp4', {'preferences': {'duration': 45}})
    assert len(cuts) == 1 and cuts[0]['id'] == 'clutch'
    assert originals == clutch['scenes']


def test_produce_selected_aligns_commentary_frame_review_and_game_edits(tmp_path, monkeypatch):
    from backend.services.studio import game_edits, game_highlights, store

    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('manual-game').mkdir(parents=True)
    raw = store.directory('manual-game') / 'raw'
    raw.mkdir(parents=True)
    video = raw / 'input.mp4'
    video.write_bytes(b'video')
    seen = {}

    def fake_subtitles(v, prefs, duration, instruction='', *, auto_frame_review=False, selection_log=None):
        seen['auto_frame_review'] = auto_frame_review
        return [shot('s1', 10, 21), shot('s2', 30, 41)]

    def fake_assemble(drafts, v, plan):
        seen['assembled'] = len(drafts)
        return [drafts[0]], [d['scenes'][0] for d in drafts]

    monkeypatch.setattr(game_highlights, 'subtitle_drafts', fake_subtitles)
    monkeypatch.setattr(game_edits, 'assemble_game_edits', fake_assemble)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **kw: None)
    plan = {
        'id': 'p1',
        'content_type': 'gameplay',
        'selected_goals': ['highlight'],
        'confirmed_analysis': 'subtitle',
        'confirmed_preferences': {'goal': 'highlight', 'duration': 45, 'language': 'source', 'aspect': 'original'},
        'analysis_preferences': {'analysis_mode': 'auto'},
        'local_evidence': {'commentary': True},
        'source_duration': 600,
    }
    store.write('manual-game', {'analysis': {'status': 'running', 'phase': 'production'}, 'drafts': [], 'events': [], 'jobs': []})
    jobs._produce_selected('manual-game', plan)
    assert seen == {'auto_frame_review': True, 'assembled': 2}
    ws = store.read('manual-game')
    assert len(ws['drafts']) == 1 and len(ws['events']) == 2
