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


def test_a_shorter_form_of_a_lit_phrase_stays_plain():
    # dad_suit lit 买了一套 then lit 一套 again on the next mention.
    cues = [
        {'start': 0, 'end': 2.0, 'text': '结果他跑出去买了一套', 'original': 'he ran out and bought one', 'emphasis': '买了一套'},
        {'start': 8, 'end': 10.0, 'text': '我妈也买了一套', 'original': 'my mom got a new dress', 'emphasis': '一套'},
        {'start': 16, 'end': 18.0, 'text': '派到了纽约', 'original': 'sent to New York', 'emphasis': '纽约'},
        {'start': 24, 'end': 26.0, 'text': '美国纽约', 'original': 'New York, USA', 'emphasis': '纽约'},
    ]
    accents = _accents(cues, [])
    assert accents.count('买了一套') + accents.count('一套') == 1, accents
    assert accents.count('纽约') == 1, accents


def test_words_emphasis_matches_the_accent_marks():
    cues = [
        {'start': 0, 'end': 2.0, 'text': '派到了纽约', 'original': 'sent to New York', 'emphasis': '纽约'},
        {'start': 8, 'end': 10.0, 'text': '美国纽约', 'original': 'New York, USA', 'emphasis': '纽约'},
    ]
    packaging = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['话题'], deck='Deck',
        cues=cues,
    )
    fill = build_fill(packaging, 20, template='editorial')
    lit = [word['emphasis'] for word in fill['words'] if word.get('emphasis')]
    assert lit == ['纽约'], lit
