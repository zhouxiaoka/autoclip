import json
import subprocess
import pytest
from pydantic import ValidationError
from backend.services.studio.models import Draft, Scene, CTA
from backend.services.studio import cta, store
from backend.services.studio.render import render_draft
from backend.services.publish_export import _probe
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path


def draft(**kwargs):
    return Draft(id='d1',title='CTA test',scenes=[Scene(id='s1',start=0,end=9)],subtitles=False,**kwargs)


def test_legacy_off_and_time_based_recommendation():
    assert cta.plan(draft())['template']=='off'
    assert cta.plan(draft(cta=CTA(template='auto')))['template']=='continue'
    short=draft(cta=CTA(template='auto'))
    short.scenes[0].end=2
    assert cta.plan(short)['template']=='brand'
    assert cta.plan(short)['duration']==4.5


def test_challenge_confirmation_is_bound_to_last_interval():
    d=draft(cta=CTA(template='challenge'))
    assert cta.plan(d)['template']=='brand'
    d.cta.confirmed_scene=cta.scene_key(d.scenes[-1])
    assert cta.plan(d)['template']=='challenge'
    d.scenes[-1].end=8
    assert cta.plan(d)['template']=='brand'


def test_copy_no_model_translation_or_brand_invention():
    d=draft(cta=CTA(template='brand',language='en'))
    assert cta.plan(d)['brand']==''
    assert cta.plan(d)['text']=='Start your adventure'
    d.cta.text="100% user's choice: [play]"
    assert cta.plan(d)['text']==d.cta.text
    assert cta.png_bytes(cta.plan(d),320,180).startswith(b'\x89PNG')
    for language in ('zh','en','ja'):
        d.cta.language=language; d.cta.text=''
        assert cta.png_bytes(cta.plan(d),180,320).startswith(b'\x89PNG')


@pytest.mark.parametrize('values',[{'template':'playable'},{'version':2},{'position':float('nan')},{'text':'a'*81}])
def test_reject_invalid_configuration(values):
    with pytest.raises(ValidationError): CTA(**values)


def test_save_revision_and_immutable_snapshot(tmp_path,monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR',str(tmp_path))
    store.directory('p1').mkdir(parents=True)
    original=store.save_draft('p1',draft(),create=True)
    edited=Draft.model_validate(original)
    edited.cta=CTA(template='brand',brand='Test game')
    saved=store.save_draft('p1',edited)
    assert saved['revision']==2 and saved['cta']['brand']=='Test game'
    assert original['cta']['template']=='off'


@pytest.mark.parametrize('kind,with_audio',[('off',False),('continue',True),('brand',True),('challenge',False)])
def test_actual_render_preserves_body_and_appends_only_when_needed(tmp_path,monkeypatch,kind,with_audio):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR',str(tmp_path/'data'))
    source=tmp_path/'source.mp4'
    cmd=[get_ffmpeg_path(),'-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=30:d=9']
    if with_audio: cmd+=['-f','lavfi','-i','sine=frequency=440:duration=9']
    cmd+=['-c:v','libx264','-pix_fmt','yuv420p','-t','9','-y',str(source)]
    subprocess.run(cmd,check=True,capture_output=True)
    d=draft(cta=CTA(template=kind,language='en'))
    d.cta.confirmed_scene=cta.scene_key(d.scenes[-1])
    result=render_draft('p1',source,d,'render',lambda _:None)
    expected=11.5 if kind in ('brand','challenge') else 9
    assert abs(result['duration']-expected)<.1
    output=store.directory('p1')/'output/studio/render.mp4'
    assert _probe(output)['width']==320
    subprocess.run([get_ffmpeg_path(),'-v','error','-i',str(output),'-f','null','-'],check=True,capture_output=True)
    streams=json.loads(subprocess.check_output([get_ffprobe_path(),'-v','error','-show_streams','-of','json',str(output)]))['streams']
    assert any(s['codec_type']=='audio' for s in streams)==with_audio
    if with_audio:
        assert abs(float(next(s for s in streams if s['codec_type']=='audio')['duration'])-expected)<.1
    # Overlay does not replace the body: the first frame remains the original red.
    raw=subprocess.check_output([get_ffmpeg_path(),'-v','error','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    assert raw[0]>220 and raw[1]<25
    if kind=='brand':
        tail=subprocess.check_output([get_ffmpeg_path(),'-v','error','-ss','10','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        assert 60 < tail[0] < 160  # Dimmed actual source behind the framed gameplay tile.
        from PIL import Image, ImageChops, ImageStat
        from backend.services.studio.cta_materials import frame
        expected_image=cta.artwork(cta.plan(d),320,180,frame(source,d)).convert('RGB')
        actual_image=Image.frombytes('RGB',(320,180),tail)
        assert max(ImageStat.Stat(ImageChops.difference(expected_image,actual_image)).mean)<8


def test_styles_survive_save_and_preview_export_plan(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR',str(tmp_path))
    store.directory('styles').mkdir(parents=True)
    images=[]
    for style in ('glossy','soft','tactical','type'):
        d=draft(cta=CTA(template='continue',style=style,accent='#d37425',text='PLAY NOW'))
        d.id=style
        saved=store.save_draft('styles',d,create=True)
        spec=cta.plan(Draft.model_validate(saved))
        assert spec['style']==style and spec['accent']=='#d37425'
        images.append(cta.png_bytes(spec,320,180))
    assert len(set(images))==4
    assert CTA.model_validate({'template':'continue'}).style=='glossy'
    with pytest.raises(ValidationError): CTA(style='unknown')
    with pytest.raises(ValidationError): CTA(accent='red;invalid')


def test_type_style_has_no_button_plate():
    from backend.services.studio.cta_materials import styled_button
    image=styled_button('PLAY',320,90,'type')
    assert image.getpixel((20,45))[3]==0
    assert styled_button('PLAY',320,90,'soft').getpixel((20,45))[3]>0
