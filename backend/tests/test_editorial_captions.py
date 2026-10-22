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
    pieces = _phrases('甲乙丙丁生产力需要15小时写进DNA里', 5)
    assert ''.join(pieces).replace(' ', '') == '甲乙丙丁生产力需要15小时写进DNA里'
    for earlier, later in pairwise(pieces):
        assert not (earlier.endswith('生') and later.startswith('产'))
        assert not (earlier.endswith('15小') and later.startswith('时'))
        assert not (earlier.endswith('DNA') and later.startswith('里'))
        assert '15小' not in earlier or '时' in earlier
    assert any('15小时' in piece for piece in pieces)
    assert any('生产力' in piece for piece in pieces)
    assert any('DNA里' in piece for piece in pieces)


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
    assert fill['deck'] == '' and fill['credit'] == '' and fill['hook_trk'] == ''


def test_progress_bar_is_a_filter_not_an_overlay_frame():
    from backend.services.studio.packaging_html import composite_tail
    graph, label = composite_tail('base', 1, 1080, 1920, '', template='street', offset=12.5, total=100)
    assert label == 'paced'
    assert "drawbox=x=0:y=1908:w='iw*(t+12.500)/100.000':h=12:color=0xD7FF3A:t=fill" in graph
    editorial, _ = composite_tail('base', 1, 1080, 1920, '', template='editorial', offset=0, total=80)
    assert "y=1826" in editorial and '(t+0.000)/80.000' in editorial
    assert "color=c=0x0C0A08:s=1080x1000" in editorial and "overlay=0:920" in editorial
    plain, plain_label = composite_tail('base', 1, 1080, 1920, '')
    assert plain_label == 'html' and 'drawbox' not in plain


def test_caption_line_limit_matches_the_template_box():
    editorial = (ROOT / 'backend/assets/templates/editorial/style.css').read_text(encoding='utf-8')
    street_css = (ROOT / 'backend/assets/templates/street/style.css').read_text(encoding='utf-8')
    assert 'font-size: 52px' in editorial and 'left: 60px' in editorial and 'right: 60px' in editorial
    assert 'font-size: 100px' in street_css and 'left: 30px' in street_css and 'right: 30px' in street_css
    assert caption_line_limit('editorial', 'douyin') == (1080 - 120) // 52
    for area in ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts'):
        assert caption_line_limit('street', area) == (1080 - 60) // 100
