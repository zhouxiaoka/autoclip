"""Editorial and street captions follow the current sentence on the clip clock."""
import json
import re
import subprocess
from itertools import pairwise
from pathlib import Path

from backend.services.studio.audio import scene_duration
from backend.services.studio.caption_layout import page_lines, page_screens, width
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


def _visible_sentence(template: str, fill: dict, index: int) -> str:
    row = _captions(template, fill)[index]
    html = row['html']
    assert 'class="w"' not in html
    text = fill['words'][index]['text']
    assert _plain_caption(html) == text
    assert html.lower().count('<br>') == text.count('\n')
    assert html.lower().count('<br>') <= 1
    return html


def _assert_pages_cover(paged: list[dict], baseline: list[dict], limit: int) -> None:
    """Each original cue is split into two-line screens that share its frame span."""
    cursor = 0
    for cue in baseline:
        parts = []
        first = last = None
        while cursor < len(paged):
            word = paged[cursor]
            piece = word['text'].replace('\n', '')
            if not cue['text'][len(''.join(parts)):].startswith(piece):
                break
            # A cue that already fits stays one string, so CSS wraps it as before.
            # A paged screen carries an explicit newline and each line fits the box.
            lines = word['text'].split('\n') if '\n' in word['text'] else page_lines(word['text'], limit)
            assert 1 <= len(lines) <= 2
            assert ''.join(lines) == piece
            assert all(width(line) <= limit + 1e-6 for line in lines)
            if first is None:
                first = word['start_frame']
            else:
                assert word['start_frame'] == last
            last = word['end_frame']
            assert word['end_frame'] > word['start_frame']
            parts.append(piece)
            cursor += 1
            if ''.join(parts) == cue['text']:
                break
        assert ''.join(parts) == cue['text']
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
    fill = build_fill(_packaging(recorded, cues), scene_duration(scene), fps=recorded['fps'], scenes=[scene])
    assert [(word['start_frame'], word['end_frame'], word['text']) for word in fill['words']] == [
        (word['start_frame'], word['end_frame'], word['text']) for word in recorded['words']
    ]
    for template in ('editorial', 'street'):
        for index, word in enumerate(fill['words']):
            _visible_sentence(template, fill, index)
            if index:
                assert word['start_frame'] >= fill['words'][index - 1]['end_frame']
        _paged(_packaging(recorded, cues), scene_duration(scene), fill['words'], template, fps=recorded['fps'], scenes=[scene])


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
    fill = build_fill(_packaging(recorded, cues), scene_duration(scene), scenes=[scene])
    assert len(fill['words']) == len(recorded['words'])
    total = round(scene_duration(scene) * fill['fps'])
    assert scene_start > length
    for index, word in enumerate(fill['words']):
        assert 0 <= word['start_frame'] < word['end_frame'] <= total
        assert word['start_frame'] < 30 * 25
        assert word['text'] == recorded['words'][index]['text']
        if index:
            assert word['start_frame'] >= fill['words'][index - 1]['end_frame']
    assert fill['words'][0]['start_frame'] == round(0.4 * 30)
    for template in ('editorial', 'street'):
        for index in range(len(fill['words'])):
            _visible_sentence(template, fill, index)
        paged = _paged(_packaging(recorded, cues), scene_duration(scene), fill['words'], template, scenes=[scene])
        assert paged['words'][0]['start_frame'] == round(0.4 * 30)
        assert all(word['start_frame'] < 30 * 25 for word in paged['words'])


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
            baseline['words'], template, fps=recorded['fps'], safe_area=recorded['safe_area'],
        )
        cue = baseline['words'][index]
        screens = [
            word for word in paged['words']
            if cue['start_frame'] <= word['start_frame'] and word['end_frame'] <= cue['end_frame']
        ]
        if length > limit * 2:
            assert len(screens) >= 2
        else:
            assert screens == [cue]


def test_emphasis_follows_the_phrase_onto_each_screen_it_touches():
    recorded = json.loads((TRUNCATION / 'fill-ed-i150-1-efb323df.json').read_text(encoding='utf-8'))
    text = recorded['words'][1]['text']
    limit = caption_line_limit('editorial', 'xiaohongshu')
    boundary = len(page_screens(text, limit)[0].replace('\n', ''))
    phrase = text[boundary - 4:boundary + 4]
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['标题'],
        cues=[{'start': 0, 'end': 10, 'text': text}],
        emphasis=[{'at': 0, 'text': phrase}],
    )
    fill = build_fill(packaging, 10, template='editorial')
    shown = ''.join(word['text'].replace('\n', '') for word in fill['words'])
    assert shown == text
    marked = [word for word in fill['words'] if word['emphasis']]
    assert marked and ''.join(word['emphasis'] for word in marked) == phrase
    assert any(not word['emphasis'] for word in fill['words'])
    for index in range(len(fill['words'])):
        _visible_sentence('editorial', fill, index)


def test_english_pages_keep_the_spaces():
    packaging = Packaging(
        version=2, template='street', audience_language='en', title_lines=['Title'],
        cues=[{'start': 0.2, 'end': 4.2, 'text': LONG_EN}],
    )
    fill = build_fill(packaging, 5, safe_area='xiaohongshu', template='street')
    assert ''.join(word['text'].replace('\n', '') for word in fill['words']) == LONG_EN
    assert len(fill['words']) >= 2
    assert fill['words'][0]['start_frame'] == round(0.2 * 30)
    assert fill['words'][-1]['end_frame'] == round(4.2 * 30)
    for index in range(len(fill['words'])):
        _visible_sentence('street', fill, index)


def test_caption_line_limit_matches_the_template_box():
    editorial = (ROOT / 'backend/assets/templates/editorial/style.css').read_text(encoding='utf-8')
    street_css = (ROOT / 'backend/assets/templates/street/style.css').read_text(encoding='utf-8')
    street_js = (ROOT / 'backend/assets/templates/street/template.js').read_text(encoding='utf-8')

    def box(css: str) -> tuple[int, int, int]:
        body = re.search(r'(?:^|\n)#sub\s*\{([^}]*)\}', css).group(1)
        def px(prop: str) -> int:
            return int(re.search(rf'{prop}\s*:\s*(\d+)px', body).group(1))
        return px('left'), px('right'), px('font-size')

    left, right, font = box(editorial)
    assert caption_line_limit('editorial', 'douyin') == (720 - left - right) // font
    _, _, street_font = box(street_css)
    insets = re.findall(r'(\w+):\s*\{[^}]*left:\s*(\d+),\s*right:\s*(\d+)', street_js)
    assert insets
    for area, inset_left, inset_right in insets:
        assert caption_line_limit('street', area) == (720 - int(inset_left) - int(inset_right)) // street_font
