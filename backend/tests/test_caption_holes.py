"""A spoken line is never left without its caption because a longer line took its share of text."""
from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import _transcript_rows, build_fill, cue_lines

ROWS = [
    (85.02, 87.68, 'All the things that he bought at the airport, brought it back.', ''),
    (88.90, 90.72, 'He brought chocolate.', ''),
    (90.90, 94.16, 'He brought... you know that cheese that you have in a tube back in the old days?', ''),
    (94.27, 97.13, 'And he brought back all kinds of strange things.', ''),
]
TEXT = '他把在机场买的东西全带回来了，带了巧克力，还有以前那种管装奶酪，各种稀奇古怪的东西。'
# dad_suit e: the edit trims the pause after the first line, so the cue crosses a cut.
SCENES = [Scene(id='a', start=85.0, end=88.0), Scene(id='b', start=88.6, end=98.0)]


def _spoken(template, text=TEXT):
    packaging = Packaging(
        version=2, template=template, audience_language='zh', title_lines=['话题'], deck='Dad',
        cues=[{'start': 85.02, 'end': 97.13, 'text': text, 'original': ' '.join(row[2] for row in ROWS)}],
    )
    fill = build_fill(packaging, 13, template=template, scenes=SCENES, transcript=ROWS)
    lines = cue_lines(85.02, 97.13, _transcript_rows(ROWS), SCENES)
    words = sorted((word['start_frame'] / 30, word['end_frame'] / 30, word['text']) for word in fill['words'])
    return words, [(line[2], line[3]) for line in lines]


def _covered(words, lo, hi, needle=''):
    return sum(max(0.0, min(hi, t1) - max(lo, t0)) for t0, t1, text in words if needle in text)


def test_every_spoken_line_shows_its_own_clause():
    # dad_suit e O2630-2727: 3.2s of "He brought chocolate." with no caption.
    for template in ('editorial', 'street'):
        words, lines = _spoken(template)
        assert len(lines) == 4
        for lo, hi in lines:
            assert _covered(words, lo, hi) >= 0.8 * (hi - lo), (template, lo, words)
        lo, hi = lines[1]
        assert _covered(words, lo, hi, '巧克力') >= 0.8 * (hi - lo), (template, lines, words)
        lo, hi = lines[0]
        assert _covered(words, lo, hi, '带回来了') > 0.5, (template, lines, words)


def test_without_clause_marks_a_short_line_still_gets_a_piece():
    words, lines = _spoken('editorial', TEXT.replace('，', '').replace('。', ''))
    lo, hi = lines[1]
    assert _covered(words, lo, hi) >= 0.8 * (hi - lo), (lines, words)
