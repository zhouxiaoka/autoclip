"""Editorial English shows the part of the sentence its Chinese screen says, never the last screen's tail."""
import re

from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill
from backend.tests.test_template_motion import frames


def _shown(template, packaging, count):
    shown = []
    for row in frames(template, build_fill(packaging, count / 30, template=template), count):
        zh = re.sub(r'<[^>]+>', '', row['zh'])
        en = re.sub(r'<[^>]+>', '', row['en'])
        if zh and (not shown or shown[-1][0] != zh):
            shown.append((zh, en))
    return shown


def test_each_english_word_is_on_one_screen_and_turns_at_a_clause():
    # dad_suit O99 / O219: "and I gave them..." and "travel that much. They don't travel that much."
    original = "and I gave them literally 24 hours of lead time, and they don't travel that much."
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['话题'], deck='Dad',
        cues=[{'start': 0.0, 'end': 6.0, 'text': '我只给了他们24小时准备他们平时不太出门', 'original': original}],
    )
    shown = _shown('editorial', packaging, 190)
    assert len(shown) >= 3, shown
    english = [en for _, en in shown]
    assert ' '.join(english) == original, english
    assert all(english), shown
    # A screen that turns near a comma turns on it.
    assert any(en.endswith('lead time,') for en in english), english
