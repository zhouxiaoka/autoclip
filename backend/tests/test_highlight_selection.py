"""Evidence categories and ordering must not collapse independent gameplay events."""
from pathlib import Path

import pytest
from pydantic import ValidationError
from backend.services.studio import intelligence as vision
from backend.services.studio.models import Preferences, Scene


def candidate(i, kind='gameplay', score=60, **extra):
    return dict(id=f'e{i}', start=i*10, end=i*10+5, label=f'事件{i}',
                event_type=kind, watch_score=score, selection_reason='可见挑战与反馈', **extra)


def test_filter_before_limit_and_rank_by_value_without_merging():
    raw=[candidate(0,'menu',99),candidate(1,'reward_screen',100),candidate(2,'loading',100)]
    raw += [candidate(i,score=50+i) for i in range(3,11)]
    scenes,audit=vision.select_highlights(raw,120)
    assert [e.id for e in scenes]==['e10','e9','e8','e7','e6','e5']
    assert all(e.end-e.start==5 for e in scenes)
    assert [e['disposition'] for e in audit[:3]]==['filtered']*3
    assert sum(e['disposition']=='limit' for e in audit)==2
    assert raw[0]['event_type']=='menu'  # Do not mutate provider evidence.
    assert all(set(e.model_dump())==set(Scene.model_fields) for e in scenes)


def test_rewards_during_gameplay_are_not_removed_by_keyword():
    raw=candidate(0);raw['label']='完成任务，获得奖励并使用道具'
    found,_=vision.select_highlights([raw],20)
    assert found[0].label==raw['label']


def test_legacy_endpoints_without_annotations_remain_usable_in_source_order():
    raw=[{'id':f'e{i}','start':i*4,'end':i*4+2} for i in range(4)]
    found,audit=vision.select_highlights(raw,20)
    assert [s.id for s in found]==[s['id'] for s in raw]
    assert all(a['event_type']=='unknown' and a['watch_score'] is None for a in audit)


@pytest.mark.parametrize('score',[-1,101,True,60.5,'80'])
def test_invalid_model_scores_are_rejected(score):
    with pytest.raises(ValidationError):
        vision.select_highlights([candidate(0,score=score)],20)


def test_no_gameplay_does_not_fabricate_a_highlight():
    with pytest.raises(ValueError,match='没有找到可用玩法高光'):
        vision.select_highlights([candidate(0,'menu'),candidate(1,'reward_screen')],20)


def test_duplicate_candidate_identity_is_rejected():
    with pytest.raises(ValueError,match='重复候选'):
        vision.select_highlights([candidate(0),candidate(0)],20)


def test_refinement_targets_ranked_gameplay_not_first_menu(monkeypatch):
    calls=[]
    monkeypatch.setattr(vision,'_probe',lambda _: {'duration':100})
    monkeypatch.setattr(vision,'sample',lambda v,t,p: calls.append(t) or [])
    responses=iter([{'events':[candidate(0,'menu',99),candidate(2,score=40),candidate(5,score=90)]},
                    {'events':[candidate(5,score=90)]}])
    monkeypatch.setattr(vision,'vision_call',lambda _: next(responses))
    found,coverage=vision.analyze(Path('unused'),Preferences(goal='highlight'))
    assert [s.id for s in found]==['e5','e2']
    assert min(calls[1])==48 and max(calls[1])==57
    assert coverage['refined_event_id']=='e5'
    assert coverage['selection'][0]['disposition']=='filtered'


def test_dense_non_play_correction_preserves_other_independent_events(monkeypatch):
    monkeypatch.setattr(vision,'_probe',lambda _: {'duration':100})
    monkeypatch.setattr(vision,'sample',lambda *a: [])
    responses=iter([{'events':[candidate(2,score=90),candidate(5,score=60)]},
                    {'events':[candidate(2,'reward_screen',10)]}])
    monkeypatch.setattr(vision,'vision_call',lambda _: next(responses))
    found,coverage=vision.analyze(Path('unused'),Preferences(goal='highlight'))
    assert [s.id for s in found]==['e5']
    assert coverage['selection'][0]['disposition']=='refine_filtered'
    assert coverage['refined_event_id'] is None


def test_dense_rejection_of_only_candidate_reports_no_highlight(monkeypatch):
    monkeypatch.setattr(vision,'_probe',lambda _: {'duration':100})
    monkeypatch.setattr(vision,'sample',lambda *a: [])
    responses=iter([{'events':[candidate(2)]},{'events':[candidate(2,'menu')]}])
    monkeypatch.setattr(vision,'vision_call',lambda _: next(responses))
    with pytest.raises(ValueError,match='没有找到可用玩法高光'):
        vision.analyze(Path('unused'),Preferences(goal='highlight'))


def test_overlong_candidate_does_not_discard_valid_independent_events():
    raw = [candidate(i, score=90-i) for i in range(8)]
    raw[0]['end'] = 46.3
    raw[1]['end'] = 50.6  # 40.6s, beyond the 40s target
    scenes, audit = vision.select_highlights(raw, 120, max_duration=40)
    assert [s.id for s in scenes] == ['e2', 'e3', 'e4', 'e5', 'e6', 'e7']
    assert [a['disposition'] for a in audit[:2]] == ['duration_filtered'] * 2
    assert all(s.end == raw[int(s.id[1:])]['end'] for s in scenes)
    assert raw[0]['end'] == 46.3  # Do not trim or split an event to satisfy duration.


def test_all_overlong_candidates_still_fail_without_inventing_clips():
    raw = candidate(0)
    raw['end'] = 46.3
    with pytest.raises(ValueError, match='超出期望时长'):
        vision.select_highlights([raw], 120, max_duration=40)
