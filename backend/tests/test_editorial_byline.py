"""Without a model deck the editorial byline is the guest, not the headline printed twice."""
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill, paint_fill
from backend.tests.test_template_preview_look import _render


def _frames(**kwargs):
    body = dict(
        version=2, template='editorial', audience_language='zh',
        title_lines=['我爸连西装都没有', '24小时内买了一套'],
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': ''}],
        cues=[{'start': 0.2, 'end': 2.0, 'text': '我爸连西装都没有', 'original': "My dad didn't even have a suit"}],
    )
    body.update(kwargs)
    packaging = Packaging(**body)
    fill = paint_fill(build_fill(packaging, 3, template='editorial'), packaging, 'editorial')
    return fill, _render('editorial', fill)


def test_an_empty_deck_does_not_repeat_the_headline_in_the_byline():
    # dad_suit e: the LLM left deck and issue empty.
    fill, frames = _frames(deck='', issue='')
    byline = frames['0.5']['trk']['text']
    assert byline == '黄仁勋', byline
    assert '西装' not in byline and '24小时' not in byline
    assert frames['0.5']['kick']['text'] == ''
    assert not any(rect['slot'] == 'kicker' for rect in frames['0.5']['rects'])
    # The footer is a line, not a bare timecode.
    assert fill['issue'] == '黄仁勋 访谈'


def test_a_role_joins_the_guest_and_a_model_deck_still_wins():
    fill, frames = _frames(deck='', speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达CEO'}])
    assert frames['0.5']['trk']['text'] == '黄仁勋 · 英伟达CEO'
    fill, frames = _frames(deck="Jensen Huang on his parents' American dream", issue='BG2 POD · 2026.10.15')
    assert frames['0.5']['kick']['text'] == "Jensen Huang on his parents' American dream"
    assert frames['0.5']['trk']['text'] == "HIS PARENTS' AMERICAN DREAM · JENSEN HUANG"
    assert fill['issue'] == 'BG2 POD · 2026.10.15'
