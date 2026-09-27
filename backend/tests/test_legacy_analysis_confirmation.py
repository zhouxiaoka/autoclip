import pytest
from backend.tests.test_studio import root, source, client
from backend.services.studio import jobs, store, intelligence, analysis_preferences

@pytest.mark.parametrize('goal',['content','highlight','promo'])
def test_legacy_retry_waits_for_explicit_confirmation(client,monkeypatch,goal):
    from backend.core.database import SessionLocal
    from backend.models.project import Project
    with SessionLocal() as db:
        project=db.get(Project,'p1')
        project.processing_config={'creative':{'goal':goal}}
        db.commit()
    monkeypatch.setattr(analysis_preferences,'load',lambda:analysis_preferences.AnalysisPreferences())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('unexpected visual call'))
    monkeypatch.setattr(jobs,'analyze_project',lambda *a,**k:pytest.fail('legacy bypass'))
    monkeypatch.setattr(jobs,'run_content',lambda *a,**k:pytest.fail('production before confirmation'))
    class Immediate:
        def submit(self,fn,*args): fn(*args)
    monkeypatch.setattr(jobs,'executor',Immediate())
    old=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Keep existing edit'}).json()
    response=client.post('/studio/p1/analyze')
    assert response.status_code==200,response.text
    state=store.read('p1')
    assert state['analysis']['status']=='awaiting_confirmation'
    assert state['plan']['recommended_analysis']=='subtitle'
    assert state['plan']['preferences']['goal']==goal
    assert state['drafts']==[old]
    assert client.get('/studio/p1/source').status_code==200
