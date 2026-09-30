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
        'segments': [{'from': 0, 'to': 1, 'text': 'Paul 以前常说，好的投资人像飞行教练'}, {'from': 2, 'to': 2, 'text': 'Garry，你把同样的能量带给了创始人'}],
        'speakers': [{'line': 0, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}, {'line': 2, 'name': 'Garry Tan', 'role': 'YC 总裁'}],
        'tags': [{'line': 1, 'text': '飞行教练'}], 'highlights': [],
    }
    return {**body, **overrides}


def test_interview_packaging_regroups_lines_into_translated_sentences():
    sent = []
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), known_names='Sam Altman: Never a Better Time',
                                       call=lambda prompt, data: sent.append(data) or good_response())
    assert result['template'] == 'interview_zh' and result['source_language'] == 'en' and not result['fallback']
    first, second = result['cues']
    assert (first['start'], first['end']) == (10.0, 15.0) and first['text'] == 'Paul 以前常说，好的投资人像飞行教练'
    assert first['original'] == f"{LINES[0]['text']} {LINES[1]['text']}"
    assert (second['start'], second['end']) == (15.0, 18.0)
    assert [s['name'] for s in result['speakers']] == ['Sam Altman', 'Garry Tan']
    assert result['tags'] == [{'at': 12.2, 'text': '飞行教练'}]
    assert [line['text'] for line in sent[0]['lines']] == [line['text'] for line in LINES]  # only the draft's rows


def test_names_not_seen_in_subtitles_or_listing_are_dropped():
    response = good_response(speakers=[{'line': 0, 'name': 'Elon Musk', 'role': 'CEO'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: response)
    assert result['speakers'] == []


@pytest.mark.parametrize('bad', [
    {'segments': [{'from': 0, 'to': 0, 'text': 'a'}]},                                         # does not cover every line
    {'segments': [{'from': 0, 'to': 0, 'text': 'a'}, {'from': 2, 'to': 2, 'text': 'c'}]},      # gap
    {'segments': [{'from': 0, 'to': 2, 'text': 'x' * 700}]},                                   # too long
    {'segments': None},
])
def test_malformed_segments_fall_back_to_source_captions(bad):
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: good_response(**bad))
    assert result['fallback'] is True
    assert [c['text'] for c in result['cues']] == [line['text'] for line in LINES]


def test_model_unavailable_never_blocks_output_and_keeps_english_titles_whole():
    def unavailable(*_):
        raise ValueError('文字模型不可用')
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=unavailable)
    assert result['fallback'] is True and result['title_lines'] == ['Great investors are flight', 'instructors']


def test_podcast_keeps_english_and_only_highlights_words_in_the_segment():
    response = good_response(title_lines=['Great investors are flight instructors'],
                             segments=[{'from': 0, 'to': 1, 'text': 'Paul used to say a good investor is like a flight instructor'},
                                       {'from': 2, 'to': 2, 'text': 'Garry, you brought the same energy to founders'}],
                             highlights=[{'line': 1, 'word': 'instructor'}, {'line': 2, 'word': 'nonexistent'}], tags=[{'line': 0, 'text': 'x'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), known_names='Sam Altman', call=lambda *_: response)
    assert result['template'] == 'podcast_en' and result['cues'][0]['original'] == ''
    assert result['highlights'] == [{'at': 10.0, 'text': 'instructor'}]
    assert result['tags'] == []  # commentary tags are interview-only


def test_burned_captions_skip_our_caption_track():
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), burned=True, call=lambda *_: good_response())
    assert result['burned_captions'] is True and result['cues'] == []


def test_prompt_rejects_generic_praise_tags():
    assert '禁止' in packaging.PROMPT and '逻辑清晰' in packaging.PROMPT


def test_long_english_sentences_and_titles_survive_validation():
    long_text = ' '.join(['token value asymmetry will redefine the economics of every model we ship'] * 5)  # ~370 chars
    response = good_response(title_lines=["API pricing won't die—token value asymmetry will redefine AGI economics"],
                             segments=[{'from': 0, 'to': 2, 'text': long_text}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), call=lambda *_: response)
    assert result['fallback'] is False and result['cues'][0]['text'] == long_text
    assert len(result['title_lines']) == 2 and all(len(line) <= 40 for line in result['title_lines'])
    assert ' '.join(result['title_lines']).startswith("API pricing won't die")


def test_same_language_keeps_the_package_when_segments_are_lumped():
    lumped = good_response(title_lines=['Great investors are flight instructors'],
                           segments=[{'from': 0, 'to': 0, 'text': 'a'}],  # does not cover every row
                           highlights=[{'line': 1, 'word': 'instructor'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), call=lambda *_: lumped)
    assert result['fallback'] is False and [c['text'] for c in result['cues']] == [l['text'] for l in LINES]
    assert result['title_lines'] == ['Great investors are flight instructors']
    assert result['highlights'] == [{'at': 12.0, 'text': 'instructor'}]


def test_paragraph_sized_segments_are_rejected_for_translation():
    many = [{'start': float(i), 'end': float(i + 1), 'text': f'line {i} of a long monologue'} for i in range(10)]
    response = good_response(segments=[{'from': 0, 'to': 9, 'text': '一大段合在一起的译文'}])
    result = packaging.build_packaging(DRAFT, many, platform_strategy('douyin'), call=lambda *_: response)
    assert result['fallback'] is True


def test_source_language_detection():
    assert packaging.source_language(['这是一个中文字幕，内容比较长一些']) == 'zh'
    assert packaging.source_language(['This is an English subtitle line with words']) == 'en'
