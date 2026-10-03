"""ASS packaging layer and the interview window layout (synthetic media, no model calls)."""
import re
import subprocess

import pytest
from PIL import Image

from backend.services.studio import packaging_render as pr
from backend.services.studio.models import Draft, Packaging, Scene


def _packaging(**overrides):
    body = {
        'template': 'interview_zh', 'audience_language': 'zh', 'source_language': 'en',
        'title_lines': ['好的投资人', '应该像飞行教练'], 'title_accent_line': 1,
        'cues': [{'start': 10.0, 'end': 12.0, 'text': '第一句', 'original': 'first line'},
                 {'start': 30.0, 'end': 32.0, 'text': '第二句', 'original': 'second line'}],
        'speakers': [{'at': 10.0, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}],
        'tags': [{'at': 30.2, 'text': '飞行教练'}],
    }
    return Packaging.model_validate({**body, **overrides})


SCENES = [Scene(id='a', label='a', start=10, end=13), Scene(id='b', label='b', start=30, end=33)]


def _dialogues(text):
    return [line for line in text.splitlines() if line.startswith('Dialogue:')]


def test_events_are_clipped_to_each_scene_on_its_own_clock():
    first, second = pr.scene_ass(_packaging(), SCENES, 0), pr.scene_ass(_packaging(), SCENES, 1)
    assert any('第一句' in line and ',0:00:00.00,0:00:02.00,' in line for line in _dialogues(first))
    assert not any('第二句' in line for line in _dialogues(first))
    assert any('第二句' in line and ',0:00:00.00,0:00:02.00,' in line for line in _dialogues(second))
    assert all('应该像飞行教练' in ''.join(_dialogues(doc)) for doc in (first, second))  # title stays pinned


def test_nameplate_appears_once_where_the_speaker_first_talks():
    first, second = pr.scene_ass(_packaging(), SCENES, 0), pr.scene_ass(_packaging(), SCENES, 1)
    assert sum('Sam Altman' in line for line in _dialogues(first)) == 1
    assert not any('Sam Altman' in line for line in _dialogues(second))
    plate = next(line for line in _dialogues(first) if 'Sam Altman' in line)
    assert 'PlateName' in plate and '\\an7' in plate  # left-anchored lower third, not over the face


def test_tags_can_be_switched_off_and_burned_sources_have_no_caption_layer():
    doc = pr.scene_ass(_packaging(tags_enabled=False), SCENES, 1)
    assert not any('Tag' in line.split(',')[3] for line in _dialogues(doc))
    burned = pr.scene_ass(_packaging(cues=[], burned_captions=True), SCENES, 0)
    assert not any(line.split(',')[3] in ('Caption', 'Original') for line in _dialogues(burned))


def test_podcast_captions_show_at_most_three_words_with_the_active_word_highlighted():
    podcast = _packaging(template='podcast_en', audience_language='en', title_lines=['Great investors'],
                         cues=[{'start': 10.0, 'end': 12.0, 'text': 'a good investor is a flight instructor', 'original': ''}], tags=[])
    words = [line for line in _dialogues(pr.scene_ass(podcast, SCENES, 0)) if ',Words,' in line]
    assert words
    for line in words:
        visible = re.sub(r'\{[^}]*\}', ' ', line.split(',,0,0,0,,', 1)[1]).split()
        assert len(visible) <= 3
    assert all(pr.ACCENT in line for line in words)


LONG = '这些年把同样的能量，带给了无数创始人，而且这种手把手的方式一直延续到今天，影响了整整一代人'


@pytest.mark.parametrize('template, style', [('interview_zh', 'classic'), ('interview_zh', 'boxed'), ('interview_zh', 'spotlight'),
                                             ('podcast_en', 'pop'), ('podcast_en', 'boxed'), ('podcast_en', 'cinematic')])
def test_every_style_keeps_captions_within_two_lines_and_renders(tmp_path, template, style):
    interview = template == 'interview_zh'
    text = LONG if interview else 'and brought exactly the same energy to a great many YC founders over the years, and that shaped a generation'
    packaging = _packaging(template=template, audience_language='zh' if interview else 'en', style=style,
                           title_lines=['好的投资人', '应该像飞行教练'] if interview else ['Great investors'],
                           cues=[{'start': 0.2, 'end': 2.8, 'text': text, 'original': 'the original English line that is fairly long as well' if interview else ''}],
                           speakers=[{'at': 0.2, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}],
                           tags=[{'at': 0.5, 'text': '手把手'}] if interview else [], highlights=[] if interview else [{'at': 0.2, 'text': 'energy'}])
    doc = pr.scene_ass(packaging, [Scene(id='a', label='a', start=0, end=3)], 0)
    for line in _dialogues(doc):
        name = line.split(',')[3]
        if name in ('Caption', 'CaptionBox', 'Original'):
            body = re.sub(r'\{[^}]*\}', '', line.split(',,0,0,0,,', 1)[1])
            assert body.count('\\N') <= 1, (style, body)
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=640x360:d=4:r=30', '-pix_fmt', 'yuv420p', '-y', str(source)], check=True)
    scene = Scene(id='a', label='a', start=0, end=3)
    draft = Draft(id='d', title='T', scenes=[scene], aspect='portrait', layout='window' if interview else 'blur', packaging=packaging)
    ass = tmp_path / '0.ass'
    ass.write_text(doc, encoding='utf-8')
    graph, label = pr.scene_video_graph(draft, scene, 0, ass, 1080, 1920)
    frame = tmp_path / 'frame.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-t', '3', '-i', str(source), '-filter_complex', graph,
                    '-map', f'[{label}]', '-ss', '1', '-frames:v', '1', '-y', str(frame)], check=True)
    assert Image.open(frame).size == (1080, 1920)


def test_long_title_lines_shrink_to_fit_the_frame():
    from backend.services.studio.caption_layout import width
    doc = pr.scene_ass(_packaging(title_lines=['AI无法替代视频编辑的关键：', '边干边学理解观众偏好需数月积累']), SCENES, 0)
    titles = [line for line in _dialogues(doc) if line.split(',')[3] in ('Title', 'TitleAccent')]
    assert len(titles) == 2
    for line in titles:
        size = int(re.search(r'\\fs(\d+)', line).group(1))
        text = re.sub(r'\{[^}]*\}', '', line.split(',,0,0,0,,', 1)[1])
        assert size <= 112 and size * width(text) <= 1000


def test_interview_window_renders_title_canvas_and_window(tmp_path):
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=640x360:d=4:r=30', '-pix_fmt', 'yuv420p', '-y', str(source)], check=True)
    scene = Scene(id='a', label='a', start=0, end=3)
    draft = Draft(id='d', title='T', scenes=[scene], aspect='portrait', layout='window',
                  packaging=_packaging(cues=[{'start': 0.5, 'end': 2.5, 'text': '第一句', 'original': 'first line'}], speakers=[], tags=[]))
    ass = tmp_path / '0.ass'
    ass.write_text(pr.scene_ass(draft.packaging, draft.scenes, 0), encoding='utf-8')
    graph, label = pr.scene_video_graph(draft, scene, 0, ass, 1080, 1920)
    frame = tmp_path / 'frame.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0', '-t', '3', '-i', str(source), '-filter_complex', graph,
                    '-map', f'[{label}]', '-ss', '1.5', '-frames:v', '1', '-y', str(frame)], check=True)
    image = Image.open(frame).convert('RGB')
    assert image.size == (1080, 1920)
    assert image.getpixel((20, 1700)) == image.getpixel((1060, 1800))  # plain canvas below the window
    title_region = image.crop((200, 150, 880, 400))
    assert max(max(px) for px in title_region.getdata()) > 180  # bright title text drawn on the dark canvas
    window_row = [image.getpixel((x, pr.WIN_Y + 200)) for x in range(0, 1080, 60)]
    assert len(set(window_row)) > 3  # the source picture fills the 4:3 window


def test_the_palette_colours_accents_and_keeps_pill_text_readable():
    lemon = pr.scene_ass(_packaging(palette='lemon', style='boxed'), SCENES, 1)
    assert '&H003CDCF4' in lemon  # lemon F4DC3C in ASS BGR order
    pill = next(line for line in lemon.splitlines() if line.startswith('Style: TagPill'))
    assert pill.split(',')[3] == pr.INK  # dark text on a light accent
    azure = pr.scene_ass(_packaging(), SCENES, 1)
    assert '&H00FF8B5A' in azure and '&H003CDCF4' not in azure
    draft = Draft(id='d', title='T', scenes=SCENES[:1], aspect='portrait', layout='window', packaging=_packaging(palette='mint'))
    graph, _ = pr.scene_video_graph(draft, SCENES[0], 0, pr.FONT_DIR / 'x.ass', 1080, 1920)
    assert 'color=c=0x111917' in graph and 'color=c=0x46D3A6' in graph
def test_packaged_cjk_loads_bundled_font_in_real_ffmpeg(tmp_path):
    """A successful encode can still draw tofu when the font provider rejects a family."""
    import shutil

    from backend.services.publish_export import _escape_filter_path
    from backend.utils.ffmpeg_utils import get_ffmpeg_path

    ffmpeg = get_ffmpeg_path()
    if not shutil.which(ffmpeg):
        pytest.skip('ffmpeg unavailable')
    scene = Scene(id='font', start=0, end=1)
    value = Packaging(template='podcast_en', audience_language='zh',
                      title_lines=['中文字体测试'],
                      cues=[{'start':0, 'end':1, 'text':'字幕应显示中文'}])
    ass = tmp_path / 'cjk.ass'
    ass.write_text(pr.scene_ass(value, [scene], 0), encoding='utf-8')
    graph = f"ass='{_escape_filter_path(ass)}':fontsdir='{_escape_filter_path(pr.FONT_DIR)}'"
    result = subprocess.run([ffmpeg, '-v', 'verbose', '-f', 'lavfi', '-i',
                             'color=black:s=1080x1920:d=1', '-vf', graph,
                             '-frames:v', '1', '-f', 'null', '-'],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    selections = '\n'.join(line for line in result.stderr.splitlines() if 'fontselect:' in line)
    assert 'NotoSansSC' in selections, selections
    assert 'failed to find any fallback' not in selections, selections


@pytest.mark.parametrize('at,fit', [(0.25, False), (0.75, True), (1.25, False)])
def test_interview_window_preserves_slide_edges_only_during_fit_shots(tmp_path, at, fit):
    # Side markers stand for text at the edges of an inserted quote card.
    # This track is scene-relative even when the source scene starts later.
    source = tmp_path / 'edge-markers.png'
    image = Image.new('RGB', (1920, 1080), (128, 128, 128))
    image.paste((255, 0, 0), (0, 0, 200, 1080))
    image.paste((0, 255, 0), (1720, 0, 1920, 1080))
    image.save(source)
    scene = Scene(id='slide', start=10, end=12, crop_x=.5, crop_track=[
        {'start': 0, 'crop_x': .5, 'mode': 'crop'},
        {'start': .5, 'crop_x': .5, 'mode': 'fit'},
        {'start': 1, 'crop_x': .5, 'mode': 'crop'},
    ])
    draft = Draft(id='d', title='T', scenes=[scene], aspect='portrait', layout='window',
                  packaging=_packaging(title_lines=[], cues=[], speakers=[], tags=[]))
    ass = tmp_path / 'scene.ass'
    ass.write_text(pr.scene_ass(draft.packaging, draft.scenes, 0), encoding='utf-8')
    graph, label = pr.scene_video_graph(draft, scene, 0, ass, 1080, 1920)
    frame = tmp_path / 'frame.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-threads', '1', '-loop', '1', '-i', str(source),
                    '-filter_complex_threads', '1', '-filter_complex', graph, '-map', f'[{label}]',
                    '-ss', str(at), '-frames:v', '1', '-threads', '1', '-y', str(frame)],
                   check=True, timeout=30)
    rendered = Image.open(frame).convert('RGB')
    left = rendered.getpixel((40, pr.WIN_Y + pr.WIN_H // 2))
    right = rendered.getpixel((1040, pr.WIN_Y + pr.WIN_H // 2))
    if fit:
        assert left[0] > 200 and left[1] < 40, 'left edge of quote card was cropped'
        assert right[1] > 200 and right[0] < 40, 'right edge of quote card was cropped'
    else:
        assert all(abs(channel - 128) < 5 for pixel in (left, right) for channel in pixel)


def test_re_render_of_an_old_empty_fallback_recovers_source_without_mutating_draft(monkeypatch):
    from backend.services.studio import render
    from backend.services.studio.models import Draft
    draft = Draft(id='old', title='Old output', scenes=[{'id': 's', 'start': 0, 'end': 3}],
                  packaging=_packaging(cues=[], fallback=True, burned_captions=False))
    monkeypatch.setattr(render, '_load_srt_entries', lambda _: [
        {'start_time': '00:00:00,000', 'end_time': '00:00:03,000', 'text': 'The original source words.'}])
    warnings = []
    recovered = render.recover_empty_packaging('project', draft, warnings)
    assert [c.text for c in recovered.packaging.cues] == ['The original source words.']
    assert draft.packaging.cues == []
    assert warnings == ['包装未能完整生成，已使用原字幕']
    burned = draft.model_copy(update={'packaging': draft.packaging.model_copy(update={'burned_captions': True})})
    assert render.recover_empty_packaging('project', burned, []) is burned
