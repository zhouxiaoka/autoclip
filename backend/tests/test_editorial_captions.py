"""Editorial and street captions follow the current sentence on the clip clock."""
import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

from backend.services.studio.audio import scene_duration
from backend.services.studio.caption_layout import width
from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import build_fill, caption_line_limit

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'editorial_repro'
HELPER = ROOT / 'frontend' / 'tests' / 'helpers' / 'caption-at.cjs'


def _fill(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))


def _packaging(fill: dict, cues: list[dict]) -> Packaging:
    return Packaging(
        version=2, template='editorial', audience_language='zh',
        title_lines=list(fill.get('title_lines') or ['标题']),
        cues=cues,
    )


def _captions(template: str, fill: dict) -> list[dict]:
    done = subprocess.run(
        ['node', str(HELPER), template],
        input=json.dumps(fill),
        capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)


def _plain_caption(html: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    for src, dst in (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>')):
        text = text.replace(src, dst)
    return text.removesuffix(' ')


def _norm(text: str) -> str:
    return re.sub(r'[，。、！？：；,.!?]+', '', text)


def _squash(text: str) -> str:
    return ''.join(_norm(text).split())


def _visible_sentence(template: str, fill: dict, index: int) -> str:
    row = _captions(template, fill)[index]
    html = row['html']
    text = fill['words'][index]['text']
    assert 'class="w"' not in html
    assert '<br' not in html.lower()
    assert '\n' not in text
    plain = _plain_caption(html)
    if template == 'street':
        assert plain == text
    else:
        assert text in plain
    return html


def _assert_pages_cover(paged: list[dict], baseline: list[dict], limit: int) -> None:
    """Each cue becomes one-line phrases that tile its frame span."""
    cursor = 0
    for cue in baseline:
        parts = []
        first = last = None
        target = _squash(cue['text'])
        while cursor < len(paged):
            word = paged[cursor]
            piece = word['text']
            assert '\n' not in piece
            assert width(piece) <= limit + 1.1
            joined = _squash(''.join(parts) + piece)
            if parts and not target.startswith(joined):
                break
            if first is None:
                first = word['start_frame']
            else:
                assert word['start_frame'] == last
            last = word['end_frame']
            assert word['end_frame'] > word['start_frame']
            parts.append(piece)
            cursor += 1
            if _squash(''.join(parts)) == target:
                break
        assert _squash(''.join(parts)) == target
        assert first == cue['start_frame'] and last == cue['end_frame']
    assert cursor == len(paged)
    for earlier, later in pairwise(paged):
        assert earlier['end_frame'] <= later['start_frame']


def _paged(packaging, duration, baseline, template, fps=30, safe_area='xiaohongshu', scenes=None):
    limit = caption_line_limit(template, safe_area)
    paged = build_fill(packaging, duration, fps=fps, safe_area=safe_area, scenes=scenes, template=template)
    _assert_pages_cover(paged['words'], baseline, limit)
    for index in range(len(paged['words'])):
        _visible_sentence(template, paged, index)
    return paged


def test_repro_fill_switches_one_sentence_on_the_clip_clock():
    """ed1 (Mac recheck) already has sequential clip frames. Each midpoint shows only that sentence."""
    recorded = _fill('fill-ed1-92df5145.json')
    scene = Scene(id='ed1', start=0, end=recorded['words'][-1]['end_frame'] / recorded['fps'])
    cues = [
        {'start': word['start_frame'] / recorded['fps'], 'end': word['end_frame'] / recorded['fps'], 'text': word['text']}
        for word in recorded['words']
    ]
    for template in ('editorial', 'street'):
        fill = build_fill(_packaging(recorded, cues), scene_duration(scene), fps=recorded['fps'], scenes=[scene], template=template)
        assert _squash(''.join(word['text'] for word in fill['words'])) == _squash(''.join(word['text'] for word in recorded['words']))
        assert fill['words'][0]['start_frame'] == recorded['words'][0]['start_frame']
        assert fill['words'][-1]['end_frame'] == recorded['words'][-1]['end_frame']
        for index, word in enumerate(fill['words']):
            _visible_sentence(template, fill, index)
            if index:
                assert word['start_frame'] >= fill['words'][index - 1]['end_frame']
        _paged(_packaging(recorded, cues), scene_duration(scene), [
            {'text': word['text'], 'start_frame': word['start_frame'], 'end_frame': word['end_frame']}
            for word in recorded['words']
        ], template, fps=recorded['fps'], scenes=[scene])


def test_scene_that_starts_after_its_own_length_still_shows_each_sentence():
    """ed6 clip 2: source cues begin at 74.3s on a 41s clip, so the old clock clamped every word to the last frame."""
    recorded = _fill('fill-ed6-interview150-a4a4a6de.json')
    assert {word['start_frame'] for word in recorded['words']} == {1229}
    scene_start = 74.3
    length = 41.0
    scene = Scene(id='ed6b', start=scene_start, end=scene_start + length)
    cursor = scene_start + 0.4
    cues = []
    for word in recorded['words']:
        cues.append({'start': cursor, 'end': cursor + 5, 'text': word['text']})
        cursor += 5
    for template in ('editorial', 'street'):
        fill = build_fill(_packaging(recorded, cues), scene_duration(scene), scenes=[scene], template=template)
        total = round(scene_duration(scene) * fill['fps'])
        assert scene_start > length
        assert _squash(''.join(word['text'] for word in fill['words'])) == _squash(''.join(cue['text'] for cue in cues))
        for index, word in enumerate(fill['words']):
            assert 0 <= word['start_frame'] < word['end_frame'] <= total
            assert word['start_frame'] < 30 * 25
            if index:
                assert word['start_frame'] >= fill['words'][index - 1]['end_frame']
            _visible_sentence(template, fill, index)
        assert fill['words'][0]['start_frame'] == round(0.4 * 30)


TRUNCATION = Path(__file__).resolve().parent / 'fixtures' / 'caption_truncation'
LONG_EN = 'and brought exactly the same energy to a great many founders over the years'


def _from_recorded(name: str, template: str) -> tuple[dict, dict, int]:
    recorded = json.loads((TRUNCATION / name).read_text(encoding='utf-8'))
    fps = recorded['fps']
    cues = [
        {'start': word['start_frame'] / fps, 'end': word['end_frame'] / fps, 'text': word['text']}
        for word in recorded['words']
    ]
    duration = recorded['words'][-1]['end_frame'] / fps
    area = recorded['safe_area']
    packaging = Packaging(
        version=2, template=template, audience_language='zh',
        title_lines=list(recorded.get('title_lines') or ['标题']),
        cues=cues,
    )
    baseline = build_fill(packaging, duration, fps=fps, safe_area=area)
    return recorded, baseline, caption_line_limit(template, area)


def test_repro_long_sentences_page_inside_two_lines():
    """Mac recheck 906e0dc0: the 113-character editorial cue and the street cues were clipped."""
    cases = (
        ('fill-ed-i150-1-efb323df.json', 'editorial', 1, 113),
        ('fill-st-i150-97c135c8.json', 'street', 3, 92),
        ('fill-st-s45-89fcb363.json', 'street', 4, 12),
    )
    for name, template, index, length in cases:
        recorded, baseline, limit = _from_recorded(name, template)
        assert len(recorded['words'][index]['text']) == length
        paged = _paged(
            Packaging(
                version=2, template=template, audience_language='zh',
                title_lines=list(recorded.get('title_lines') or ['标题']),
                cues=[
                    {'start': word['start_frame'] / recorded['fps'], 'end': word['end_frame'] / recorded['fps'], 'text': word['text']}
                    for word in recorded['words']
                ],
            ),
            recorded['words'][-1]['end_frame'] / recorded['fps'],
            recorded['words'], template, fps=recorded['fps'], safe_area=recorded['safe_area'],
        )
        cue = recorded['words'][index]
        screens = [
            word for word in paged['words']
            if cue['start_frame'] <= word['start_frame'] and word['end_frame'] <= cue['end_frame']
        ]
        assert screens
        assert _squash(''.join(word['text'] for word in screens)) == _squash(cue['text'])
        if width(cue['text']) > limit:
            assert len(screens) >= 2
        else:
            assert len(screens) == 1


def test_emphasis_follows_the_phrase_onto_the_piece_that_contains_it():
    recorded = json.loads((TRUNCATION / 'fill-ed-i150-1-efb323df.json').read_text(encoding='utf-8'))
    text = recorded['words'][1]['text']
    clause = max((part.strip() for part in re.split(r'[，。、！？：；,.!?]+', text) if part.strip()), key=len)
    phrase = clause[2:8]
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['标题'],
        cues=[{'start': 0, 'end': 10, 'text': text}],
        emphasis=[{'at': 0, 'text': phrase}],
    )
    fill = build_fill(packaging, 10, template='editorial')
    shown = ''.join(word['text'] for word in fill['words'])
    assert _squash(shown) == _squash(text)
    marked = [word for word in fill['words'] if word['emphasis']]
    assert marked and all(word['emphasis'] == phrase and phrase in word['text'] for word in marked)
    assert any(not word['emphasis'] for word in fill['words'])
    for index in range(len(fill['words'])):
        _visible_sentence('editorial', fill, index)


def test_english_pages_keep_the_spaces():
    packaging = Packaging(
        version=2, template='street', audience_language='en', title_lines=['Title'],
        cues=[{'start': 0.2, 'end': 4.2, 'text': LONG_EN}],
    )
    fill = build_fill(packaging, 5, safe_area='xiaohongshu', template='street')
    assert ''.join(''.join(item['text'].split()) for item in fill['words']) == ''.join(LONG_EN.split())
    assert len(fill['words']) >= 2
    assert fill['words'][0]['start_frame'] == round(0.2 * 30)
    assert fill['words'][-1]['end_frame'] == round(4.2 * 30)
    for index in range(len(fill['words'])):
        _visible_sentence('street', fill, index)


def test_chinese_breaks_keep_words_numbers_and_latin_together():
    from backend.services.studio.overlay_fill import _phrases
    marked = _phrases('甲乙丙丁生产力需要15小时写进DNA里', 5, '生产力')
    assert ''.join(marked).replace(' ', '') == '甲乙丙丁生产力需要15小时写进DNA里'
    for earlier, later in pairwise(marked):
        assert not (earlier.endswith('生') and later.startswith('产'))
        assert not (earlier.endswith('15小') and later.startswith('时'))
        assert not (earlier.endswith('DNA') and later.startswith('里'))
    assert any('生产力' in piece for piece in marked)
    plain = _phrases('甲乙丙丁生产力需要15小时写进DNA里', 5)
    assert ''.join(plain).replace(' ', '') == '甲乙丙丁生产力需要15小时写进DNA里'
    for earlier, later in pairwise(plain):
        assert not (earlier.endswith('15小') and later.startswith('时'))
        assert not (earlier.endswith('DNA') and later.startswith('里'))
        assert '15小' not in earlier or '时' in earlier
    assert any('15小时' in piece for piece in plain)
    assert any('DNA里' in piece for piece in plain)
    lead = _phrases('甲乙丙的DNA里', 3)
    assert lead and all(not piece.startswith('的') for piece in lead)
    assert any('DNA里' in piece for piece in lead)
    highlight = _phrases('智能会解锁更多机会', 8, '机会')
    assert all(piece.strip('，。') != '机会' for piece in highlight)
    assert '机会' in ''.join(highlight)


def test_a_sentence_across_cuts_plays_each_phrase_once():
    text = '我完全不同意，他把在机场买的东西都扔了'
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{'start': 85, 'end': 97, 'text': text}],
    )
    scenes = [Scene(id='a', start=85, end=91), Scene(id='b', start=91, end=97)]
    fill = build_fill(packaging, 12, scenes=scenes, template='street')
    shown = [word['text'] for word in fill['words']]
    assert _squash(''.join(shown)) == _squash(text)
    assert len(shown) == len(set(shown))
    first = [word['text'] for word in fill['words'] if word['start_frame'] < 6 * 30]
    second = [word['text'] for word in fill['words'] if word['start_frame'] >= 6 * 30]
    assert first and second
    assert not set(first) & set(second)
    assert first[0].startswith('我完全不同意')

    tail = build_fill(packaging, 4, scenes=[Scene(id='tail', start=93, end=97)], template='street')
    tail_text = ''.join(word['text'] for word in tail['words'])
    assert tail['words']
    assert '我完全不同意' not in tail_text
    assert '机场' in tail_text or '扔' in tail_text


def test_word_times_place_a_phrase_once_on_the_output_clock():
    text = '我完全不同意，他把东西扔了'
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{'start': 0, 'end': 8, 'text': text}],
    )
    words = [
        {'text': '我完全不同意', 'start': 0.2, 'end': 2.0},
        {'text': '他把东西扔了', 'start': 5.0, 'end': 7.5},
    ]
    scenes = [Scene(id='a', start=0, end=4), Scene(id='b', start=4, end=8)]
    fill = build_fill(packaging, 8, scenes=scenes, template='street', word_timing=[{'words': words}])
    shown = [(word['text'], word['start_frame'], word['end_frame']) for word in fill['words']]
    assert [item[0] for item in shown] == ['我完全不同意', '他把东西扔了']
    assert shown[0][1] == round(0.2 * 30)
    assert shown[1][1] == round(5.0 * 30)
    assert shown[0][0] not in ''.join(word['text'] for word in fill['words'] if word['start_frame'] >= 4 * 30)


def test_fallback_emphasis_uses_whole_words_and_an_empty_deck_stays_empty():
    from backend.services.studio.packaging import key_phrase
    assert key_phrase('他买了一件衬衫来') == '衬衫'
    assert key_phrase('这就是的美国梦') == '美国梦'
    assert key_phrase('真是奇怪的东西') == '东西'
    assert key_phrase('他在公司上班') == '上班'
    for bad in ('件衬衫来', '的美国梦', '怪的东西', '公司上班'):
        assert key_phrase('他买了一件衬衫来') != bad or bad == '衬衫'
    assert '件衬衫来' not in {key_phrase('他买了一件衬衫来')}
    spoken = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['标题'],
        cues=[{'start': 0, 'end': 4, 'text': '原话', 'original': 'This is literally 24 hours of labor and more'}],
    )
    fill = build_fill(spoken, 4, template='editorial')
    assert fill['deck'] == ''
    # No deck and no known guest: no byline, rather than the headline printed twice.
    assert fill['credit'] == '' and fill['hook_trk'] == ''
    assert 'literally' not in fill['credit'].lower() and 'hours' not in fill['credit'].lower()
    named = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['更闲的工作'],
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        cues=[{'start': 0, 'end': 4, 'text': '原话', 'original': 'This is literally 24 hours of labor and more'}],
    )
    named_fill = build_fill(named, 4, template='editorial')
    assert named_fill['deck'] == '' and named_fill['credit'] == '黄仁勋 · 英伟达'
    assert 'literally' not in named_fill['credit'].lower()


def test_progress_bar_is_a_filter_not_an_overlay_frame():
    from backend.services.studio.packaging_html import composite_tail
    graph, label = composite_tail('base', 1, 1080, 1920, '', template='street', offset=12.5, total=100)
    assert 'overlay=0:0:format=yuv420:eof_action=repeat[html]' in graph
    assert 'overlay=0:0:format=yuv420:shortest=1' not in graph
    assert label == 'paced'
    assert "scale=w='max(2\\,min(1080\\,2*trunc(1080*(t+12.500)/100.000/2)))':h=12:eval=frame" in graph
    assert 'overlay=x=0:y=1908' in graph and '0xD7FF3A' in graph
    editorial, _ = composite_tail('base', 1, 1080, 1920, '', template='editorial', offset=0, total=80)
    assert "y=1826" in editorial and '(t+0.000)/80.000' in editorial and 'eval=frame' in editorial
    assert 'min(960' in editorial and 'overlay=x=60:y=1826' in editorial
    assert "color=c=0x0C0A08:s=1080x1000" in editorial and "overlay=0:920" in editorial
    assert 'trim=end_frame=1' in editorial and 'loop=loop=-1:size=1' in editorial
    plain, plain_label = composite_tail('base', 1, 1080, 1920, '')
    assert plain_label == 'html' and 'drawbox' not in plain and 'eval=frame' not in plain


def test_caption_line_limit_matches_the_template_box():
    editorial = (ROOT / 'backend/assets/templates/editorial/style.css').read_text(encoding='utf-8')
    street_css = (ROOT / 'backend/assets/templates/street/style.css').read_text(encoding='utf-8')
    assert 'font-size: 52px' in editorial and 'left: 60px' in editorial and 'right: 60px' in editorial
    assert 'font-size: 48px' in street_css and 'line-height: 64px' in street_css
    assert 'left: 30px' in street_css and 'right: 30px' in street_css
    assert caption_line_limit('editorial', 'douyin') == (1080 - 120) // 52
    for area in ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts'):
        assert caption_line_limit('street', area) == (1080 - 60) // 48
    assert caption_line_limit('news') == (1080 - 144) // 42
    assert caption_line_limit('cinema') == (1080 - 160) // 40


def test_caption_breaks_do_not_depend_on_jieba():
    requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
    project = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    assert 'jieba' not in requirements and 'jieba' not in project


def test_a_phrase_in_the_second_shot_is_not_dropped_at_the_cut():
    text = '对大多数人来说，智能会解锁更多机会'
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{'start': 0, 'end': 16, 'text': text}],
    )
    scenes = [Scene(id='a', start=0, end=7.05), Scene(id='b', start=10, end=16)]
    fill = build_fill(packaging, 16, scenes=scenes, template='street')
    shown = [word['text'] for word in fill['words']]
    assert len(shown) == len(set(shown))
    assert _squash(''.join(shown)) == _squash(text)
    hit = [word for word in fill['words'] if '机会' in word['text']]
    assert len(hit) == 1
    assert hit[0]['start_frame'] >= round(7.05 * 30) - 2
    assert (hit[0]['end_frame'] - hit[0]['start_frame']) / 30 > 1
    assert any(word['start_frame'] < 7 * 30 and '大多数' in word['text'] for word in fill['words'])


def test_short_phrases_hold_for_at_least_half_a_second():
    text = '介绍，80小时，收尾，15小时'
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{'start': 0, 'end': 4, 'text': text}],
    )
    timing = [{'words': [
        {'text': '介绍', 'start': 0.0, 'end': 1.2},
        {'text': '80小时', 'start': 1.2, 'end': 1.57},
        {'text': '收尾', 'start': 1.57, 'end': 3.2},
        {'text': '15小时', 'start': 3.2, 'end': 3.57},
    ]}]
    fill = build_fill(packaging, 4, template='street', word_timing=timing)
    blob = ''.join(word['text'] for word in fill['words'])
    assert '80小时' in blob and '15小时' in blob
    assert not any(word['text'] in {'80小时', '15小时'} for word in fill['words'])
    for word in fill['words']:
        assert (word['end_frame'] - word['start_frame']) / 30 >= 0.55


def test_speaker_name_follows_the_transcript_not_the_model_alone():
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['更闲的工作'],
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}, {'at': 0, 'name': '主持人', 'role': '访谈'}],
        cues=[
            {'start': 14.7, 'end': 21.7, 'text': '智能会解锁更多机会', 'speaker': ''},
            {'start': 30.7, 'end': 44.9, 'text': '经济会增长', 'speaker': ''},
            {'start': 45.1, 'end': 56.4, 'text': '凯恩斯说工作会更闲吗', 'speaker': '黄仁勋'},
            {'start': 66.1, 'end': 77.6, 'text': '那十五小时又怎么说', 'speaker': '黄仁勋'},
        ],
    )
    # Host and guest alternate. The two Keynes questions are the host; a guest line sits between them.
    transcript = [
        (14.7, 21.7, 'intelligence unlocks more opportunity'),
        (30.7, 44.9, 'the economy can grow'),
        (45.1, 56.4, '>> would Keynes say we get more leisure?'),
        (56.4, 66.1, '>> not for the work itself'),
        (66.1, 77.6, '>> and what about fifteen hours a week?'),
    ]
    fill = build_fill(packaging, 80, template='street', transcript=transcript)

    def labels(start, end):
        return {word['speaker'] for word in fill['words'] if start - 0.05 <= word['start_frame'] / 30 < end}

    assert labels(14.7, 21.7) == {'黄仁勋'}
    assert labels(30.7, 44.9) == {'黄仁勋'}
    assert labels(45.1, 56.4) == {''}
    assert labels(66.1, 77.6) == {''}
    bare = build_fill(packaging, 80, template='street')
    assert bare['words'] and all(word['speaker'] == '' for word in bare['words'])

    contradicted = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}, {'at': 0, 'name': '主持人', 'role': '访谈'}],
        cues=[{'start': 45.1, 'end': 56.4, 'text': '凯恩斯说工作会更闲吗', 'speaker': '黄仁勋'}],
    )
    voiced = build_fill(
        contradicted, 60, template='street',
        word_timing=[{'words': [{'text': '凯恩斯说工作会更闲吗', 'start': 45.1, 'end': 56.4, 'speaker': '主持人'}]}],
    )
    assert voiced['words'] and all(word['speaker'] == '' for word in voiced['words'])
    agreed = build_fill(
        contradicted.model_copy(update={'cues': [{'start': 14.7, 'end': 21.7, 'text': '智能会解锁更多机会', 'speaker': ''}]}),
        30, template='street',
        word_timing=[{'words': [{'text': '智能会解锁更多机会', 'start': 14.7, 'end': 21.7, 'speaker': '黄仁勋'}]}],
    )
    assert {word['speaker'] for word in agreed['words']} == {'黄仁勋'}


def _ffmpeg_ok() -> bool:
    return subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode == 0


def _bar_edges(template: str, total: float, times: list[float], folder: Path) -> list[tuple[int, int]]:
    from PIL import Image
    from backend.services.studio.packaging_html import composite_tail
    graph, label = composite_tail('0:v', 1, 1080, 1920, '', template=template, offset=0, total=total)
    frames = [int(round(t * 30)) for t in times]
    picked = '+'.join(f'eq(n,{frame})' for frame in frames)
    dest = folder / template
    dest.mkdir()
    subprocess.run(
        [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', f'color=c=black:s=1080x1920:r=30:d={total}',
            '-f', 'lavfi', '-i', f'color=c=black@0:s=1080x1920:r=30:d={total},format=rgba',
            '-filter_complex', graph + f';[{label}]select=\'{picked}\'[picked]',
            '-map', '[picked]', '-vsync', 'vfr', str(dest / 'f%02d.png'),
        ],
        check=True, capture_output=True,
    )
    row_y = 1914 if template == 'street' else 1826
    edges = []
    for index, _time in enumerate(times, start=1):
        image = Image.open(dest / f'f{index:02d}.png').convert('RGB')
        row = [image.getpixel((x, row_y)) for x in range(1080)]
        if template == 'street':
            lit = [x for x, pixel in enumerate(row) if pixel[1] > 180 and pixel[0] > 140 and pixel[2] < 120]
        else:
            lit = [x for x, pixel in enumerate(row) if pixel[0] > 80 and pixel[1] > 80 and pixel[2] > 70]
        assert lit, (template, _time)
        edges.append((lit[0], lit[-1]))
    return edges


def test_progress_bar_width_tracks_three_timestamps(tmp_path):
    if not _ffmpeg_ok():
        return
    total = 4.0
    times = [0.5, 2.0, 3.5]
    street = _bar_edges('street', total, times, tmp_path)
    rights = []
    for t, (left, right) in zip(times, street):
        expected = 1080 * t / total
        assert left <= 2
        assert abs((right + 1) - expected) <= 1080 / total / 30 + 8
        rights.append(right)
    assert rights[0] < rights[1] < rights[2]
    assert rights[0] < 1080 * 0.4
    editorial = _bar_edges('editorial', total, times, tmp_path)
    for t, (left, right) in zip(times, editorial):
        expected_right = 60 + 960 * t / total
        assert left >= 58
        assert abs((right + 1) - expected_right) <= 960 / total / 30 + 8
        assert right <= 1020


def _graph_chains(graph: str) -> list[str]:
    return [chain for chain in graph.split(';') if chain]


def test_editorial_composite_has_no_per_frame_generator_or_conversion():
    """Structure, not wall time: CI runners are 2x slower than a desktop, so a seconds budget is noise.

    The 1.5.7 editorial graph cost about 2x classic per second of video. The causes were a
    looped yuva444p scrim and bar blended with ``format=auto`` (converted on every output
    frame) and a per-pixel ``colorbalance`` in the grade. Every generator and ``geq`` must
    run on one frame, be converted to the blend format before ``loop``, and every blend is yuv420.
    """
    from backend.services.studio.packaging_html import composite_tail
    from backend.services.studio.templates.registry import get
    for template in ('editorial', 'street'):
        grade = get(template).base.grade
        graph, label = composite_tail('base', 1, 1080, 1920, grade, template=template, offset=4, total=80)
        assert label == 'paced'
        assert 'colorbalance' not in graph
        sources = [chain for chain in _graph_chains(graph) if not chain.startswith('[')]
        assert sources, graph
        for chain in sources:
            assert 'trim=end_frame=1' in chain and 'loop=loop=-1:size=1' in chain, chain
            head, _, tail = chain.partition('loop=loop=-1')
            assert head.rstrip(',').endswith('format=yuva420p'), chain
            assert 'geq' not in tail and 'format=' not in tail, chain
        for chain in _graph_chains(graph):
            for blend in re.findall(r'overlay=[^;\[]*', chain):
                assert 'format=yuv420' in blend and 'format=auto' not in blend, blend
        assert 'format=yuva444p[ov]' not in graph and 'format=yuva420p[ov]' in graph
    scrims = [chain for chain in _graph_chains(composite_tail('base', 1, 1080, 1920, '', template='editorial', offset=0, total=3)[0]) if 'geq' in chain]
    assert len(scrims) == 1


def test_editorial_grade_keeps_the_warm_look_without_colorbalance(tmp_path):
    """The curves LUT replaced curves+colorbalance. A gray ramp must land within 2 levels of the old grade."""
    if not _ffmpeg_ok():
        return
    from backend.services.studio.templates.registry import get
    old = "curves=all='0/0.02 0.5/0.52 1/0.97',colorbalance=rs=0.035:gs=0.01:bs=-0.03:rh=0.025:bh=-0.02"
    grade = get('editorial').base.grade
    new = grade.split(',eq=')[0]
    assert new.startswith('curves=r=') and 'colorbalance' not in grade
    ramp = bytes(v for _row in range(2) for level in range(256) for v in (level, level, level))
    def run(vf: str) -> bytes:
        return subprocess.run(
            ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '256x2', '-i', '-',
             '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
            input=ramp, capture_output=True, check=True,
        ).stdout
    before, after = run(old), run(new)
    assert len(before) == len(after) == len(ramp)
    assert max(abs(a - b) for a, b in zip(before, after)) <= 2
    # Still warm: red lifted over blue in the shadows, as the preview grade does.
    assert after[3 * 32] > after[3 * 32 + 2] + 6


def test_editorial_scrim_darkens_the_lower_frame(tmp_path):
    if not _ffmpeg_ok():
        return
    from PIL import Image
    from backend.services.studio.packaging_html import composite_tail
    graph, label = composite_tail('0:v', 1, 1080, 1920, '', template='editorial', offset=0, total=3)
    shot = tmp_path / 'scrim.png'
    subprocess.run(
        [
            'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', 'color=c=0x4a3428:s=1080x1920:r=30:d=1',
            '-f', 'lavfi', '-i', 'color=c=black@0:s=1080x1920:r=30:d=1,format=rgba',
            '-filter_complex', graph, '-map', f'[{label}]', '-frames:v', '1', str(shot),
        ],
        check=True, capture_output=True,
    )
    image = Image.open(shot).convert('RGB')
    top = image.getpixel((540, 100))
    bottom = image.getpixel((540, 1919))
    assert top[0] > bottom[0] and top[1] > bottom[1]
