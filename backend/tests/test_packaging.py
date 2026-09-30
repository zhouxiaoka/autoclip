"""Template packaging: model output validation, fallbacks and privacy boundary (no model calls)."""
import pytest

from backend.services.platform_strategy import platform_strategy
from backend.services.studio import packaging

LINES = [
    {'start': 10.0, 'end': 12.0, 'text': 'Paul had this thing he used to say'},
    {'start': 12.0, 'end': 15.0, 'text': 'a good investor is like a flight instructor'},
    {'start': 15.0, 'end': 18.0, 'text': 'Garry, you brought the same energy to founders'},
]
DRAFT = {'title': 'Great investors are flight instructors', 'hook': ''}


def good_response(**overrides):
    body = {
        'title_lines': ['好的投资人', '应该像飞行教练'], 'accent_line': 1,
        'translations': ['Paul 以前常说', '好的投资人像飞行教练', 'Garry，你把同样的能量带给了创始人'],
        'speakers': [{'line': 0, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}, {'line': 2, 'name': 'Garry Tan', 'role': 'YC 总裁'}],
        'tags': [{'line': 1, 'text': '飞行教练'}], 'highlights': [],
    }
    return {**body, **overrides}


def test_interview_packaging_translates_every_line_and_keeps_the_original():
    sent = []
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), known_names='Sam Altman: Never a Better Time',
                                       call=lambda prompt, data: sent.append(data) or good_response())
    assert result['template'] == 'interview_zh' and result['source_language'] == 'en' and not result['fallback']
    assert [c['text'] for c in result['cues']][1] == '好的投资人像飞行教练'
    assert result['cues'][1]['original'] == LINES[1]['text']
    assert [s['name'] for s in result['speakers']] == ['Sam Altman', 'Garry Tan']
    assert result['tags'] == [{'at': 12.2, 'text': '飞行教练'}]
    assert [line['text'] for line in sent[0]['lines']] == [line['text'] for line in LINES]  # only the draft's rows


def test_names_not_seen_in_subtitles_or_listing_are_dropped():
    response = good_response(speakers=[{'line': 0, 'name': 'Elon Musk', 'role': 'CEO'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: response)
    assert result['speakers'] == []


@pytest.mark.parametrize('bad', [
    {'translations': ['only one']},
    {'translations': ['a', 'b', 'x' * 300]},
])
def test_malformed_translations_fall_back_to_source_captions(bad):
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: good_response(**bad))
    assert result['fallback'] is True
    assert [c['text'] for c in result['cues']] == [line['text'] for line in LINES]


def test_model_unavailable_never_blocks_output():
    def unavailable(*_):
        raise ValueError('文字模型不可用')
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), call=unavailable)
    assert result['fallback'] is True and result['title_lines'] == ['Great investors are flight', 'instructors']


def test_podcast_keeps_english_and_only_highlights_words_in_the_line():
    response = good_response(title_lines=['Great investors are flight instructors'], translations=[],
                             highlights=[{'line': 1, 'word': 'instructor'}, {'line': 0, 'word': 'nonexistent'}], tags=[{'line': 0, 'text': 'x'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), known_names='Sam Altman', call=lambda *_: response)
    assert result['template'] == 'podcast_en' and result['cues'][0]['text'] == LINES[0]['text']
    assert result['highlights'] == [{'at': 12.0, 'text': 'instructor'}]
    assert result['tags'] == []  # commentary tags are interview-only


def test_burned_captions_skip_our_caption_track():
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), burned=True, call=lambda *_: good_response(translations=[]))
    assert result['burned_captions'] is True and result['cues'] == []


def test_source_language_detection():
    assert packaging.source_language(['这是一个中文字幕，内容比较长一些']) == 'zh'
    assert packaging.source_language(['This is an English subtitle line with words']) == 'en'
