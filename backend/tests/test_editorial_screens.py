"""Editorial shows a short screen at a time, like the preview (about 6-8 characters, about 1.5s)."""
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill
from backend.tests.test_template_motion import frames


import re


def _screens(fill, count):
    shown = []
    for row in frames('editorial', fill, count):
        zh = re.sub(r'<[^>]+>', '', row['zh'])
        if zh and (not shown or shown[-1][0] != zh):
            shown.append([zh, 0])
        if zh:
            shown[-1][1] += 1
    return shown


def test_a_long_sentence_turns_over_in_short_screens_on_word_breaks():
    # dad_suit O1080: an 18-character line used to sit up for 4s as one block.
    text = '他跑出去买了一套穿着全新的西装来了'
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['话题'],
        deck='Dad in a new suit',
        cues=[{'start': 0.0, 'end': 4.5, 'text': text, 'original': 'He ran out and bought a suit and came in a brand new suit'}],
    )
    fill = build_fill(packaging, 5, template='editorial')
    shown = _screens(fill, 140)
    assert ''.join(zh for zh, _ in shown) == text
    assert len(shown) >= 3, shown
    assert all(len(zh) <= 9 for zh, _ in shown), shown
    # Every screen is up long enough to read and none is a stuck caption.
    assert all(18 <= count <= 78 for _, count in shown), shown
    # Breaks land between words: never 西|装, 全|新 or 一|套.
    joints = [left[-1] + right[0] for (left, _), (right, _) in zip(shown, shown[1:])]
    assert not set(joints) & {'西装', '全新', '一套', '出去'}, joints


def test_a_slow_phrase_is_split_at_a_natural_break():
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['话题'],
        deck='Slow',
        cues=[{'start': 0.0, 'end': 3.6, 'text': '我妈也买了新裙子', 'original': 'My mom bought a new dress too'}],
    )
    shown = _screens(build_fill(packaging, 4, template='editorial'), 110)
    assert len(shown) == 2, shown
    assert ''.join(zh for zh, _ in shown) == '我妈也买了新裙子'
    assert shown[0][0][-1] + shown[1][0][0] not in {'裙子', '新裙'}
