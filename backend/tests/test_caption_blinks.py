"""No empty caption frame between two sentences a couple of frames apart."""
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill
from backend.tests.test_template_motion import frames


def _fill(template, gap):
    packaging = Packaging(
        version=2, template=template, audience_language='zh', title_lines=['话题'],
        cues=[
            {'start': 0.0, 'end': 2.0, 'text': '我们包了架飞机', 'original': 'We chartered a plane'},
            {'start': 2.0 + gap, 'end': 4.0, 'text': '他们见到总统特别高兴', 'original': 'they were so happy to meet the president'},
        ],
    )
    return build_fill(packaging, 5, template=template)


def test_a_two_frame_gap_between_cues_holds_the_caption():
    for template in ('street', 'editorial'):
        fill = _fill(template, 2 / 30)
        rows = frames(template, fill, 120)
        blank = [index for index, row in enumerate(rows) if 30 < index < 90 and not row['zh']]
        assert blank == [], (template, blank)
        words = sorted(fill['words'], key=lambda word: word['start_frame'])
        assert all(a['end_frame'] == b['start_frame'] for a, b in zip(words, words[1:]))


def test_a_real_pause_still_clears_the_line():
    fill = _fill('street', 0.6)
    rows = frames('street', fill, 120)
    blank = [index for index, row in enumerate(rows) if 55 < index < 85 and not row['zh']]
    assert len(blank) >= 15
