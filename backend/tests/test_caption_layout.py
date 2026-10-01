"""Golden layout contract: a caption screen never exceeds two lines (vertical outputs)."""
import pytest

from backend.services.studio import caption_layout as cl

LONG_ZH = '这些年把同样的能量，带给了无数创始人，而且这种手把手的方式一直延续到今天，影响了整整一代人'
LONG_EN = 'and brought exactly the same energy to a great many YC founders over the years, and that hands-on style shaped a whole generation'


@pytest.mark.parametrize('text, limit', [(LONG_ZH, 15), (LONG_EN, 16), ('Paul 以前常说', 15), ('短句', 15)])
def test_every_screen_has_at_most_two_lines_within_the_width(text, limit):
    screens = cl.split_screens(text, limit)
    assert screens and ''.join(s.replace('\\N', '').replace(' ', '') for s in screens) == text.replace(' ', '')
    for screen in screens:
        assert cl.line_count(screen) <= 2
        assert all(cl.width(line) <= limit + 1e-6 for line in screen.split('\\N'))


def test_line_breaks_prefer_punctuation_and_natural_joints():
    lines = cl.lines_for(LONG_ZH, 15)
    assert lines[0].endswith('，') and lines[1].endswith('，')
    assert '延\\N续' not in '\\N'.join(lines) and not any(line.endswith('延') for line in lines)


def test_a_long_original_under_a_short_caption_never_exceeds_two_lines():
    original = ('about my preferences and tastes and the different trade-offs we have and just over the course of '
                'many months building up this understanding of what works for our audience and what does not')
    screens = cl.timed_screens('的工作部分在于持续学习观众的偏好、我的个人审美与取舍，', 0, 6, 15, original, 25.5)
    assert len(screens) >= 2
    for _, _, text, orig in screens:
        assert cl.line_count(text) <= 2 and cl.line_count(orig) <= 2
        assert all(cl.width(line) <= 25.5 + 1e-6 for line in orig.split('\\N'))


def test_screens_share_time_by_width_and_keep_the_original_in_step():
    screens = cl.timed_screens(LONG_ZH, 10.0, 16.0, 15, LONG_EN, 25)
    assert len(screens) >= 2
    assert screens[0][0] == 10.0 and abs(screens[-1][1] - 16.0) < 1e-6
    assert all(a < b for a, b, _, _ in screens)
    assert all(cl.line_count(original) <= 2 for *_, original in screens)
    assert ' '.join(o.replace('\\N', ' ') for *_, o in screens).split() == LONG_EN.split()
