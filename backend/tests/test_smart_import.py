"""Automatic entry routing, corrections and old pipeline adapter; no paid calls."""
import sys
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from backend.tests.test_studio import root, source, client
from backend.services.studio import intelligence, jobs, store, planning
from backend.services.studio.models import ImportOptions

@pytest.fixture(autouse=True)
def explicit_visual_preferences(monkeypatch):
    # These existing tests exercise the opted-in visual workflow.
    from backend.services.studio import analysis_preferences as ap
    monkeypatch.setattr(ap, 'load', lambda: ap.AnalysisPreferences(analysis_mode='visual', allow_visual_screening=True))

class Immediate:
    def submit(self, fn, *args): fn(*args)

def recommendation(goal='highlight'):
    return {'content_type':'gameplay' if goal!='content' else 'talk', 'goal':goal, 'reason':'测试证据', 'confidence':.8, 'aspect':'original', 'duration':30}

def test_append_platforms_reuses_saved_drafts_without_reanalysis(client, root, monkeypatch):
    from backend.services.studio.models import Draft, Scene
    original = Draft(id='base', title='Saved output', scenes=[Scene(id='scene', label='Scene', start=0, end=1)], subtitles=False).model_dump()
    store.write('p1', {
        'schema_version': 2, 'drafts': [original], 'events': [], 'jobs': [],
        'analysis': {'status': 'completed'},
        'generation': {'auto_start': True, 'status': 'completed', 'branding': {'outro_enabled': True, 'outro_version': 'v1'}},
        'output_variants': [{'id': 'done', 'draft_id': 'base', 'draft_revision': 1, 'strategy_id': 'douyin', 'strategy_version': 1, 'branding': {'outro_enabled': True, 'outro_version': 'v1'}, 'status': 'completed', 'render_job_id': 'old'}],
    })
    calls = []
    monkeypatch.setattr(jobs, 'run_content', lambda *_: pytest.fail('must not rerun content analysis'))
    monkeypatch.setattr(jobs, 'analyze', lambda *_: pytest.fail('must not rerun visual analysis'))
    monkeypatch.setattr(jobs, 'export', lambda _pid, draft, **kwargs: calls.append((draft, kwargs)) or {'job_id': 'new-job', 'status': 'queued'})

    response = client.post('/studio/p1/platforms', json={'platforms': ['tiktok']})
    assert response.status_code == 200, response.text
    state = client.get('/studio/p1').json()
    assert len(state['output_variants']) == 2
    added = next(item for item in state['output_variants'] if item['strategy_id'] == 'tiktok')
    assert added['draft_id'] != 'base' and added['render_job_id'] == 'new-job'
    assert state['output_variants'][0]['status'] == 'completed'
    assert len(calls) == 1 and calls[0][1] == {'brand_outro': True}


def test_retry_variant_only_requeues_failed_output(client, root, monkeypatch):
    draft = jobs.Draft(id='failed-draft', title='Retry', scenes=[jobs.Scene(id='scene', label='Scene', start=0, end=1)], subtitles=False).model_dump()
    store.write('p1', {
        'schema_version': 2, 'drafts': [draft], 'events': [], 'jobs': [], 'analysis': {'status': 'failed'},
        'generation': {'auto_start': True, 'status': 'partial'},
        'output_variants': [
            {'id': 'completed', 'draft_id': 'failed-draft', 'draft_revision': 1, 'strategy_id': 'douyin', 'strategy_version': 1, 'branding': {'outro_enabled': True, 'outro_version': 'v1'}, 'status': 'completed', 'render_job_id': 'old'},
            {'id': 'failed', 'draft_id': 'failed-draft', 'draft_revision': 1, 'strategy_id': 'tiktok', 'strategy_version': 1, 'branding': {'outro_enabled': False, 'outro_version': 'v1'}, 'status': 'failed', 'render_job_id': 'bad', 'error': 'encoder stopped'},
        ],
    })
    calls = []
    monkeypatch.setattr(jobs, 'export', lambda _pid, value, **kwargs: calls.append((value, kwargs)) or {'job_id': 'retry-job', 'status': 'queued'})

    response = client.post('/studio/p1/output-variants/failed/retry')
    assert response.status_code == 200, response.text
    state = client.get('/studio/p1').json()
    retried = next(item for item in state['output_variants'] if item['id'] == 'failed')
    assert retried['status'] == 'queued' and retried['render_job_id'] == 'retry-job' and 'error' not in retried
    assert state['analysis']['status'] == 'running'  # same process: must not be mistaken for a restart
    assert next(item for item in state['output_variants'] if item['id'] == 'completed')['status'] == 'completed'
    assert calls[0][1] == {'brand_outro': False}


def test_auto_variant_passes_branding_to_render_job(client, source, monkeypatch):
    submitted = []
    class CaptureExecutor:
        def submit(self, fn, *args, **kwargs):
            submitted.append((fn, args, kwargs))
            return None

    monkeypatch.setattr(jobs, 'executor', CaptureExecutor())
    draft = jobs.Draft(id='brand-draft', title='Brand', scenes=[jobs.Scene(id='scene', label='Scene', start=0, end=1)], subtitles=False)
    job = jobs.export('p1', draft, brand_outro=True)
    assert job['brand_outro'] is True
    assert submitted[0][2] == {'brand_outro': True}
    assert submitted[0][1][-1] == job['job_id']


def test_variant_terminal_states_preserve_partial_success(root):
    store.write('p1', {
        'schema_version': 2, 'drafts': [], 'events': [], 'jobs': [],
        'analysis': {'status': 'running'},
        'generation': {'status': 'rendering'},
        'output_variants': [
            {'id': 'one', 'draft_id': 'draft-one', 'draft_revision': 1, 'strategy_id': 'tiktok', 'strategy_version': 1, 'branding': {'outro_enabled': True, 'outro_version': 'v1'}, 'status': 'running', 'render_job_id': 'job-one'},
            {'id': 'two', 'draft_id': 'draft-two', 'draft_revision': 1, 'strategy_id': 'youtube_shorts', 'strategy_version': 1, 'branding': {'outro_enabled': True, 'outro_version': 'v1'}, 'status': 'running', 'render_job_id': 'job-two'},
        ],
    })
    jobs._sync_variant_status('p1', 'job-one', 'completed')
    state = store.read('p1')
    assert state['generation']['status'] == 'rendering'
    jobs._sync_variant_status('p1', 'job-two', 'failed', 'encoder stopped')
    state = store.read('p1')
    assert state['generation']['status'] == 'partial'
    assert state['generation']['completed_variant_count'] == 1
    assert state['analysis']['outcome'] == 'partial'
    assert state['output_variants'][1]['error'] == 'encoder stopped'


def test_auto_start_skips_ineligible_long_output_without_faking_duration(client, source, monkeypatch):
    class ImmediateAuto:
        def submit(self, fn, *args):
            return fn(*args)

    monkeypatch.setattr(jobs, 'executor', ImmediateAuto())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    monkeypatch.setattr(jobs, 'run_content', lambda *args: [
        {'generated_title': '短观点', 'start_time': '00:00:00,000', 'end_time': '00:00:01,000'},
    ])
    monkeypatch.setattr(jobs, 'export', lambda *_: (_ for _ in ()).throw(AssertionError('long form must not render')))

    response = client.post(
        '/studio/import',
        data={'auto_start': 'true', 'platforms': 'youtube_long'},
        files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')},
    )
    state = client.get('/studio/' + response.json()['project_id']).json()
    assert state['generation']['status'] == 'failed'
    assert state['output_variants'] == []
    assert state['generation']['skipped'] == [{'strategy_id': 'youtube_long', 'reason': '素材没有足够完整的长内容'}]


def test_auto_start_creates_platform_variants_without_confirmation(client, source, monkeypatch):
    class ImmediateAuto:
        def submit(self, fn, *args):
            return fn(*args)

    monkeypatch.setattr(jobs, 'executor', ImmediateAuto())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    monkeypatch.setattr(jobs, 'run_content', lambda *args: [
        {'generated_title': '完整观点', 'start_time': '00:00:00,000', 'end_time': '00:00:01,000'},
    ])
    exports = []
    def fake_export(project_id, draft, **kwargs):
        assert kwargs == {'brand_outro': True}
        exports.append(draft)
        return {'job_id': f'job-{draft.id}', 'status': 'queued'}
    monkeypatch.setattr(jobs, 'export', fake_export)

    response = client.post(
        '/studio/import',
        data={'auto_start': 'true', 'platforms': 'tiktok', 'name': 'Automatic output'},
        files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')},
    )
    assert response.status_code == 200, response.text
    state = client.get('/studio/' + response.json()['project_id']).json()
    assert state['analysis']['phase'] == 'rendering', state['generation'].get('error')
    assert state['generation']['status'] == 'rendering'
    assert state['generation']['requested_platforms'] == ['tiktok']
    assert len(state['output_variants']) == len(exports) == 1
    variant = state['output_variants'][0]
    assert variant['strategy_id'] == 'tiktok'
    assert variant['draft_id'] == exports[0].id
    assert variant['render_job_id'] == f'job-{exports[0].id}'
    assert state['plan']['id']
    assert state['analysis']['status'] != 'awaiting_confirmation'


def test_async_analysis_failure_persists_error_after_exception_scope(client, monkeypatch):
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(jobs, 'analyze', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('analysis failed')))

    jobs.analyze_project('p1', ImportOptions(goal='highlight'))
    state = client.get('/studio/p1').json()
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['error'] == 'analysis failed'


def test_import_persists_platform_and_branding_contract_without_auto_start(client, source, monkeypatch):
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)

    response = client.post(
        '/studio/import',
        data={'platforms': 'tiktok', 'brand_outro_enabled': 'false', 'name': 'Platform contract'},
        files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')},
    )
    assert response.status_code == 200, response.text
    state = client.get('/studio/' + response.json()['project_id']).json()
    assert state['schema_version'] == 2
    assert state['generation'] == {
        'requested_platforms': ['tiktok'],
        'branding': {'outro_enabled': False, 'outro_version': 'v1'},
        'auto_start': False,
        'portrait_style': 'auto',
        'status': 'awaiting_confirmation',
        'created_at': state['generation']['created_at'],
    }
    assert state['output_variants'] == []
    assert ImportOptions(platforms=['tiktok', 'reels', 'tiktok']).platforms == ['tiktok', 'instagram_reels']


def test_ai_plan_samples_real_source_and_explicit_preferences_win(source,monkeypatch):
    inputs=[]
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda content, **kw: inputs.append(content) or recommendation())
    plan=planning.recommend(source,ImportOptions(language='ja',aspect='portrait',duration=60,instruction='保留完整挑战'))
    assert plan['source_duration']>0
    assert plan['mode']=='ai' and plan['preferences']=={'goal':'highlight','language':'ja','aspect':'portrait','duration':60}
    assert sum(x['type']=='image_url' for x in inputs[0])==4
    assert all(x['image_url']['url'].startswith('data:image/jpeg;base64,') for x in inputs[0] if x['type']=='image_url')
    assert '保留完整挑战' in inputs[0][0]['text']

@pytest.mark.parametrize('goal',['content','highlight','promo'])
def test_manual_correction_does_not_call_classifier(source,monkeypatch,goal):
    monkeypatch.setattr(intelligence,'vision_call',lambda *a, **kw: pytest.fail('manual choice must win'))
    plan=planning.recommend(source,ImportOptions(goal=goal))
    assert plan['mode']=='manual' and plan['preferences']['goal']==goal

@pytest.mark.parametrize('hours, route', [(1, 'visual'), (4, 'subtitle')])
def test_long_sources_are_accepted_and_skip_costly_visual_analysis(source, monkeypatch, hours, route):
    real_probe = intelligence._probe
    monkeypatch.setattr(intelligence, '_probe', lambda video: {**real_probe(video), 'duration': hours * 3600.0})
    plan = planning.recommend(source, ImportOptions(goal='highlight'))
    assert plan['source_duration'] == hours * 3600.0
    assert plan['recommended_analysis'] == route

def test_missing_vision_is_explicit_fallback_not_fake_ai(source,monkeypatch):
    monkeypatch.setattr(intelligence,'ready',lambda:False)
    plan=planning.recommend(source,ImportOptions())
    assert plan['mode']=='fallback' and plan['confidence']==0
    assert plan['preferences']['goal']=='content' and '未配置' in plan['reason']
    assert plan['suggested_goals']==[]

def test_invalid_model_choice_does_not_silently_route(source,monkeypatch):
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a, **kw: {**recommendation(),'goal':'invented'})
    plan = planning.recommend(source,ImportOptions())
    assert plan['mode']=='fallback' and plan['suggested_goals']==[]

@pytest.mark.parametrize('goal',['content','highlight','promo'])
def test_one_import_endpoint_routes_and_keeps_srt(client,source,monkeypatch,goal):
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    def provider(content, **kwargs):
        if 'content_type' in content[0]['text']: return recommendation(goal)
        if 'hooks' in content[0]['text']: return {'hooks':[{'title':'Variant','hook':'Try this!'}]}
        return {'events':[{'id':'e1','label':'Visible event','start':0,'end':1,'evidence':'Fixture'}]}
    monkeypatch.setattr(intelligence,'vision_call',provider)
    content_calls=[]
    monkeypatch.setattr(jobs,'run_content',lambda pid,video:content_calls.append((pid,video)) or [{'id':'clip'}])
    response=client.post('/studio/import',data={'name':'Unified entry'},files={'video':('source.mp4',source.read_bytes(),'video/mp4'),'subtitle':('captions.srt',b'1\n00:00:00,000 --> 00:00:01,000\nHello\n','text/plain')})
    assert response.status_code==200,response.text
    pid=response.json()['project_id'];state=client.get('/studio/'+pid).json()
    assert state['analysis']['status']=='awaiting_confirmation',state
    from backend.core.database import SessionLocal
    from backend.models import Project
    with SessionLocal() as db: assert db.get(Project,pid).processing_config['import_staging'] is True
    assert not content_calls and state['drafts']==[]
    assert state['plan']['preferences']['goal']==goal
    confirmed=client.post('/studio/'+pid+'/start',json={'plan_id':state['plan']['id'],'goals':[goal]})
    assert confirmed.status_code==200,confirmed.text
    state=client.get('/studio/'+pid).json()
    assert state['analysis']['status']=='completed',state
    assert (store.directory(pid)/'raw/input.srt').exists()
    assert bool(content_calls)==(goal=='content')
    assert len(state['drafts'])==(0 if goal=='content' else 1)
    if goal!='content': assert state['drafts'][0]['subtitles'] is True
    from backend.core.database import SessionLocal
    from backend.models import Project
    with SessionLocal() as db:
        p=db.get(Project,pid)
        assert p.processing_config['smart_import']['goal']=='auto'
        assert p.processing_config['creative']['goal']==goal
        assert p.processing_config['import_staging'] is False


def test_correction_keeps_existing_drafts_and_exports(client,monkeypatch):
    original=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Keep me'}).json()
    store.change('p1',lambda s:s['jobs'].append({'job_id':'old','status':'completed','draft_id':original['id']}))
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(jobs,'run_content',lambda *a, **kw:None)
    result=client.put('/studio/p1/plan',json={'goal':'content','language':'en','aspect':'portrait'})
    assert result.status_code==200,result.text
    state=client.get('/studio/p1').json()
    assert state['drafts']==[original] and state['jobs'][0]['job_id']=='old'
    assert state['plan']['mode']=='manual' and state['analysis']['status']=='awaiting_confirmation'
    response=client.post('/studio/p1/start',json={'plan_id':state['plan']['id'],'goals':['content']})
    assert response.status_code==200,response.text
    new=client.post('/studio/p1/drafts',json={'clip_ids':['c2'],'title':'New draft'}).json()
    assert new['language']=='en' and new['aspect']=='portrait'


def test_correction_during_analysis_is_rejected_without_changing_config(client):
    store.change('p1',lambda s:s.update(analysis={'status':'running','instance':store.INSTANCE}))
    response=client.put('/studio/p1/plan',json={'goal':'content'})
    assert response.status_code==409
    assert client.get('/studio/p1').json().get('plan') is None


def test_classifier_failure_keeps_source_for_retry(client,source,monkeypatch):
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('模型超时，请重试')))
    response=client.post('/studio/import',files={'video':('source.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id'];state=client.get('/studio/'+pid).json()
    assert state['analysis']['status']=='awaiting_confirmation' and state['plan']['mode']=='fallback'
    assert state['plan']['suggested_goals']==[]
    assert client.get('/studio/'+pid+'/source').status_code==200


def test_content_adapter_uses_existing_pipeline_without_broker(source,monkeypatch):
    calls=[]
    (source.parent/'input.srt').write_text('provided captions')
    fake=SimpleNamespace(apply=lambda **kwargs: calls.append(kwargs) or SimpleNamespace(get=lambda: {'success':True,'result':{'result':{'titled_clips':[{}]}}}))
    monkeypatch.setitem(sys.modules,'backend.tasks.processing',SimpleNamespace(process_video_pipeline=fake))
    jobs.run_content('p1',source)
    assert calls[0]['kwargs']['input_srt_path']==str(source.parent/'input.srt')
    assert calls[0]['throw'] is True


def test_content_adapter_rejects_empty_success(source,monkeypatch):
    fake=SimpleNamespace(apply=lambda **kwargs:SimpleNamespace(get=lambda:{'success':True,'result':{'result':{'titled_clips':[]}}}))
    monkeypatch.setitem(sys.modules,'backend.tasks.processing',SimpleNamespace(process_video_pipeline=fake))
    with pytest.raises(ValueError,match='可用'): jobs.run_content('p1',source)


def test_bad_subtitle_rejected_before_project_creation(client,source):
    response=client.post('/studio/import',files={'video':('source.mp4',source.read_bytes(),'video/mp4'),'subtitle':('notes.txt',b'not srt','text/plain')})
    assert response.status_code==422


def test_user_request_reaches_visual_selection_and_copy(source,monkeypatch):
    from backend.services.studio.models import Preferences, Scene
    prompts=[]
    def provider(content, **kwargs):
        prompts.append(content[0]['text'])
        if 'hooks' in content[0]['text']: return {'hooks':[{'title':'Challenge','hook':'Try this'}]}
        return {'events':[{'id':'e1','start':0,'end':1}]}
    monkeypatch.setattr(intelligence,'vision_call',provider)
    monkeypatch.setattr(intelligence,'sample',lambda *a, **kw:[])
    prefs=Preferences(goal='promo')
    intelligence.analyze(source,prefs,instruction='强调连续躲避')
    intelligence.make_drafts([Scene(id='e1',start=0,end=1)],prefs,instruction='强调连续躲避')
    assert len(prompts)==3 and all('强调连续躲避' in prompt for prompt in prompts)


def test_link_import_uses_same_automatic_plan(client,source,monkeypatch):
    import shutil
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:False)
    downloads=[]
    def download(pid,url,browser):
        downloads.append((url,browser))
        shutil.copy2(source,store.directory(pid)/'raw/input.mp4')
    monkeypatch.setattr(jobs,'download',download)
    monkeypatch.setattr(jobs,'run_content',lambda *a, **kw:None)
    response=client.post('/studio/import',data={'url':'https://www.youtube.com/watch?v=example'})
    assert response.status_code==200,response.text
    pid=response.json()['project_id']
    assert downloads==[('https://www.youtube.com/watch?v=example',None)]
    assert client.get('/studio/'+pid).json()['plan']['mode']=='fallback'


def test_multiple_choices_share_visual_analysis_and_require_confirmation(client,source,monkeypatch):
    from backend.services.studio.models import Scene
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    calls=[]
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:{**recommendation(),'suggested_goals':['highlight','promo']})
    monkeypatch.setattr(jobs,'analyze',lambda *a: calls.append('analysis') or ([Scene(id='e1',start=0,end=1)],{}))
    def drafts(events,prefs,*args,**kwargs):
        calls.append(prefs.goal)
        from backend.services.studio.models import Draft
        return [Draft(id=prefs.goal,title=prefs.goal,scenes=events).model_dump()]
    monkeypatch.setattr(jobs,'make_drafts',drafts)
    response=client.post('/studio/import',files={'video':('input.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id'];state=client.get('/studio/'+pid).json()
    assert calls==[] and state['drafts']==[]
    assert state['analysis']['status']=='awaiting_confirmation'
    body={'plan_id':state['plan']['id'],'goals':['highlight','promo']}
    assert client.post('/studio/'+pid+'/start',json={**body,'goals':[]}).status_code==422
    assert client.post('/studio/'+pid+'/start',json={**body,'plan_id':'stale'}).status_code==409
    assert calls==[]
    assert client.post('/studio/'+pid+'/start',json=body).status_code==200
    assert calls==['analysis','highlight','promo']
    assert client.post('/studio/'+pid+'/start',json=body).status_code==409
    assert len(client.get('/studio/'+pid).json()['drafts'])==2


def test_unchecked_goal_is_never_produced(client,source,monkeypatch):
    from backend.services.studio.models import Scene
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    calls=[]
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:{**recommendation(),'suggested_goals':['highlight','promo']})
    monkeypatch.setattr(jobs,'analyze',lambda *a: ([Scene(id='e1',start=0,end=1)],{}))
    monkeypatch.setattr(jobs,'make_drafts',lambda events,prefs,*args,**kwargs:calls.append(prefs.goal) or [])
    response=client.post('/studio/import',files={'video':('input.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id'];state=client.get('/studio/'+pid).json()
    assert client.post('/studio/'+pid+'/start',json={'plan_id':state['plan']['id'],'goals':['highlight']}).status_code==200
    assert calls==['highlight']


@pytest.mark.parametrize('model,quick,thinking', [('doubao-seed-2-1-pro-260915',True,True),('custom-vision',True,False),('doubao-seed-2-1-pro-260915',False,True)])
def test_quick_screening_request_is_small_and_provider_scoped(monkeypatch,model,quick,thinking):
    import io,json
    requests=[]
    def send(req,timeout):
        requests.append((json.loads(req.data),timeout))
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{}'}}]}).encode())
    monkeypatch.setattr(intelligence.urllib.request,'urlopen',send)
    intelligence.vision_call([],config={'base_url':'https://example.test/v1','model':model,'quick_screening':quick,'timeout':30})
    body,timeout=requests[0]
    assert body['max_tokens']==(1000 if quick else 4000)
    assert ('thinking' in body)==thinking
    if thinking: assert body['thinking']=={'type':'disabled'}
    assert timeout==30


def test_awaiting_confirmation_survives_restart_without_production(client,source,monkeypatch):
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:False)
    monkeypatch.setattr(jobs,'analyze',lambda *a:pytest.fail('must await confirmation'))
    response=client.post('/studio/import',files={'video':('input.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id']
    before=client.get('/studio/'+pid).json()
    monkeypatch.setattr(store,'INSTANCE','new-service-instance')
    after=client.get('/studio/'+pid).json()
    assert after['analysis']['status']=='awaiting_confirmation'
    assert after['plan']['id']==before['plan']['id'] and after['drafts']==[]


def test_nearby_independent_events_remain_multiple_highlights_with_context():
    from backend.services.studio.models import Scene,Preferences
    events=[Scene(id='a',label='躲避障碍',start=0,end=10),Scene(id='b',label='追赶避险',start=8,end=14),Scene(id='c',label='磁铁收集',start=16,end=20)]
    drafts=intelligence.make_drafts(events,Preferences(goal='highlight',duration=22),source_duration=22)
    assert len(drafts)==3
    assert [d['title'] for d in drafts]==['躲避障碍','追赶避险','磁铁收集']
    assert [(d['scenes'][0]['start'],d['scenes'][0]['end']) for d in drafts]==[(0,12),(6.5,16),(14.5,22)]
    assert [(e.start,e.end) for e in events]==[(0,10),(8,14),(16,20)]


def test_separate_events_do_not_fill_unobserved_gaps_or_exceed_duration():
    from backend.services.studio.models import Scene,Preferences
    events=[Scene(id='a',start=0,end=8),Scene(id='b',start=50,end=58)]
    scenes=intelligence.assemble_sequences(events,Preferences(goal='highlight',duration=10),60)
    assert len(scenes)==2 and scenes[0].end<=10 and scenes[1].start>=48.5
    assert all(0<=s.start<s.end<=60 and s.end-s.start<=10 for s in scenes)


def test_single_event_is_not_split_to_manufacture_multiple_highlights():
    from backend.services.studio.models import Scene,Preferences
    drafts=intelligence.make_drafts([Scene(id='a',start=0,end=22)],Preferences(goal='highlight'),source_duration=22)
    assert len(drafts)==1 and drafts[0]['scenes'][0]['end']==22


def test_analysis_keeps_more_than_three_independent_events(source,monkeypatch):
    from backend.services.studio.models import Preferences
    monkeypatch.setattr(intelligence,'_probe',lambda video:{'duration':120})
    monkeypatch.setattr(intelligence,'sample',lambda *a,**kw:[])
    events=[{'id':f'e{i}','start':i*20,'end':i*20+10,'label':f'事件{i}'} for i in range(5)]
    responses=iter([{'events':events},{'events':[events[0]]}])
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:next(responses))
    found,_=intelligence.analyze(source,Preferences(goal='highlight'))
    assert len(found)==5
    assert [e.id for e in found]==[e['id'] for e in events]


@pytest.mark.parametrize('goals',[['highlight','promo'],['promo','content','highlight']])
def test_shared_visual_failure_is_not_retried_for_second_goal(client,source,monkeypatch,goals):
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:recommendation())
    calls=[]
    reports=[]
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda error, phase, **kwargs: reports.append((error, phase)))
    failure=intelligence.VisionRequestError('rate_limited','请稍后重试',elapsed_seconds=2,http_status=429)
    failure.phase='scan'
    def analyze(*args):
        calls.append('scan')
        raise failure
    monkeypatch.setattr(jobs,'analyze',analyze)
    monkeypatch.setattr(jobs,'make_drafts',lambda *a,**kw:pytest.fail('no drafts without analysis'))
    monkeypatch.setattr(jobs,'run_content',lambda *a,**kw:calls.append('content') or [{'id':'clip'}])
    response=client.post('/studio/import',files={'video':('input.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id'];state=client.get('/studio/'+pid).json()
    body={'plan_id':state['plan']['id'],'goals':goals}
    assert client.post('/studio/'+pid+'/start',json=body).status_code==200
    result=client.get('/studio/'+pid).json()
    assert calls==(['scan','content'] if 'content' in goals else ['scan'])
    assert result['drafts']==[] and result['analysis']['status']=='failed'
    details=result['analysis']['diagnostics']
    assert [d['goal'] for d in details]==[g for g in goals if g!='content']
    assert all(d['code']=='rate_limited' and d['http_status']==429 and d['phase']=='scan' for d in details)
    assert store.read(pid)['analysis']['diagnostics']==details
    assert client.post('/studio/'+pid+'/start',json=body).status_code==409
    assert calls.count('scan')==1
    assert len(reports)==1
    assert result['analysis']['failed_goals']==[g for g in goals if g!='content']
    assert result['analysis']['outcome']==('partial' if 'content' in goals else 'failed')


def test_hook_failure_preserves_other_goal_and_does_not_repeat_analysis(client,source,monkeypatch):
    from backend.services.studio.models import Scene, Draft
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:recommendation())
    calls=[]
    monkeypatch.setattr(jobs,'analyze',lambda *a:calls.append('scan') or ([Scene(id='e1',start=0,end=1)],{'duration':1}))
    def drafts(events,prefs,*a,**kw):
        calls.append(prefs.goal)
        if prefs.goal=='promo':
            error=intelligence.VisionRequestError('output_truncated','模型输出不完整',elapsed_seconds=8)
            error.phase='hooks'
            raise error
        return [Draft(id='highlight',title='完整高光',scenes=events).model_dump()]
    monkeypatch.setattr(jobs,'make_drafts',drafts)
    response=client.post('/studio/import',files={'video':('input.mp4',source.read_bytes(),'video/mp4')})
    pid=response.json()['project_id'];plan=client.get('/studio/'+pid).json()['plan']
    assert client.post('/studio/'+pid+'/start',json={'plan_id':plan['id'],'goals':['promo','highlight']}).status_code==200
    result=client.get('/studio/'+pid).json()
    assert calls==['scan','promo','highlight']
    assert result['analysis']['outcome']=='partial'
    assert result['analysis']['succeeded_goals']==['highlight']
    assert result['analysis']['failed_goals']==['promo']
    assert result['analysis']['result_count']==1
    assert result['analysis']['duration_ms']>=0
    assert [d['id'] for d in result['drafts']]==['highlight']
    assert result['analysis']['diagnostics']==[{'goal':'promo','code':'output_truncated','phase':'hooks','elapsed_seconds':8}]


def test_confirmation_dispatch_failure_preserves_staging_and_allows_explicit_retry(client, source, monkeypatch):
    from backend.core.database import SessionLocal
    from backend.models import Project
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    response = client.post('/studio/import', files={'video':('input.mp4', source.read_bytes(), 'video/mp4')})
    pid = response.json()['project_id']
    from backend.tests.test_studio import draft
    saved = store.save_draft(pid, draft(), create=True)
    store.change(pid, lambda state: state['jobs'].append({'job_id':'existing', 'status':'completed', 'draft_id':saved['id'], 'revision':saved['revision']}))
    output = store.directory(pid) / 'previous.mp4'
    output.write_bytes(b'previous export')
    before = store.read(pid)
    with SessionLocal() as db:
        p = db.get(Project, pid)
        original_config, original_status = dict(p.processing_config), p.status
    calls = []
    class Reject:
        def submit(self, *args):
            calls.append(args)
            raise RuntimeError('private executor failure')
    monkeypatch.setattr(jobs, 'executor', Reject())
    payload = {'plan_id':before['plan']['id'], 'goals':['content']}
    failed = client.post('/studio/'+pid+'/start', json=payload)
    assert failed.status_code == 422
    assert '重试确认' in failed.json()['detail']
    assert 'private executor' not in failed.text
    assert store.read(pid) == before
    assert output.read_bytes() == b'previous export'
    assert (store.directory(pid)/'raw/input.mp4').read_bytes() == source.read_bytes()
    with SessionLocal() as db:
        p = db.get(Project, pid)
        assert p.processing_config == original_config and p.status == original_status
    assert client.get('/studio/'+pid).json()['analysis']['status'] == 'awaiting_confirmation'
    assert len(calls) == 1  # Reading the state never submits work.
    produced = []
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(jobs, 'run_content', lambda *args: produced.append(args))
    assert client.post('/studio/'+pid+'/start', json=payload).status_code == 200
    assert len(produced) == 1
    with SessionLocal() as db:
        assert db.get(Project, pid).processing_config['import_staging'] is False
    assert client.post('/studio/'+pid+'/start', json=payload).status_code == 409
    assert len(produced) == 1


@pytest.mark.parametrize('route', ['visual', 'subtitle'])
@pytest.mark.parametrize('import_aspect,confirmation,expected', [
    (None, {}, ['original', 'portrait']),
    ('landscape', {}, ['landscape', 'landscape']),
    ('landscape', {'aspect':None}, ['original', 'portrait']),
    (None, {'aspect':'original'}, ['original', 'original']),
    (None, {'aspect':'landscape'}, ['landscape', 'landscape']),
    (None, {'aspect':'portrait'}, ['portrait', 'portrait']),
])
def test_confirm_matches_each_output_aspect_without_extra_analysis(
    root, source, monkeypatch, route, import_aspect, confirmation, expected,
):
    from backend.services.studio.models import ConfirmPlan, Preferences, Scene
    from backend.services.studio import subtitle_highlights, subtitle_promo
    seen=[]; scans=[]
    monkeypatch.setattr(jobs,'executor',Immediate())
    monkeypatch.setattr(jobs,'source',lambda _:source)
    monkeypatch.setattr(jobs,'mark_project',lambda *a,**kw:None)
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**kw:pytest.fail('paid call'))
    def analyze(*args):
        scans.append('visual')
        return [Scene(id='e',start=0,end=1)], {}
    def content(*args):
        scans.append('subtitle')
        return []
    def record(prefs):
        seen.append((prefs.goal,prefs.aspect))
        return []
    monkeypatch.setattr(jobs,'analyze',analyze)
    monkeypatch.setattr(jobs,'run_content',content)
    monkeypatch.setattr(jobs,'make_drafts',lambda events,prefs,*a,**kw:record(prefs))
    monkeypatch.setattr(subtitle_highlights,'make_highlights',lambda clips,prefs,*a:record(prefs))
    monkeypatch.setattr(subtitle_promo,'make_promos',lambda pid,clips,prefs,*a:record(prefs))
    plan={'id':'screened','aspect':'original','preferences':Preferences(aspect=import_aspect or 'original').model_dump(),
          'overrides':{'aspect':import_aspect} if import_aspect else {}}
    store.write('p1',{'plan':plan,'analysis':{'status':'awaiting_confirmation'},'drafts':[],'events':[],'jobs':[]})
    jobs.confirm_project('p1',ConfirmPlan(plan_id='screened',analysis_mode=route,goals=['highlight','promo'],**confirmation))
    state=store.read('p1')
    assert state['analysis']['status']=='completed'
    assert seen==list(zip(['highlight','promo'],expected))
    assert scans==[route]
    assert state['plan']['goal_preferences']['promo']['aspect']==expected[1]


class RejectSubmission:
    def submit(self, *args):
        raise RuntimeError('private executor failure')


def test_initial_import_dispatch_failure_is_retryable(client, source, monkeypatch):
    from backend.core.database import SessionLocal
    from backend.models import Project
    monkeypatch.setattr(jobs, 'executor', RejectSubmission())
    response = client.post('/studio/import', data={'name':'dispatch recovery'}, files={'video':('input.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 422
    assert '导入任务未能启动' in response.json()['detail']
    assert 'private executor' not in response.text
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.name == 'dispatch recovery').one()
        pid = str(project.id)
        assert project.status.value == 'failed'
    assert store.read(pid)['analysis']['status'] == 'failed'
    assert (store.directory(pid) / 'raw/input.mp4').read_bytes() == source.read_bytes()
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    assert client.post('/studio/'+pid+'/analyze').status_code == 200
    assert store.read(pid)['analysis']['status'] == 'awaiting_confirmation'


@pytest.mark.parametrize("route", ["analyze", "plan"])
def test_rescreen_dispatch_failure_preserves_plan_and_exports(client, source, monkeypatch, route):
    from backend.tests.test_studio import draft
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    pid = client.post('/studio/import', files={'video':('input.mp4', source.read_bytes(), 'video/mp4')}).json()['project_id']
    saved = store.save_draft(pid, draft(), create=True)
    store.change(pid, lambda data: data['jobs'].append({'job_id':'existing', 'status':'completed', 'draft_id':saved['id']}))
    before = store.read(pid)
    monkeypatch.setattr(jobs, 'executor', RejectSubmission())
    from backend.core.database import SessionLocal
    from backend.models import Project
    with SessionLocal() as db:
        config = dict(db.get(Project, pid).processing_config)
    def rescreen():
        if route == 'plan':
            return client.put('/studio/'+pid+'/plan', json={'goal':'highlight'})
        return client.post('/studio/'+pid+'/analyze')
    response = rescreen()
    assert response.status_code == 422
    with SessionLocal() as db:
        assert db.get(Project, pid).processing_config == config
    assert store.read(pid) == before
    monkeypatch.setattr(jobs, 'executor', Immediate())
    assert rescreen().status_code == 200
    after = store.read(pid)
    assert after['analysis']['status'] == 'awaiting_confirmation'
    assert after['drafts'] == before['drafts'] and after['jobs'] == before['jobs']


@pytest.mark.parametrize('url', [
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com/watch?si=abc&v=dQw4w9WgXcQ',
    'https://youtu.be/dQw4w9WgXcQ?si=abc',
    'https://m.youtube.com/watch?v=dQw4w9WgXcQ',
    'https://youtube.com/shorts/dQw4w9WgXcQ',
    'https://youtube.com/live/dQw4w9WgXcQ',
])
def test_current_studio_accepts_shared_youtube_urls(client, source, monkeypatch, url):
    seen = []
    def download(pid, link, browser):
        seen.append(link)
        (store.directory(pid) / 'raw/input.mp4').write_bytes(source.read_bytes())
    monkeypatch.setattr(jobs, 'download', download)
    monkeypatch.setattr(jobs, 'executor', Immediate())
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    response = client.post('/studio/import', data={'url':url})
    assert response.status_code == 200
    assert seen == [url]
    assert store.read(response.json()['project_id'])['analysis']['status'] == 'awaiting_confirmation'


def test_studio_content_preserves_structured_pipeline_failure(monkeypatch, tmp_path):
    from backend.tasks.processing import process_video_pipeline
    from backend.pipeline.failures import PipelineFailure
    class Result:
        def get(self):
            return {'success':False, 'error':'private hint', 'result':{'stage':'ANALYZE', 'error_code':'llm_not_configured'}}
    monkeypatch.setattr(process_video_pipeline, 'apply', lambda **kwargs: Result())
    with pytest.raises(PipelineFailure) as caught:
        jobs.run_content('p', tmp_path/'input.mp4')
    assert caught.value.code == 'llm_not_configured'


def test_local_import_creates_project_thumbnail(client, source, monkeypatch):
    import base64
    import io
    from PIL import Image
    from backend.core.database import SessionLocal
    from backend.models import Project
    monkeypatch.setattr(jobs, 'executor', Immediate())
    response = client.post('/studio/import', data={'goal': 'content'},
                           files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    pid = response.json()['project_id']
    with SessionLocal() as db:
        thumbnail = db.get(Project, pid).thumbnail
    assert thumbnail.startswith('data:image/jpeg;base64,')
    Image.open(io.BytesIO(base64.b64decode(thumbnail.split(',', 1)[1]))).verify()
    assert client.get('/studio/' + pid).json()['analysis']['status'] == 'awaiting_confirmation'


def test_many_auto_variants_are_all_queued_for_rendering(root, monkeypatch):
    submitted = []
    class Capture:
        def submit(self, fn, *args, **kwargs):
            submitted.append(args)
    monkeypatch.setattr(jobs, 'render_executor', Capture())
    branding = {'outro_enabled': False, 'outro_version': 'v1'}
    count = 20  # e.g. a two-hour source with many complete highlights
    drafts = [jobs.Draft(id=f'd{i}', title=f'T{i}', scenes=[jobs.Scene(id='s', label='S', start=i, end=i + 1)], subtitles=False).model_dump() for i in range(count)]
    store.write('p1', {
        'schema_version': 2, 'drafts': drafts, 'events': [], 'jobs': [], 'analysis': {'status': 'running'},
        'generation': {'auto_start': True, 'status': 'rendering'},
        'output_variants': [{'id': f'v{i}', 'draft_id': f'd{i}', 'draft_revision': 1, 'strategy_id': 'douyin', 'strategy_version': 1, 'branding': branding, 'status': 'queued'} for i in range(count)],
    })

    jobs._dispatch_pending_variants('p1')
    jobs._dispatch_pending_variants('p1')  # idempotent: attached variants are not resubmitted
    state = store.read('p1')
    assert all(item.get('render_job_id') for item in state['output_variants'])
    assert len(submitted) == count and len(state['jobs']) == count
    assert state['generation']['status'] == 'rendering'


def test_only_hard_platform_limits_trim_and_they_cut_at_sentence_ends(root, monkeypatch):
    from backend.services import publish_export
    from backend.services.platform_strategy import platform_strategy
    monkeypatch.setattr(publish_export, '_load_srt_entries', lambda _pid: [
        {'start_time': '00:00:00,000', 'end_time': '00:02:50,000'},
        {'start_time': '00:02:50,000', 'end_time': '00:03:05,000'},
    ])
    long_moment = {'id': 'x', 'revision': 1, 'scenes': [{'id': 's', 'label': 'S', 'start': 0.0, 'end': 240.0}]}

    kept, trimmed = jobs._fit_platform_limit('p1', long_moment, platform_strategy('douyin'))
    assert trimmed is None and kept['scenes'][0]['end'] == 240.0  # Douyin accepts long uploads: stay whole

    cut, trimmed = jobs._fit_platform_limit('p1', long_moment, platform_strategy('youtube_shorts'))
    assert trimmed == 180 and cut['scenes'][0]['end'] == 170.0  # last sentence end within 180 s
    assert long_moment['scenes'][0]['end'] == 240.0  # input draft is not mutated


def test_render_ffmpeg_threads_are_bounded_and_low_priority():
    from backend.services import render_limits
    assert int(render_limits.THREADS) >= 2
    assert '-filter_complex_threads' in render_limits.input_args()
    cmd, kwargs = render_limits.low_priority(['ffmpeg', '-version'])
    assert cmd[-2:] == ['ffmpeg', '-version']
    assert 'preexec_fn' not in kwargs


@pytest.mark.parametrize('automatic', [True, False])
def test_import_staging_matches_confirmation_before_worker_starts(client, source, monkeypatch, automatic):
    from backend.services.project_service import ProjectService
    created = []
    original = ProjectService.create_project
    def capture(self, body):
        project = original(self, body)
        created.append(project.processing_config)
        return project
    class PausedExecutor:
        def submit(self, *_):
            return None  # Hold screening exactly at the startup boundary seen by the UI.
    monkeypatch.setattr(ProjectService, 'create_project', capture)
    monkeypatch.setattr(jobs, 'executor', PausedExecutor())
    monkeypatch.setattr(jobs, '_prepare_speaker_framing', lambda *_: None)
    response = client.post('/studio/import', data={'auto_start': str(automatic).lower()},
                           files={'video': ('source.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    state = client.get('/studio/' + response.json()['project_id']).json()
    assert state['generation']['status'] == 'screening'
    assert created[0]['import_staging'] is (not automatic), 'automatic output must remain on its progress page before the worker runs'
