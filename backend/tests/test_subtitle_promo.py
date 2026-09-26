import pytest
from backend.tests.test_studio import root, source, client
from backend.services.studio import subtitle_promo as promo, intelligence, jobs, store, analysis_preferences
from backend.services.studio.models import Preferences
from backend.tests.test_subtitle_highlights import clip

@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.setattr(promo,'_load_srt_entries',lambda _: [
        {'start_time':'00:00:00,000','end_time':'00:00:01,000','text':'Supported topic'},
        {'start_time':'00:00:10,000','end_time':'00:00:11,000','text':'Unrelated private text'}])
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('vision forbidden'))


def test_grounded_text_request_preserves_source_bounds(evidence,monkeypatch):
    calls=[]
    monkeypatch.setattr(intelligence,'text_json',lambda *a:calls.append(a) or {'drafts':[{'candidate':0,'title':'Topic','hook':'Supported opening'}]})
    result=promo.make_promos('p',[clip(0,1)],Preferences(goal='promo'),12)
    assert len(calls)==1 and 'Unrelated private text' not in str(calls)
    assert result[0]['scenes'][0]['start']==0 and result[0]['scenes'][0]['end']==1
    assert result[0]['origin']=='subtitle-promo' and result[0]['title_template_version']==6

@pytest.mark.parametrize('response',[
 {'drafts':[{'candidate':5,'title':'No','hook':'No'}]},
 {'drafts':[{'candidate':0,'title':' ','hook':' '}]},
 {'drafts':[]},
 {'drafts':[{'candidate':0,'title':'T','hook':'H','start':20}]},
])
def test_invalid_model_result_is_rejected_atomically(evidence,monkeypatch,response):
    monkeypatch.setattr(intelligence,'text_json',lambda *a:response)
    with pytest.raises(ValueError):promo.make_promos('p',[clip(0,1)],Preferences(),12)


def test_missing_subtitle_evidence_makes_no_model_call(monkeypatch):
    monkeypatch.setattr(promo,'_load_srt_entries',lambda _:[])
    monkeypatch.setattr(intelligence,'text_json',lambda *a:pytest.fail('no evidence'))
    with pytest.raises(ValueError,match='字幕证据'):promo.make_promos('p',[clip(0,1)],Preferences(),12)


def test_subtitle_promo_import_confirmation_and_edit(client,source,evidence,monkeypatch):
    monkeypatch.setattr(analysis_preferences,'load',lambda:analysis_preferences.AnalysisPreferences())
    analyses=[]; requests=[]
    monkeypatch.setattr(jobs,'run_content',lambda *a:analyses.append(a) or [clip(0,1)])
    monkeypatch.setattr(intelligence,'text_json',lambda *a:requests.append(a) or {'drafts':[{'candidate':0,'title':'Topic','hook':'Supported opening'}]})
    class Immediate:
        def submit(self,fn,*args):fn(*args)
    monkeypatch.setattr(jobs,'executor',Immediate())
    r=client.post('/studio/import',files={'video':('test.mp4',source.read_bytes(),'video/mp4')})
    assert r.status_code==200
    pid=r.json()['project_id'];plan=store.read(pid)['plan']
    assert not requests and not analyses
    r=client.post(f'/studio/{pid}/start',json={'plan_id':plan['id'],'goals':['highlight','promo'],'analysis_mode':'subtitle'})
    assert r.status_code==200,r.text
    state=store.read(pid)
    assert state['analysis']['status']=='completed' and len(state['drafts'])==2
    assert len(analyses)==len(requests)==1
    draft=next(d for d in state['drafts'] if d['origin']=='subtitle-promo')
    draft['hook']='Reviewed opening'
    assert client.put(f"/studio/{pid}/drafts/{draft['id']}",json=draft).status_code==200
