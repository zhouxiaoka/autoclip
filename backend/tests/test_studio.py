"""Workspace invariants and real ffmpeg output; no provider calls in regression tests."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from pydantic import ValidationError
from backend.services.studio import store, intelligence, vision_settings
from backend.services.studio.models import Draft, Scene, Preferences

@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p1').mkdir(parents=True)
    return store.directory('p1')

def draft(**values):
    return Draft(id='d1', title='First cut', scenes=[Scene(id='s1', start=.2, end=1.2)], subtitles=False, **values)

def test_draft_save_preserves_original_and_detects_conflict(root):
    original = root / 'metadata' / 'clips_metadata.json'
    original.parent.mkdir()
    original.write_text('[{"title":"legacy"}]')
    first = store.save_draft('p1', draft(), create=True)
    second = store.save_draft('p1', Draft.model_validate({**first, 'hook': 'New opening'}))
    assert second['revision'] == 2
    with pytest.raises(store.ConflictError):
        store.save_draft('p1', Draft.model_validate(first))
    assert original.read_text() == '[{"title":"legacy"}]'
    assert store.read('p1')['drafts'][0]['hook'] == 'New opening'

def test_restart_turns_running_jobs_into_retryable_failures(root):
    store.write('p1', {'drafts': [], 'events': [], 'jobs': [{'job_id':'j1','status':'running','instance':'previous'}], 'analysis':{'status':'running','instance':'previous'}})
    state = store.read('p1')
    assert state['jobs'][0]['status'] == 'failed'
    assert state['analysis']['status'] == 'failed'

@pytest.mark.parametrize('start,end', [(1,1),(-1,2),(2,1),(float('nan'),3),(0,float('inf'))])
def test_reject_invalid_scene(start,end):
    with pytest.raises(ValidationError): Scene(id='bad',start=start,end=end)

def test_no_path_traversal(root):
    with pytest.raises(ValueError): store.directory('../another-project')

def test_reject_out_of_bounds_and_oversized_composition():
    with pytest.raises(ValueError): intelligence.validate_scenes([Scene(id='s',start=0,end=5)],4)
    with pytest.raises(ValueError): intelligence.validate_scenes([Scene(id='s',start=0,end=1900)],2000)

def test_visual_refinement_uses_valid_source_timestamps(root,monkeypatch):
    calls=[]
    monkeypatch.setattr(intelligence,'_probe',lambda _: {'duration':30})
    monkeypatch.setattr(intelligence,'sample',lambda video,times,folder: calls.append(times) or [])
    responses=iter([{'events':[{'id':'e1','label':'避障','start':5,'end':20,'evidence':'障碍密集'}]}, {'events':[{'id':'r','label':'连续避障','start':6,'end':19,'evidence':'复核'}]}])
    monkeypatch.setattr(intelligence,'vision_call',lambda _: next(responses))
    stages=[]
    events, coverage=intelligence.analyze(Path('unused'),Preferences(goal='highlight'),stages.append)
    assert stages==['扫描画面，寻找候选高光','复核首选高光的起止边界']
    assert events[0].id=='e1' and events[0].start==6
    assert min(calls[1])==3 and max(calls[1])==22
    assert coverage['sample_interval']==2

def test_visual_empty_evidence_is_not_fabricated(root,monkeypatch):
    monkeypatch.setattr(intelligence,'_probe',lambda _: {'duration':30})
    monkeypatch.setattr(intelligence,'sample',lambda *args: [])
    monkeypatch.setattr(intelligence,'vision_call',lambda _: {'events':[]})
    with pytest.raises(ValueError,match='没有找到'): intelligence.analyze(Path('unused'),Preferences(goal='promo'))

def test_settings_mask_key_preserve_and_clear(root,monkeypatch):
    monkeypatch.setenv('SEEDANCE_API_KEY','test-env-key')
    monkeypatch.setenv('SEEDANCE_BASE_URL','https://example.test/v1')
    body=vision_settings.VisionSettingsInput(base_url='https://example.test/v1/chat/completions/',model='vision-test')
    first=vision_settings.save(body)
    assert first['base_url']=='https://example.test/v1'
    assert first['has_key'] is True and 'api_key' not in first and 'test-env-key' not in json.dumps(first)
    second=vision_settings.save(body.model_copy(update={'model':'vision-test-2'}))
    assert vision_settings.effective()['api_key']=='test-env-key'
    assert second['model']=='vision-test-2'
    cleared=vision_settings.save(body.model_copy(update={'clear_key':True}))
    assert not cleared['has_key']
    assert vision_settings.effective()['api_key']==''
    config=root.parent.parent/'vision-settings.json'
    assert config.stat().st_mode & 0o777 == 0o600

def test_connection_test_really_sends_image_without_leaking_key(root,monkeypatch):
    captured=[]
    monkeypatch.setattr(intelligence,'vision_call',lambda content,config: captured.append((content,config)) or {'color':'red'})
    result=vision_settings.test(vision_settings.VisionSettingsInput(base_url='https://example.test/v1',model='v',api_key='secret'))
    assert result['ok']
    assert captured[0][0][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert 'secret' not in json.dumps(result)

@pytest.fixture
def source(root):
    if not shutil.which('ffmpeg'): pytest.skip('ffmpeg unavailable')
    raw=root/'raw';raw.mkdir()
    video=raw/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=3','-f','lavfi','-i','sine=f=440:d=3','-shortest','-y',str(video)],check=True)
    return video

def test_render_two_scenes_reordered_muted_and_versioned(root,source):
    from backend.services.studio.render import render_draft
    d=draft(original_audio=False)
    d.scenes=[Scene(id='late',start=1.5,end=2.5),Scene(id='early',start=.2,end=.7)]
    progress=[]
    result=render_draft('p1',source,d,'job1',progress.append)
    out=root/'output'/'studio'/'job1.mp4'
    assert out.is_file() and result['width']==320 and abs(result['duration']-1.5)<.1
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]))['streams']
    assert all(s['codec_type']!='audio' for s in streams)
    # Compare the decoded first frame with the late source interval; proves ordering is applied.
    def pixel(path,start):
        return subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(path),'-frames:v','1','-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
    assert max(abs(a-b) for a,b in zip(pixel(out,0),pixel(source,1.5)))<10
    assert progress==[50,90]
    assert not list(out.parent.glob('*.part.mp4'))

def test_translation_is_applied_and_warning_for_missing_srt(root,source,monkeypatch):
    from backend.services.studio import render
    monkeypatch.setattr(render,'text_json',lambda *args: {'title':'A new opening','subtitles':[]})
    if not render.resolve_cjk_font(): pytest.skip('No title font')
    d=draft(language='en',hook='新开头');d.subtitles=True
    result=render.render_draft('p1',source,d,'translated',lambda _:None)
    assert result['warnings']==['原素材没有可用字幕，本次未烧录字幕']
    assert (root/'output'/'studio'/'translated.mp4').stat().st_size>0

@pytest.fixture
def client(root, source, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models import Base, Project, Clip
    from backend.models.project import ProjectStatus
    from backend.core import database
    from backend.api.v1.studio import router
    engine = create_engine('sqlite:///' + str(root.parent.parent / 'api.sqlite'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    with sessions() as db:
        db.add(Project(id='p1', name='Legacy project', status=ProjectStatus.COMPLETED, video_path=str(source)))
        db.add_all([Clip(id='c1', project_id='p1', title='Early', start_time=0, end_time=1, duration=1), Clip(id='c2', project_id='p1', title='Late', start_time=1, end_time=2, duration=1)])
        db.commit()
    def get_db():
        with sessions() as db: yield db
    app=FastAPI(); app.include_router(router, prefix='/studio')
    app.dependency_overrides[database.get_db]=get_db
    with TestClient(app) as c: yield c
    engine.dispose()

def test_api_legacy_adapter_conflict_and_source(client):
    assert client.get('/studio/missing').status_code==404
    assert client.post('/studio/p1/drafts',json={'clip_ids':['missing'],'title':'No'}).status_code==404
    response=client.post('/studio/p1/drafts',json={'clip_ids':['c2','c1'],'title':'New cut'})
    assert response.status_code==200, response.text
    d=response.json(); assert [s['label'] for s in d['scenes']]==['Late','Early']
    d['hook']='Changed'
    saved=client.put('/studio/p1/drafts/'+d['id'],json=d)
    assert saved.status_code==200 and saved.json()['revision']==2
    assert client.put('/studio/p1/drafts/'+d['id'],json=d).status_code==409
    assert client.get('/studio/p1/source').headers['content-type']=='video/mp4'
    assert len(client.get('/studio/p1').json()['drafts'])==1

def test_api_export_runs_real_worker_and_survives_poll(client,root):
    import time
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Render'}).json()
    result=client.post('/studio/p1/drafts/'+d['id']+'/export')
    assert result.status_code==200
    job=result.json(); assert 'snapshot' not in job
    for _ in range(100):
        jobs=client.get('/studio/p1').json()['jobs']
        if jobs[0]['status'] in ('completed','failed'): break
        time.sleep(.05)
    assert jobs[0]['status']=='completed',jobs
    output=client.get('/studio/p1/exports/'+job['job_id']+'/video?download=true')
    assert output.status_code==200 and len(output.content)>1000
    assert 'attachment' in output.headers['content-disposition']
    assert client.get('/studio/p1/exports/missing/video').status_code==404

def test_api_settings_static_routes_and_errors_hide_key(client,monkeypatch):
    body={'base_url':'https://example.test/v1','model':'test','api_key':'private-key'}
    assert client.put('/studio/vision-settings',json=body).status_code==200
    response=client.get('/studio/vision-settings')
    assert response.status_code==200 and response.json()['has_key']
    assert 'private-key' not in response.text
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('private-key')))
    response=client.post('/studio/vision-settings/test',json=body)
    assert response.status_code==502 and 'private-key' not in response.text

def test_visual_import_worker_persists_project_status(client,root,source,monkeypatch):
    from backend.services.studio import jobs
    from backend.core.database import SessionLocal
    from backend.models.project import Project, ProjectStatus
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    monkeypatch.setattr(jobs,'analyze',lambda *a: ([Scene(id='e1',label='真实事件',start=0,end=1)],{}))
    class Immediate:
        def submit(self,fn,*args): fn(*args)
    monkeypatch.setattr(jobs,'executor',Immediate())
    response=client.post('/studio/import',data={'goal':'highlight','name':'Visual upload'},files={'video':('game.mp4',source.read_bytes(),'video/mp4')})
    assert response.status_code==200,response.text
    pid=response.json()['project_id']
    with SessionLocal() as db:
        p=db.get(Project,pid)
        assert p.status==ProjectStatus.COMPLETED
        assert p.processing_config['creative']['goal']=='highlight'
    state=client.get('/studio/'+pid).json()
    assert state['analysis']['status']=='completed' and len(state['drafts'])==1
    assert client.get('/studio/'+pid+'/source').status_code==200

def test_duplicate_copies_unsaved_edits_preserving_parent_and_exports(client):
    original = client.post('/studio/p1/drafts', json={'clip_ids': ['c2', 'c1'], 'title': '原版'}).json()
    store.change('p1', lambda state: state['jobs'].append({'job_id': 'old-export', 'draft_id': original['id'], 'revision': 1, 'status': 'completed', 'snapshot': original}))
    snapshot = {**original, 'hook': '未保存的新开头', 'scenes': list(reversed(original['scenes']))}
    response = client.post('/studio/p1/drafts/' + original['id'] + '/duplicate', json={'draft': snapshot, 'title': '  English variant  ', 'language': 'en'})
    assert response.status_code == 200, response.text
    copied = response.json()
    assert copied['id'] != original['id'] and copied['revision'] == 1
    assert copied['parent_draft_id'] == original['id'] and copied['parent_revision'] == 1
    assert copied['language'] == 'en' and copied['title'] == 'English variant'
    assert copied['hook'] == snapshot['hook'] and copied['scenes'] == snapshot['scenes']
    state = store.read('p1')
    assert next(d for d in state['drafts'] if d['id'] == original['id']) == original
    assert state['jobs'][0]['snapshot'] == original
    from backend.core.database import SessionLocal
    from backend.models import Project
    with SessionLocal() as db:
        assert db.get(Project, 'p1').processing_config['studio_draft_count'] == 2
    copied['hook'] = 'Changed only in the variant'
    assert client.put('/studio/p1/drafts/' + copied['id'], json=copied).status_code == 200
    assert store.read('p1')['drafts'][0] == original

def test_duplicate_old_revision_can_be_recovered_without_overwriting_new_parent(client):
    original = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    saved = client.put('/studio/p1/drafts/' + original['id'], json={**original, 'hook': 'Other window edit'}).json()
    response = client.post('/studio/p1/drafts/' + original['id'] + '/duplicate', json={'draft': {**original, 'hook': 'My unsaved edit'}, 'title': 'Recovered edit', 'language': 'zh'})
    assert response.status_code == 200
    state = store.read('p1')
    assert state['drafts'][0] == saved
    assert state['drafts'][1]['parent_revision'] == 1
    assert state['drafts'][1]['hook'] == 'My unsaved edit'

def test_duplicate_rejects_wrong_parent_empty_title_and_invalid_source_ranges(client):
    original = client.post('/studio/p1/drafts', json={'clip_ids': ['c1'], 'title': 'Original'}).json()
    url = '/studio/p1/drafts/' + original['id'] + '/duplicate'
    body = {'draft': original, 'title': 'Variant', 'language': 'ja'}
    assert client.post(url, json={**body, 'title': '  '}).status_code == 422
    assert client.post(url, json={**body, 'draft': {**original, 'id': 'another'}}).status_code == 422
    assert client.post(url, json={**body, 'draft': {**original, 'revision': 999}}).status_code == 409
    invalid = {**original, 'scenes': [{**original['scenes'][0], 'end': 999}]}
    assert client.post(url, json={**body, 'draft': invalid}).status_code == 422
    assert client.post('/studio/p1/drafts/missing/duplicate', json={**body, 'draft': {**original, 'id': 'missing'}}).status_code == 404
    assert len(store.read('p1')['drafts']) == 1

def test_candidates_are_project_scoped_and_invalid_ranges_are_excluded(client):
    from backend.core.database import SessionLocal
    from backend.models import Project, Clip
    with SessionLocal() as db:
        db.add(Project(id='other', name='Other project'))
        db.add(Clip(id='private', project_id='other', title='Other footage', start_time=0, end_time=1, duration=1))
        db.add(Clip(id='bad', project_id='p1', title='Outside source', start_time=0, end_time=999, duration=999))
        db.commit()
    store.change('p1', lambda state: state['events'].extend([
        {'id':'event-1','label':'Visual event','start':.5,'end':1.5,'evidence':'Visible obstacle'},
        {'id':'invalid','label':'Bad event','start':2,'end':1},
    ]))
    response=client.get('/studio/p1/candidates')
    assert response.status_code==200,response.text
    data=response.json()
    assert abs(data['duration']-3)<.1
    assert [c['id'] for c in data['candidates']]==['visual-event-1','legacy-c1','legacy-c2']
    assert data['warnings']==['2 个片段时间无效，已从候选中排除']
    assert 'Other footage' not in response.text
    assert client.get('/studio/missing/candidates').status_code==404

def test_candidate_replacement_and_append_save_render_actual_order(client,root,source):
    import time
    original=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Candidate test'}).json()
    candidates=client.get('/studio/p1/candidates').json()['candidates']
    scenes=[{k:v for k,v in c.items() if k!='kind'} for c in reversed(candidates)]
    updated=client.put('/studio/p1/drafts/'+original['id'],json={**original,'scenes':scenes,'original_audio':False,'subtitles':False})
    assert updated.status_code==200,updated.text
    assert [s['start'] for s in updated.json()['scenes']]==[1,0]
    job=client.post('/studio/p1/drafts/'+original['id']+'/export').json()
    for _ in range(100):
        state=client.get('/studio/p1').json()
        if state['jobs'][0]['status'] in ('completed','failed'):break
        time.sleep(.05)
    assert state['jobs'][0]['status']=='completed',state['jobs']
    assert abs(state['jobs'][0]['result']['duration']-2)<.1
    output=client.get('/studio/p1/exports/'+job['job_id']+'/video')
    assert output.status_code==200
    # Ensure the first decoded output frame is the replacement (late) interval.
    video=root/'output'/'studio'/(job['job_id']+'.mp4')
    def pixel(path,start):
        return subprocess.check_output(['ffmpeg','-v','error','-ss',str(start),'-i',str(path),'-frames:v','1','-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
    assert max(abs(a-b) for a,b in zip(pixel(video,0),pixel(source,1)))<10

def test_empty_upload_is_actionable_and_does_not_create_project(client,monkeypatch):
    from backend.core.database import SessionLocal
    from backend.models import Project
    monkeypatch.setattr(intelligence,'ready',lambda:True)
    response=client.post('/studio/import',data={'goal':'highlight'},files={'video':('empty.mp4',b'','video/mp4')})
    assert response.status_code==422 and '为空' in response.json()['detail']
    with SessionLocal() as db: assert db.query(Project).count()==1

def test_export_requires_the_revision_shown_in_editor(client,monkeypatch):
    from backend.services.studio import jobs
    monkeypatch.setattr(jobs,'export',lambda pid,draft: {'revision':draft.revision})
    original=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Original'}).json()
    url='/studio/p1/drafts/'+original['id']
    assert client.post(url+'/export',json={'revision':1}).json()['revision']==1
    assert client.put(url,json={**original,'hook':'New text'}).status_code==200
    assert client.post(url+'/export',json={'revision':1}).status_code==409
    assert client.post(url+'/export',json={'revision':2}).json()['revision']==2

def test_vision_timeout_is_actionable_and_hides_credentials(monkeypatch):
    monkeypatch.setattr(intelligence.urllib.request,'urlopen',lambda *a,**k: (_ for _ in ()).throw(TimeoutError('read timed out private-key')))
    with pytest.raises(RuntimeError,match='提高请求超时') as error:
        intelligence.vision_call([],config={'base_url':'https://example.test/v1','model':'vision','api_key':'private-key','timeout':10})
    assert 'private-key' not in str(error.value)


def test_portrait_promo_defaults_and_legacy_compatibility(monkeypatch):
    monkeypatch.setattr(intelligence, 'vision_call', lambda _: {'hooks':[{'title':'Run','hook':'Can you escape?'}]})
    result=intelligence.make_drafts([Scene(id='s',start=0,end=1)],Preferences(goal='promo',aspect='portrait'))[0]
    assert result['layout']=='crop' and result['title_style']=='impact'
    assert draft().layout=='fit' and draft().title_style=='plain'
    for x in (-.1,1.1,float('nan')):
        with pytest.raises(ValidationError): draft(crop_x=x)


def test_title_wrapping_bounds_and_literal_text():
    from backend.services.studio.titles import title_layout, text_width
    for text in ["They're right behind you!", '追兵就在身后，能逃脱吗？', '100% {test}: escape!', 'W'*30]:
        lines,size=title_layout(text,'impact',1080,1920)
        assert 1<=len(lines)<=3
        assert all(text_width(line)*size <= 1080*.80+.1 for line in lines)
    with pytest.raises(ValueError,match='太长'): title_layout('非常长的文字'*100,'card',1080,1920)


@pytest.mark.parametrize('style,x,expected', [('impact',.5,'blue'),('card',0,'red')])
def test_portrait_fills_frame_and_applies_focus_and_title(root,style,x,expected):
    from backend.services.studio.render import render_draft
    raw=root/'raw';raw.mkdir()
    video=raw/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=red:s=320x180:r=30:d=1,drawbox=x=105:y=0:w=110:h=180:color=blue:t=fill','-y',str(video)],check=True)
    d=Draft(id='portrait',title='Portrait',hook='CAN YOU ESCAPE?',title_style=style,aspect='portrait',layout='crop',crop_x=x,subtitles=False,scenes=[Scene(id='s',start=0,end=.8)])
    result=render_draft('p1',video,d,style,lambda _:None)
    assert (result['width'],result['height'])==(1080,1920)
    out=root/'output/studio'/f'{style}.mp4'
    pixel=subprocess.check_output(['ffmpeg','-v','error','-ss','0.3','-i',str(out),'-frames:v','1','-vf','crop=20:20:0:1800,scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'])
    # Bottom of the portrait must contain the selected footage, never a black bar.
    assert pixel[2 if expected=='blue' else 0]>200
    assert max(pixel)-min(pixel)>180
