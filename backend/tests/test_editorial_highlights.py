"""A highlight is a whole word and lights once a clip."""
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill


def _accents(cues, emphasis):
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['话题'], deck='Deck',
        emphasis=[{'at': 0, 'text': text} for text in emphasis], cues=cues,
    )
    fill = build_fill(packaging, 40, template='editorial')
    return [(phrase['hl'] or phrase['s']) for moment in fill['moments'] for phrase in moment['zh'] if phrase['acc']]


def test_a_highlight_inside_a_word_grows_to_the_whole_word():
    # dad_suit O1750: only 差回 of 出差回来 turned gold.
    cues = [{'start': 0, 'end': 2.5, 'text': '我爸刚从美国出差回来', 'original': 'my dad just came back from a trip', 'emphasis': '差回'}]
    accents = _accents(cues, [])
    assert accents and '差回' in accents[0] and accents[0] in {'出差回来', '刚从美国出差回来'}, accents


def test_the_same_highlight_does_not_light_twice_in_a_clip():
    cues = [
        {'start': 0, 'end': 2.0, 'text': '我只给了他们24小时', 'original': 'I gave them 24 hours', 'emphasis': '24小时'},
        {'start': 8, 'end': 10.0, 'text': '真的就24小时', 'original': 'literally in 24 hours', 'emphasis': '24小时'},
        {'start': 16, 'end': 18.0, 'text': '他们见到了总统', 'original': 'they met the president', 'emphasis': '总统'},
    ]
    accents = _accents(cues, [])
    assert accents.count('24小时') == 1, accents
    assert '总统' in accents
