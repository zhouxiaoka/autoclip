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
    state=client.get('/studio/'+pid).json()
    assert state['analysis']['status']=='awaiting_confirmation' and state['drafts']==[]
    assert client.post('/studio/'+pid+'/start',json={'plan_id':state['plan']['id'],'goals':['highlight'],'analysis_mode':'visual'}).status_code==200
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
    assert result['layout']=='crop' and result['title_style']=='comic'
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


@pytest.mark.parametrize('style,version', [('comic',1),('neon',1),('arena',1),('comic',2),('neon',2),('arena',2),('editorial',2),('comic',3),('neon',3),('arena',3),('editorial',3),('pixel',3),('frosted',3),('comic',4),('comic',5),('comic',6),('neon',6),('arena',6),('pixel',6),('editorial',6),('frosted',6)])
def test_title_art_preview_matches_export_geometry(root,style,version):
    import io
    from PIL import Image,ImageChops,ImageStat
    from backend.services.studio import title_art,render
    raw=root/'raw';raw.mkdir()
    source=raw/'input.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=0x404040:s=320x180:r=30:d=1','-y',str(source)],check=True)
    d=Draft(id=style,title=style,hook='CAN YOU\nESCAPE?',title_style=style,title_template_version=version,title_motion=False,aspect='portrait',layout='crop',subtitles=False,original_audio=False,scenes=[Scene(id='s',start=0,end=.7)])
    layer=Image.open(io.BytesIO(title_art.png_bytes(d.hook,style,1080,1920,version=version)))
    box=layer.getbbox()
    assert box and box[0]>=1080*.04 and box[2]<=1080*.96 and box[3]<1920*.5
    expected=Image.new('RGBA',(1080,1920),(64,64,64,255));expected.alpha_composite(layer)
    render.render_draft('p1',source,d,style,lambda _:None)
    output=root/'output/studio'/f'{style}.mp4'
    png=subprocess.check_output(['ffmpeg','-v','error','-ss','0.3','-i',str(output),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
    actual=Image.open(io.BytesIO(png)).convert('RGB')
    diff=ImageChops.difference(actual.crop(box),expected.convert('RGB').crop(box))
    assert max(ImageStat.Stat(diff).mean)<8  # Allows H.264 color conversion, not layout drift.


def test_title_preview_api_does_not_mutate_draft_or_call_model(client,monkeypatch):
    from PIL import Image
    import io
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Preview'}).json()
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k: pytest.fail('preview must not invoke a model'))
    body={**d,'hook':'追兵就在身后！','title_style':'comic','aspect':'portrait','title_accent':'#ff6633'}
    response=client.post('/studio/p1/title-preview',json=body)
    assert response.status_code==200 and response.headers['content-type']=='image/png'
    assert Image.open(io.BytesIO(response.content)).size==(1080,1920)
    assert store.read('p1')['drafts'][0]['hook']==''
    saved=client.put('/studio/p1/drafts/'+d['id'],json=body).json()
    assert saved['title_style']=='comic' and saved['title_accent']=='#ff6633'
    assert client.post('/studio/p1/title-preview',json={**body,'title_accent':'bad'}).status_code==422
    assert client.post('/studio/missing/title-preview',json=body).status_code==404


def test_artwork_cjk_manual_breaks_and_limits():
    from backend.services.studio import title_art
    for text in ['追兵就在身後！','逃げ切れる？','100% {escape}: Go!']:
        assert title_art.artwork(text,'neon',1080,1920).getbbox()
    font=title_art.font_for('CAN YOU',120)
    assert title_art.lines_for('CAN YOU\nESCAPE?',font,800)==['CAN YOU','ESCAPE?']
    with pytest.raises(ValueError,match='太长'):
        title_art.artwork('a\nb\nc\nd','comic',1080,1920)
    with pytest.raises(ValueError,match='像素'):
        title_art.artwork('Hi','comic',20000,20000)


def test_title_thumbnail_is_packaged_style_and_rejects_unknown(client):
    from PIL import Image
    import io
    r=client.get('/studio/title-presets/arena/thumbnail')
    assert r.status_code==200 and Image.open(io.BytesIO(r.content)).size==(324,174)
    assert 'max-age' in r.headers['cache-control']
    assert client.get('/studio/title-presets/unknown/thumbnail').status_code==422


def decoded_audio(path):
    from array import array
    values=array('f')
    values.frombytes(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','48000','-f','f32le','-']))
    return values


def audio_rms(values,start,end):
    import math
    samples=values[round(start*48000):round(end*48000)]
    return math.sqrt(sum(v*v for v in samples)/max(1,len(samples)))


def test_short_audio_reordered_after_silent_interval_is_preserved(root):
    from backend.services.studio.render import render_draft
    video=root/'short-audio.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=3','-f','lavfi','-i','sine=frequency=431:sample_rate=48000:duration=0.6','-y',str(video)],check=True)
    d=Draft(id='short-audio',title='Short audio',subtitles=False,scenes=[Scene(id='late',start=2,end=2.5),Scene(id='early',start=.1,end=.6)])
    render_draft('p1',video,d,'short-audio',lambda _:None)
    values=decoded_audio(root/'output/studio/short-audio.mp4')
    assert audio_rms(values,.1,.4)<.001
    assert audio_rms(values,.6,.9)>.02
    assert abs(len(values)/48000-1)<.025


def test_many_cuts_have_short_fades_and_aligned_audio_video(root,source):
    from backend.services.studio.render import render_draft
    d=Draft(id='cuts',title='Cuts',subtitles=False,scenes=[Scene(id=f's{i}',start=.23+(i%2)*.51,end=.73+(i%2)*.51) for i in range(12)])
    render_draft('p1',source,d,'cuts',lambda _:None)
    path=root/'output/studio/cuts.mp4'
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(path)]))['streams']
    assert {s['codec_type'] for s in streams}=={'audio','video'}
    assert all(abs(float(s['start_time']))<.002 for s in streams)
    assert all(abs(float(s['duration'])-6)<1/30 for s in streams)
    values=decoded_audio(path)
    middle=audio_rms(values,.15,.35)
    assert middle>.02
    for i in range(1,12):
        assert audio_rms(values,i*.5-.001,i*.5+.001)<middle*.3
    assert audio_rms(values,0,.001)<middle*.3
    assert audio_rms(values,5.999,6)<middle*.3


def test_delayed_source_audio_keeps_its_initial_silence(root):
    from backend.services.studio.render import render_draft
    video=root/'delayed-audio.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=2','-itsoffset','0.5','-f','lavfi','-i','sine=frequency=431:sample_rate=48000:duration=0.7','-y',str(video)],check=True)
    d=Draft(id='delay',title='Delay',subtitles=False,scenes=[Scene(id='s',start=0,end=1.5)])
    render_draft('p1',video,d,'delay',lambda _:None)
    values=decoded_audio(root/'output/studio/delay.mp4')
    assert audio_rms(values,.05,.35)<.001
    assert audio_rms(values,.6,1)>.02


def test_video_without_audio_stays_silent_and_reports_it(root):
    from backend.services.studio.render import render_draft
    video=root/'silent.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=blue:s=320x180:r=30:d=1','-y',str(video)],check=True)
    d=Draft(id='silent',title='Silent',subtitles=False,scenes=[Scene(id='s',start=0,end=.5)])
    result=render_draft('p1',video,d,'silent',lambda _:None)
    assert result['warnings']==['原素材没有音轨，本次导出无声']
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(root/'output/studio/silent.mp4')]))['streams']
    assert [s['codec_type'] for s in streams]==['video']


@pytest.mark.parametrize('style', ['comic','neon','arena','editorial'])
def test_v2_title_languages_and_safety_bounds(style):
    from backend.services.studio import title_art
    for text in ['CAN YOU\nESCAPE?', '你能逃出\n这里吗？', '逃げ切れる？', 'A longer challenge with several words!', '100% {escape}: Go!']:
        for w,h in [(1080,1920),(1920,1080)]:
            art=title_art.artwork(text,style,w,h,version=2)
            x0,y0,x1,y1=art.getbbox()
            assert x0>=w*.04 and x1<=w*.98
            assert y0>=h*.035 and y1<h*.4
    with pytest.raises(ValueError,match='太长'):
        title_art.artwork('a\nb\nc\nd',style,1080,1920,version=2)


def test_title_versions_persist_and_have_distinct_previews(client):
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Version'}).json()
    assert d['title_template_version']==1
    body={**d,'hook':'CAN YOU\nESCAPE?','title_style':'comic','aspect':'portrait'}
    old=client.post('/studio/p1/title-preview',json=body)
    new=client.post('/studio/p1/title-preview',json={**body,'title_template_version':2})
    assert old.status_code==new.status_code==200 and old.content!=new.content
    for version in (6,5,4,3,2,1):
        body={**body,'title_template_version':version}
        saved=client.put('/studio/p1/drafts/'+d['id'],json=body).json()
        assert saved['title_template_version']==version
        body=saved
    assert client.post('/studio/p1/title-preview',json={**body,'title_style':'editorial'}).status_code==422
    assert client.post('/studio/p1/title-preview',json={**body,'title_template_version':7}).status_code==422
    for style in ['comic','neon','arena','editorial']:
        assert client.get('/studio/title-presets/'+style+'/thumbnail?v=2').status_code==200
    assert client.get('/studio/title-presets/comic/thumbnail?v=4').status_code==200


@pytest.mark.parametrize('style', ['comic','neon','arena','editorial','pixel','frosted'])
def test_v3_multilingual_bounds_and_thumbnails(client,style):
    from backend.services.studio import title_art
    for text in ['CAN YOU\nESCAPE?', '你能逃出\n这里吗？', '逃げ切れる？']:
        for w,h in [(1080,1920),(1920,1080)]:
            layer=title_art.artwork(text,style,w,h,version=3)
            box=layer.getbbox()
            assert box and box[0]>=0 and box[2]<=w and box[3]<h*.5
    assert client.get('/studio/title-presets/'+style+'/thumbnail?v=3').status_code==200
    if style in ('pixel','frosted'):
        with pytest.raises(ValidationError):draft(title_style=style,title_template_version=2)


@pytest.mark.parametrize('version', [3,6])
def test_frosted_preview_mask_matches_art_and_does_not_call_model(client,monkeypatch,version):
    import io
    from PIL import Image
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Glass'}).json()
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k:pytest.fail('No provider calls'))
    body={**d,'hook':'CAN YOU\nESCAPE?','title_style':'frosted','title_template_version':version,'aspect':'portrait'}
    responses=[client.post('/studio/p1/title-preview?layer='+layer,json=body) for layer in ('artwork','backdrop')]
    assert all(r.status_code==200 for r in responses)
    images=[Image.open(io.BytesIO(r.content)) for r in responses]
    assert images[0].getbbox()==images[1].getbbox()
    assert client.post('/studio/p1/title-preview?layer=backdrop',json={**body,'title_style':'comic'}).status_code==422
    assert store.read('p1')['drafts'][0]['title_style']=='plain'


def test_pixel_uses_exact_grid_and_gloss_changes_face():
    from backend.services.studio import title_art
    from PIL import ImageChops
    pixel=title_art.artwork('CAN YOU\nESCAPE?','pixel',1080,1920,version=3)
    # Nearest-neighbor typography keeps a small discrete palette, no smoothed edges.
    assert len(pixel.getcolors(10000))<200
    old=title_art.artwork('CAN YOU\nESCAPE?','comic',1080,1920,version=2)
    new=title_art.artwork('CAN YOU\nESCAPE?','comic',1080,1920,version=3)
    assert old.getbbox()==new.getbbox()
    assert ImageChops.difference(old.convert('RGB'),new.convert('RGB')).getbbox()


@pytest.mark.parametrize('version', [3,6])
def test_frosted_blurs_moving_background_only_inside_card_and_expires(root,version):
    import io
    from PIL import Image,ImageChops,ImageStat
    from backend.services.studio.render import render_draft
    source=root/'checker.mp4'
    filters="color=white:s=320x180:r=30:d=5,drawgrid=width=8:height=8:thickness=4:color=black,drawbox=color=red@0.4:t=fill:enable='lt(t,2)',drawbox=color=blue@0.4:t=fill:enable='gte(t,2)'"
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',filters,'-c:v','libx264','-y',str(source)],check=True)
    d=Draft(id='glass',title='Glass',hook='HI',title_style='frosted',title_template_version=version,subtitles=False,original_audio=False,title_motion=False,scenes=[Scene(id='s',start=0,end=5)])
    render_draft('p1',source,d,'glass',lambda _:None)
    def frame(path,t):
        data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
        return Image.open(io.BytesIO(data)).convert('RGB')
    out=root/'output/studio/glass.mp4'
    means=[]
    for t in (.5,2.5):
        original=frame(source,t);actual=frame(out,t)
        box=(195,22,230,38)  # Empty card area, away from label and border.
        assert max(ImageStat.Stat(actual.crop(box)).stddev)<max(ImageStat.Stat(original.crop(box)).stddev)*.3
        assert max(ImageStat.Stat(ImageChops.difference(actual.crop((0,90,320,180)),original.crop((0,90,320,180)))).mean)<8
        means.append(ImageStat.Stat(actual.crop(box)).mean)
    assert means[0][0]>means[1][0]+10 and means[1][2]>means[0][2]+10
    # Title and blur both disappear at the same 4-second boundary.
    assert max(ImageStat.Stat(ImageChops.difference(frame(out,4.5),frame(source,4.5))).mean)<8


@pytest.mark.parametrize('version', [3,6])
def test_frosted_keeps_moving_source_frames_in_sync(root,source,version):
    import io
    from PIL import Image,ImageChops,ImageStat
    from backend.services.studio.render import render_draft
    base=Draft(id='sync',title='Sync',subtitles=False,original_audio=False,scenes=[Scene(id='s',start=.2,end=2.7)])
    render_draft('p1',source,base,'control',lambda _:None)
    glass=base.model_copy(update={'hook':'HI','title_style':'frosted','title_template_version':version})
    render_draft('p1',source,glass,'glass-sync',lambda _:None)
    def frame(name,t):
        path=root/'output/studio'/f'{name}.mp4'
        png=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
        return Image.open(io.BytesIO(png)).convert('RGB').crop((0,90,320,180))
    for t in (.5,1,2):
        assert max(ImageStat.Stat(ImageChops.difference(frame('control',t),frame('glass-sync',t))).mean)<8


@pytest.mark.parametrize('version', [4,5])
def test_comic_v4_bounds_and_version_isolation(version):
    from backend.services.studio.title_art import artwork
    for text in ['CAN YOU\nESCAPE?', '你能逃出\n这里吗？', '逃げ切れる？', 'A']:
        for w,h in [(1080,1920),(1920,1080),(320,180)]:
            for scale,y in [(.75,.06),(1.2,.70)]:
                box=artwork(text,'comic',w,h,scale=scale,y=y,version=version).getbbox()
                assert box and box[0]>=w*.04 and box[2]<=w*.96
                assert box[1]>=h*.035 and box[3]<=h*.91
    for style in ['neon','arena','editorial','pixel','frosted','plain']:
        with pytest.raises(ValidationError):draft(title_style=style,title_template_version=version)
    with pytest.raises(ValueError,match='太长'):
        artwork('a\nb\nc\nd','comic',1080,1920,version=version)


@pytest.mark.parametrize('style',['comic','neon','arena','pixel','editorial','frosted'])
def test_v6_multilingual_layout_and_saved_preview(client,style):
    from backend.services.studio.title_art import artwork
    for text in ['CAN YOU\nESCAPE?','你能逃出\n这里吗？','逃げ切れる？']:
        for w,h in [(720,1280),(1280,720)]:
            image=artwork(text,style,w,h,version=6,scale=1.2,y=.7)
            x0,y0,x1,y1=image.getbbox()
            assert 0<=x0<x1<=w and h*.035<=y0<y1<=h*.91
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'Typography'}).json()
    body={**d,'hook':'CAN YOU\nESCAPE?','title_style':style,'title_template_version':6,'aspect':'portrait'}
    saved=client.put('/studio/p1/drafts/'+d['id'],json=body)
    assert saved.status_code==200 and saved.json()['title_template_version']==6
    assert client.post('/studio/p1/title-preview',json=saved.json()).status_code==200
    assert client.get('/studio/title-presets/'+style+'/thumbnail?v=6').status_code==200
    with pytest.raises(ValueError,match='太长'):
        artwork('a\nb\nc\nd',style,1080,1920,version=6)


def test_v6_preserves_accepted_comic_and_pixel_palette():
    from backend.services.studio.title_art import artwork
    for text in ['CAN YOU\nESCAPE?','你能逃出\n这里吗？']:
        assert artwork(text,'comic',720,1280,version=6).tobytes()==artwork(text,'comic',720,1280,version=5).tobytes()
    pixel=artwork('CAN YOU\nESCAPE?','pixel',1080,1920,version=6)
    assert len(pixel.getcolors(10000))<30
    for style in ['plain','impact','card']:
        with pytest.raises(ValidationError):draft(title_style=style,title_template_version=6)


def test_thumbnail_is_real_jpeg_and_preserves_draft(client, root):
    import io
    from PIL import Image
    from backend.services.studio import thumbnails
    d = store.save_draft('p1', draft(), create=True)
    before = store.read('p1')
    response = client.get(f"/studio/p1/drafts/{d['id']}/thumbnail", params={'revision': 1})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/jpeg'
    with Image.open(io.BytesIO(response.content)) as frame:
        assert max(frame.size) <= 640
    hits = thumbnails._frame.cache_info().hits
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1").content == response.content
    assert thumbnails._frame.cache_info().hits == hits + 1
    assert store.read('p1') == before
    from backend.services.studio import jobs
    import os
    video = jobs.source('p1')
    stat = video.stat()
    os.utime(video, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    misses = thumbnails._frame.cache_info().misses
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1").status_code == 200
    assert thumbnails._frame.cache_info().misses == misses + 1
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=2").status_code == 409
    assert client.get(f"/studio/missing/drafts/{d['id']}/thumbnail?revision=1").status_code == 404
    assert client.get('/studio/p1/drafts/missing/thumbnail?revision=1').status_code == 404
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1&job_id=../outside").status_code == 422


def test_thumbnail_rejects_unfinished_or_wrong_revision_export(client, root):
    d = store.save_draft('p1', draft(), create=True)
    jid = 'a' * 32
    state = store.read('p1')
    state['jobs'] = [{'job_id':jid,'draft_id':d['id'],'revision':1,'status':'failed'}]
    store.write('p1', state)
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1&job_id={jid}").status_code == 404
    state['jobs'][0].update(status='completed', revision=2)
    store.write('p1', state)
    assert client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1&job_id={jid}").status_code == 404


def test_thumbnail_output_uses_scoped_file_not_result_path(client, root, source):
    import io
    from PIL import Image
    d = store.save_draft('p1', draft(), create=True)
    jid = 'b' * 32
    output = root / 'output' / 'studio' / f'{jid}.mp4'
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    state = store.read('p1')
    state['jobs'] = [{'job_id':jid,'draft_id':d['id'],'revision':1,'status':'completed','result':{'path':'/outside/private.mp4'}}]
    store.write('p1', state)
    response = client.get(f"/studio/p1/drafts/{d['id']}/thumbnail?revision=1&job_id={jid}")
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as frame:
        assert max(frame.size) <= 640


def test_thumbnail_failure_does_not_cache_empty_frame(monkeypatch):
    from backend.services.studio import thumbnails
    thumbnails._frame.cache_clear()
    monkeypatch.setattr(thumbnails.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess([], 0, b'', b''))
    with pytest.raises(ValueError, match='缩略图'):
        thumbnails._frame('/unused', 1, 1, 0)
    assert thumbnails._frame.cache_info().currsize == 0


def test_legacy_editor_resumes_saved_edits_without_creating_duplicates(client, root):
    request = {'clip_ids':['c1','c2'], 'title':'Original', 'reuse_existing':True}
    first = client.post('/studio/p1/drafts',json=request).json()
    edited = client.put('/studio/p1/drafts/'+first['id'],json={**first,'hook':'Saved opening','scenes':first['scenes'][:1]}).json()
    again = client.post('/studio/p1/drafts',json=request).json()
    assert again['id'] == edited['id'] and again['revision'] == 2
    assert again['hook'] == 'Saved opening' and len(again['scenes']) == 1
    assert len(store.read('p1')['drafts']) == 1
    separate = client.post('/studio/p1/drafts',json={**request,'reuse_existing':False}).json()
    assert separate['id'] != first['id']
    assert client.post('/studio/p1/drafts',json=request).json()['id'] == first['id']
    reordered = client.post('/studio/p1/drafts',json={**request,'clip_ids':['c2','c1']}).json()
    assert reordered['id'] not in (first['id'],separate['id'])
    assert client.post('/studio/p1/drafts',json={**request,'clip_ids':['other-project-clip']}).status_code == 404


def test_concurrent_legacy_editor_open_creates_one_draft(root):
    from concurrent.futures import ThreadPoolExecutor
    import uuid
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _:store.open_legacy_editor('p1',draft().model_copy(update={'id':uuid.uuid4().hex}),'same-source',reuse_existing=True),range(6)))
    assert len({d['id'] for d in results}) == 1
    assert len(store.read('p1')['drafts']) == 1


def test_export_dispatch_failure_is_retryable_and_preserves_success(root, monkeypatch):
    from backend.services.studio import jobs
    saved = store.save_draft('p1', draft(), create=True)
    output = root / 'prior.mp4'
    output.write_bytes(b'previous export')
    previous = {'job_id':'success', 'status':'completed', 'draft_id':'d1', 'revision':1, 'result':{'path':str(output)}}
    store.change('p1', lambda data: data['jobs'].append(previous))
    calls = []
    class Executor:
        def submit(self, *args):
            calls.append(args)
            if len(calls) == 1:
                raise RuntimeError('executor unavailable: private runtime details')
    monkeypatch.setattr(jobs, 'executor', Executor())
    with pytest.raises(ValueError, match='导出任务未能启动'):
        jobs.export('p1', Draft.model_validate(saved))
    state = store.read('p1')
    failed = state['jobs'][0]
    assert failed['status'] == 'failed'
    assert 'private runtime' not in failed['error']
    assert state['jobs'][1] == previous
    assert state['drafts'][0] == saved
    assert output.read_bytes() == b'previous export'
    retry = jobs.export('p1', Draft.model_validate(saved))
    assert retry['status'] == 'queued'
    assert retry['job_id'] != failed['job_id']
    assert jobs.export('p1', Draft.model_validate(saved))['job_id'] == retry['job_id']
    assert len(calls) == 2  # retry accepted once; duplicate does not dispatch again
    assert len(store.read('p1')['jobs']) == 3


def test_cta_preview_api_uses_shared_plan_without_mutating_or_calling_models(client,monkeypatch):
    from backend.services.studio import cta
    d=client.post('/studio/p1/drafts',json={'clip_ids':['c1'],'title':'CTA preview'}).json()
    monkeypatch.setattr(intelligence,'vision_call',lambda *a,**k: pytest.fail('CTA must not invoke a model'))
    monkeypatch.setattr(intelligence,'text_json',lambda *a,**k: pytest.fail('CTA must not invoke a model'))
    body={**d,'cta':{'template':'auto','language':'en'},'aspect':'portrait'}
    response=client.post('/studio/p1/cta-preview',json=body)
    assert response.status_code==200
    expected=cta.plan(Draft.model_validate(body))
    assert response.json()['template']==expected['template']
    assert response.json()['duration']==expected['duration']
    assert response.json()['image'].startswith('data:image/png;base64,')
    assert store.read('p1')['drafts'][0]['cta']['template']=='off'
    assert client.post('/studio/missing/cta-preview',json=body).status_code==404
    assert client.post('/studio/p1/cta-preview',json={**body,'cta':{'template':'unknown'}}).status_code==422
