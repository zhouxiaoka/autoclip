import pytest
from backend.tests.test_studio import root, source
from backend.services.studio import jobs, store, intelligence
from backend.services.studio.models import Preferences
from backend.services.studio.subtitle_highlights import make_highlights


def clip(start, end, score=1):
    return {'start_time':f'00:00:{start:02d},000','end_time':f'00:00:{end:02d},000','generated_title':'Semantic event','final_score':score}


def test_ranked_whole_ranges_deduplicate_and_cap():
    rows = [clip(i*5,i*5+4,i) for i in range(9)] + [clip(40,44,99),clip(50,59,1),clip(0,99)]
    drafts=make_highlights(rows, Preferences(goal='highlight'), 55)
    assert len(drafts)==6
    assert drafts[0]['scenes'][0]['start']==40
    assert all(d['scenes'][0]['end']-d['scenes'][0]['start']==4 for d in drafts)
    assert all(d['origin']=='subtitle-highlight' and d['subtitles'] for d in drafts)


def test_invalid_results_do_not_fabricate_full_length_highlight():
    with pytest.raises(ValueError,match='没有可用'):
        make_highlights([{},clip(2,1),clip(0,40),clip(1,2,float('nan'))],Preferences(),30)


@pytest.mark.parametrize('fails',[False,True])
def test_combined_subtitle_outputs_share_one_attempt(root,source,monkeypatch,fails):
    calls=[]
    def run(*args):
        calls.append(args)
        if fails: raise ValueError('test failure')
        return [clip(0,1)]
    monkeypatch.setattr(jobs,'run_content',run)
    monkeypatch.setattr(jobs,'source',lambda _:source)
    monkeypatch.setattr(jobs,'mark_project',lambda *a,**k:None)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('vision call'))
    monkeypatch.setattr(jobs,'analyze',lambda *a,**k:pytest.fail('visual analysis'))
    store.write('p1',{'drafts':[],'events':[],'jobs':[],'analysis':{'status':'running'}})
    jobs._produce_selected('p1',{'selected_goals':['content','highlight'],'confirmed_analysis':'subtitle','confirmed_preferences':Preferences().model_dump()})
    result=store.read('p1')
    assert len(calls)==1
    assert result['analysis']['status']==('failed' if fails else 'completed')
    assert len(result['drafts'])==(0 if fails else 1)

from backend.tests.test_studio import client

def test_subtitle_highlight_confirmation_reaches_shared_editor(client,source,monkeypatch):
    from backend.services.studio import analysis_preferences as ap
    monkeypatch.setattr(ap,'load',lambda:ap.AnalysisPreferences())
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('vision forbidden'))
    monkeypatch.setattr(jobs,'run_content',lambda *a:[clip(0,1)])
    class Immediate:
        def submit(self,fn,*args): fn(*args)
    monkeypatch.setattr(jobs,'executor',Immediate())
    imported=client.post('/studio/import',files={'video':('test.mp4',source.read_bytes(),'video/mp4')})
    assert imported.status_code==200
    pid=imported.json()['project_id'];plan=store.read(pid)['plan']
    assert client.post(f'/studio/{pid}/start',json={'plan_id':plan['id'],'analysis_mode':'subtitle','goals':['highlight']}).status_code==200
    state=client.get(f'/studio/{pid}').json()
    assert state['analysis']['status']=='completed'
    draft=state['drafts'][0]
    assert draft['origin']=='subtitle-highlight'
    draft['title']='Edited subtitle highlight'
    response=client.put(f"/studio/{pid}/drafts/{draft['id']}",json=draft)
    assert response.status_code==200,response.text
    assert response.json()['revision']==2
