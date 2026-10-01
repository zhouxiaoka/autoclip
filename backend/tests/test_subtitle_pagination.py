"""Long ASR paragraphs must fit the frame and retain their source timeline when clipped."""
import pytest

from backend.pipeline.quality import to_seconds, to_srt_time
from backend.services.publish_export import slice_srt, subtitle_line_limit
from backend.services.studio.caption_layout import timed_screens, width

PARAGRAPH = ('How teams at OpenAI use dots via a fictional music app we are calling Blossom. '
             'You can add them to Slack and orchestrate your codex. ') * 12


def rows(body):
    for block in body.strip().split('\n\n'):
        _, clock, *text = block.splitlines()
        start, end = clock.split(' --> ')
        yield to_seconds(start), to_seconds(end), text


@pytest.mark.parametrize('w,h,style', [(1920,1080,'clean'), (1920,1080,'bold'),
                                     (1080,1920,'accent'), (1080,1920,'bold'), (1080,1080,'box')])
def test_long_paragraph_is_paginated_without_dropping_text(w, h, style):
    limit = subtitle_line_limit(w, h, style)
    body = slice_srt([{'start_time': '00:09:33,520', 'end_time': '00:11:08,080', 'text': PARAGRAPH}],
                     573.52, 668.08, limit)
    screens = list(rows(body))
    assert len(screens) > 10
    assert ''.join(''.join(text).replace(' ', '') for _, _, text in screens) == PARAGRAPH.replace(' ', '')
    for start, end, text in screens:
        assert 0 <= start < end <= 94.56
        assert len(text) <= 2
        assert all(width(line) <= limit + 1e-6 for line in text)
    assert screens[0][0] == 0 and screens[-1][1] == 94.56


def test_clipping_selects_source_pages_instead_of_replaying_the_entire_paragraph():
    text = ' '.join(f'word{i:03}' for i in range(100))
    pages = timed_screens(text, 10, 110, 24)
    start, end = pages[4][0] + .1, pages[6][1] - .1
    body = slice_srt([{'start_time': to_srt_time(10), 'end_time': to_srt_time(110), 'text': text}], start, end, 24)
    actual = list(rows(body))
    assert len(actual) == 3
    assert body.splitlines()[2:] and 'word000' not in body and 'word099' not in body
    expected = ''.join(page[2].replace('\\N', '').replace(' ', '') for page in pages[4:7])
    assert ''.join(''.join(lines).replace(' ', '') for _, _, lines in actual) == expected
    assert actual[0][0] == 0 and abs(actual[-1][1] - (end - start)) < .002


def test_larger_fonts_get_a_smaller_width_budget():
    assert subtitle_line_limit(1920, 1080, 'bold') < subtitle_line_limit(1920, 1080, 'clean')
    assert subtitle_line_limit(1080, 1920, 'bold') < subtitle_line_limit(1080, 1920, 'clean')


def test_invalid_or_submillisecond_source_cues_cannot_emit_zero_length_subtitles():
    assert not slice_srt([{'start_time':'00:00:01,000','end_time':'00:00:01,000','text':PARAGRAPH}], 0, 2, 24)
    body = slice_srt([{'start_time':'00:00:00,000','end_time':'00:00:00,001','text':PARAGRAPH}], 0, .001, 24)
    assert all(end > start for start, end, _ in rows(body))
