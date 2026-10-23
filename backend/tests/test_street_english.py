"""Street English: the sentence on its spoken lines, not spread evenly over the cue."""
import re

from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import build_fill
from backend.tests.test_template_preview_look import _render


def _fill():
    rows = [
        (0.0, 1.5, 'I came home late.', ''),
        (4.0, 6.0, 'Every time you open a new door, there is another one.', ''),
    ]
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{
            'start': 0.0, 'end': 6.0,
            'text': '我回家晚了。每次你打开一扇新门，后面还有一扇。',
            'original': 'I came home late. Every time you open a new door, there is another one.',
        }],
    )
    scenes = [Scene(id='a', start=0.0, end=3.0), Scene(id='b', start=3.6, end=8.0)]
    return build_fill(packaging, 7.4, template='street', scenes=scenes, transcript=rows)


def test_english_words_sit_on_the_line_they_were_spoken_on():
    fill = _fill()
    english = fill['moments'][0]['en']
    every = next(word for word in english if word['w'] == 'Every')
    late = next(word for word in english if word['w'] == 'late.')
    # Scene b starts at 3.0 on the output clock; 4.0 s source is 3.4 s output.
    assert every['t0'] >= 3.4 - 1e-6
    assert late['t1'] <= 1.5 + 1e-6
    # Spread over 0..5.4 s by length, "Every" used to land at about 1.3 s, a clause early.


def test_the_line_on_screen_is_the_one_being_spoken():
    fill = _fill()
    phrases = [phrase for moment in fill['moments'] for phrase in moment['zh']]
    door = next(phrase for phrase in phrases if '新门' in phrase['s'])
    at = f"{door['t0'] + 0.05:.3f}"
    painted = _render('street', fill, times=['0.300', at])
    first = re.sub(r'<[^>]+>', '', painted['0.300']['en']['html'])
    second = re.sub(r'<[^>]+>', '', painted[at]['en']['html'])
    assert first == 'I came home late.'
    assert second.startswith('Every time you open a new door')
    assert 'late' not in second
