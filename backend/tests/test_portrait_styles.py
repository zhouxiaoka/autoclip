"""Visual template selection cannot change platform language or mix language caches."""
import re
import pytest

from backend.tests.test_studio import root, source, client  # noqa: F401
from backend.services.studio import jobs, store, packaging, packaging_render
from backend.services.studio.models import ImportOptions, Packaging, PackagingCue, Scene
from backend.services.studio.caption_layout import width


def select(style):
    store.write('p1', {'generation':{'portrait_style':style},'drafts':[],'jobs':[],'output_variants':[]})


@pytest.mark.parametrize('style,platform,template,language', [
    ('auto','douyin','interview_zh','zh'), ('auto','tiktok','podcast_en','en'),
    ('podcast','douyin','podcast_en','zh'), ('interview','tiktok','interview_zh','en'),
    ('podcast','bilibili','landscape','zh'), ('interview','youtube_long','landscape','en')])
def test_choice_changes_only_vertical_template(root, style, platform, template, language):
    select(style)
    strategy = jobs._project_strategy('p1', platform)
    assert (strategy.template, strategy.audience_language) == (template, language)
    assert (strategy.width,strategy.height) == ((1920,1080) if template=='landscape' else (1080,1920))
    assert jobs._project_strategy('p1','youtube_shorts').max_duration_sec == 180


def test_import_endpoint_persists_the_user_choice(client, source, monkeypatch):
    def inspect(pid, options, *args):
        store.write(pid, {'generation':{'portrait_style':options.portrait_style,'status':'screening'},'jobs':[],'drafts':[]})
    monkeypatch.setattr(jobs,'inspect_project',inspect)
    response=client.post('/studio/import',data={'auto_start':'true','platforms':'douyin','portrait_style':'podcast'},
                         files={'video':('demo.mp4',source.read_bytes(),'video/mp4')})
    assert response.status_code==200,response.text
    assert store.read(response.json()['project_id'])['generation']['portrait_style']=='podcast'
    assert ImportOptions().portrait_style=='auto'


def test_framing_uses_the_selected_window(root, monkeypatch):
    calls=[]
    monkeypatch.setattr(jobs,'_speaker_framing',lambda *args,**kwargs:calls.append(kwargs['window']) or (None,'full_frame'))
    value={'scenes':[{'start':0,'end':10}]}
    select('interview')
    interview,_=jobs._apply_framing('p1',value,'tiktok',None,False,{})
    select('podcast')
    podcast,_=jobs._apply_framing('p1',value,'douyin',None,False,{})
    assert calls==[jobs.INTERVIEW_WINDOW,None]
    assert interview['layout']=='window' and podcast['layout']=='blur'


def test_same_template_cache_keeps_chinese_and_english_separate(root, monkeypatch):
    select('podcast')
    calls=[]
    def build(value,lines,strategy,**kw):
        calls.append(strategy.audience_language)
        return {'template':strategy.template,'audience_language':strategy.audience_language}
    monkeypatch.setattr(packaging,'build_packaging',build)
    cache={'entries':[],'names':''}
    value={'scenes':[{'start':0,'end':10}]}
    jobs._prefetch_packaging('p1',[('douyin',value),('tiktok',value),('xiaohongshu',value)],False,cache)
    assert sorted(calls)==['en','zh']
    assert jobs._apply_packaging('p1',value,'douyin',False,cache)['packaging']['audience_language']=='zh'
    assert jobs._apply_packaging('p1',value,'tiktok',False,cache)['packaging']['audience_language']=='en'


def test_english_interview_filters_chinese_tags_and_nameplate_roles(root):
    select('interview')
    strategy=jobs._project_strategy('p1','tiktok')
    lines=[{'start':0,'end':3,'text':'优秀的投资人让创始人自己飞翔'}]
    response={'title_lines':['Let founders fly'],'segments':[{'from':0,'to':0,'text':'Great investors let founders fly.'}],
              'speakers':[{'line':0,'name':'Sam','role':'首席执行官'}],'tags':[{'line':0,'text':'飞行教练'}]}
    result=packaging.build_packaging({'title':'Sam'},lines,strategy,known_names='Sam',call=lambda *_:response)
    assert result['template']=='interview_zh' and result['audience_language']=='en'
    assert not result['tags'] and result['speakers'][0]['role']==''
    assert all(not packaging.foreign_for('en',cue['text']) for cue in result['cues'])


@pytest.mark.parametrize('style',['pop','boxed','cinematic'])
def test_chinese_podcast_captions_and_hook_fit_two_lines(style):
    text='这是一段完整的中文观点，播客满屏字幕必须分页，不能把整段中文当作一个英文单词显示。'*4
    model=Packaging(template='podcast_en',audience_language='zh',style=style,
                    title_lines=['这是第一行中文标题','这是第二行中文标题'],cues=[PackagingCue(start=0,end=20,text=text)])
    ass=packaging_render.scene_ass(model,[Scene(id='s1',start=0,end=20)],0)
    captions=[line.split(',',9)[9] for line in ass.splitlines() if line.startswith('Dialogue: 2,')]
    assert len(captions)>5
    for caption in captions:
        caption=re.sub(r'\{[^}]*\}','',caption)
        assert len(caption.split('\\N'))<=2
        assert all(width(row)<=packaging_render._limit({'pop':82,'boxed':58,'cinematic':64}[style])/.95+1e-6 for row in caption.split('\\N'))
    assert '这是第一行中文标题\\N这是第二行中文标题' in ass


def test_long_source_paragraph_is_paginated_before_packaging_scene_cuts():
    text=' '.join(f'word{i:03}' for i in range(200))
    entries=[{'start_time':'00:00:00,000','end_time':'00:01:40,000','text':text}]
    lines=packaging.draft_lines(entries,[{'start':40,'end':60}])
    assert lines and all(40<=row['start']<row['end']<=60 and len(row['text'])<=600 for row in lines)
    assert 'word000' not in ' '.join(row['text'] for row in lines) and 'word199' not in ' '.join(row['text'] for row in lines)


@pytest.mark.parametrize('template,style',[('interview_zh','classic'),('podcast_en','boxed'),('podcast_en','pop')])
def test_editor_scene_cut_keeps_overlapping_caption_without_replaying_earlier_words(template, style):
    text=' '.join(f'word{i:03}' for i in range(120))
    model=Packaging(template=template,audience_language='en',style=style,
                    cues=[PackagingCue(start=0,end=120,text=text[:599])])
    scene=Scene(id='s1',start=50,end=70)
    ass=packaging_render.scene_ass(model,[scene],0)
    captions=[line for line in ass.splitlines() if line.startswith('Dialogue: 2,')]
    assert captions and 'word000' not in '\n'.join(captions)
    assert all(float(line.split(',')[1].split(':')[-1])<20 for line in captions)
