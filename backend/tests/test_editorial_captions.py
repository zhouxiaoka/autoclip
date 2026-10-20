"""Editorial and street captions follow the current sentence on the clip clock."""
import json
import subprocess
from pathlib import Path

from backend.services.studio.audio import scene_duration
from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import build_fill

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


def _visible_sentence(template: str, fill: dict, index: int) -> str:
    row = _captions(template, fill)[index]
    html = row['html']
    assert 'class="w"' not in html
    text = fill['words'][index]['text']
    assert text in html
    for other in fill['words']:
        if other['text'] == text:
            continue
        assert other['text'][:12] not in html
    return html


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
