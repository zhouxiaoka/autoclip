"""Template packaging: model output validation, fallbacks and privacy boundary (no model calls)."""
import pytest

from backend.services.platform_strategy import platform_strategy
from backend.services.studio import packaging

LINES = [
    {'start': 10.0, 'end': 12.0, 'text': 'Paul used to say this.'},
    {'start': 12.0, 'end': 15.0, 'text': 'A good investor is like a flight instructor.'},
    {'start': 15.0, 'end': 18.0, 'text': 'Garry, you brought the same energy to founders.'},
]
DRAFT = {'title': 'Great investors are flight instructors', 'hook': ''}


def good_response(**overrides):
    body = {
        'lines': [{'id': 0, 'text': 'Paul 以前常说'}, {'id': 1, 'text': '好的投资人像飞行教练'},
                  {'id': 2, 'text': 'Garry，你把同样的能量带给了创始人'}],
        'title_lines': ['好的投资人', '应该像飞行教练'], 'accent_line': 1,
        'segments': [{'from': 0, 'to': 1, 'text': 'Paul 以前常说，好的投资人像飞行教练'}, {'from': 2, 'to': 2, 'text': 'Garry，你把同样的能量带给了创始人'}],
        'speakers': [{'line': 0, 'name': 'Sam Altman', 'role': 'OpenAI CEO'}, {'line': 2, 'name': 'Garry Tan', 'role': 'YC 总裁'}],
        'tags': [{'line': 1, 'text': '飞行教练'}], 'highlights': [],
    }
    segments = overrides.get('segments')
    if segments and all(item.get('from') == item.get('to') for item in segments):
        body['lines'] = [{'id': item['from'], 'text': item['text']} for item in segments]
    return {**body, **overrides}


def test_interview_packaging_translates_cues_without_retiming_them():
    sent = []
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), known_names='Sam Altman: Never a Better Time',
                                       call=lambda prompt, data: sent.append(data) or good_response())
    assert result['template'] == 'interview_zh' and result['source_language'] == 'en' and not result['fallback']
    first, second, third = result['cues']
    assert (first['start'], first['end']) == (10.0, 12.0) and first['text'] == 'Paul 以前常说'
    assert first['original'] == LINES[0]['text']
    assert (second['start'], second['end']) == (12.0, 15.0)
    assert (third['start'], third['end']) == (15.0, 18.0)
    assert result['translation_status'] == 'complete'
    assert [s['name'] for s in result['speakers']] == ['Sam Altman', 'Garry Tan']
    assert result['tags'] == [{'at': 12.2, 'text': '飞行教练'}]
    assert [line['text'] for data in sent if data.get('task') == 'translate_captions' for line in data['lines']] == [line['text'] for line in LINES]  # only the draft's rows


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
def test_decoration_segments_cannot_invalidate_completed_translation(bad):
    def call(prompt, data):
        if data.get('task') == 'translate_captions':
            return {'lines': [{'id': row['id'], 'text': f"第{row['id']}句"} for row in data['lines']]}
        return good_response(**bad)
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=call)
    assert result['translation_status'] == 'complete'
    assert [c['text'] for c in result['cues']] == ['第0句', '第1句', '第2句']
    broken = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: {'lines': None})
    assert [c['text'] for c in broken['cues']] == [l['text'] for l in LINES]  # readable original captions survive rejected translation


def test_an_english_platform_never_shows_a_chinese_fallback_title():
    def unavailable(*_):
        raise ValueError('文字模型不可用')
    result = packaging.build_packaging({'title': '好的投资人像飞行教练', 'hook': ''}, LINES, platform_strategy('tiktok'), call=unavailable)
    assert result['title_lines'] == [] and all(not packaging.CJK.search(c['text']) for c in result['cues'])


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
    assert result['highlights'] == [{'at': 12.0, 'text': 'instructor'}]  # anchored on the row that says it
    assert result['tags'] == []  # commentary tags are interview-only


def test_burned_captions_in_the_audience_language_skip_our_track():
    zh_lines = [{'start': 0.0, 'end': 3.0, 'text': '这是一个中文字幕，内容比较长一些'}]
    result = packaging.build_packaging(DRAFT, zh_lines, platform_strategy('douyin'), burned=True,
                                       call=lambda *_: good_response(segments=[{'from': 0, 'to': 0, 'text': '这是一个中文字幕'}]))
    assert result['burned_captions'] is True and result['cues'] == []


def test_burned_foreign_captions_still_get_audience_captions_without_the_original():
    ja_lines = [{'start': 0.0, 'end': 3.0, 'text': 'ゲーム業界に来たという事でございます'}]
    response = good_response(segments=[{'from': 0, 'to': 0, 'text': '所以我才进了游戏行业'}])
    result = packaging.build_packaging(DRAFT, ja_lines, platform_strategy('douyin'), burned=True, call=lambda *_: response)
    assert result['source_language'] == 'other'
    assert [c['text'] for c in result['cues']] == ['所以我才进了游戏行业'] and result['cues'][0]['original'] == ''


@pytest.mark.parametrize('lines, burned_language, platform, expect', [
    # Chinese talk with Chinese captions in the picture (TIM × 罗永浩).
    ([{'start': 0.0, 'end': 3.0, 'text': '这是一个中文字幕，内容比较长一些'}], 'zh', 'douyin', None),
    ([{'start': 0.0, 'end': 3.0, 'text': '这是一个中文字幕，内容比较长一些'}], 'zh', 'tiktok', 'This is a subtitle'),
    # Japanese talk with English captions in the picture (Kojima × WIRED).
    ([{'start': 0.0, 'end': 3.0, 'text': 'ゲーム業界に来たという事でございます'}], 'en', 'tiktok', None),
    ([{'start': 0.0, 'end': 3.0, 'text': 'ゲーム業界に来たという事でございます'}], 'en', 'douyin', '所以我才进了游戏行业'),
])
def test_captions_are_added_only_when_the_audience_cannot_read_the_burned_ones(lines, burned_language, platform, expect):
    zh = platform == 'douyin'
    sent = []
    response = good_response(segments=[{'from': 0, 'to': 0, 'text': '所以我才进了游戏行业' if zh else 'This is a subtitle'}],
                             title_lines=['好的投资人'] if zh else ['Great investors'])
    result = packaging.build_packaging(DRAFT, lines, platform_strategy(platform), burned=True, burned_language=burned_language,
                                       call=lambda _p, data: sent.append(data) or response)
    assert [c['text'] for c in result['cues']] == ([expect] if expect else [])
    assert (sent[0].get('task') == 'translate_captions') is bool(expect)  # no translation when not shown


def test_japanese_is_not_mistaken_for_chinese():
    assert packaging.source_language(['最高傑作は何ですか', '今後多分映画を超えるものになる']) == 'other'


def test_prompt_rejects_generic_praise_tags():
    assert '禁止' in packaging.PROMPT and '逻辑清晰' in packaging.PROMPT


def test_long_english_sentences_and_titles_survive_validation():
    long_text = ' '.join(['token value asymmetry will redefine the economics of every model we ship'] * 5)  # ~370 chars
    response = good_response(title_lines=["API pricing won't die—token value asymmetry will redefine AGI economics"],
                             segments=[{'from': 0, 'to': 2, 'text': long_text}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('tiktok'), call=lambda *_: response)
    assert result['fallback'] is False and [c['text'] for c in result['cues']] == [l['text'] for l in LINES]  # same language: source rows
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
    many = [{'start': float(i), 'end': float(i + 1), 'text': f'line {i} of a long monologue'} for i in range(20)]
    response = good_response(segments=[{'from': 0, 'to': 19, 'text': '一大段合在一起的译文'}])
    result = packaging.build_packaging(DRAFT, many, platform_strategy('douyin'), call=lambda *_: response)
    assert result['fallback'] is True


def test_source_language_detection():
    assert packaging.source_language(['这是一个中文字幕，内容比较长一些']) == 'zh'
    assert packaging.source_language(['This is an English subtitle line with words']) == 'en'


def test_the_content_mood_picks_a_matching_look_that_is_stable_per_clip():
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: good_response(mood='bold'))
    palettes, styles = packaging.MOOD_LOOKS['bold']
    assert result['mood'] == 'bold' and result['palette'] in palettes and result['style'] in styles['interview_zh']
    again = packaging.build_packaging(DRAFT, LINES, platform_strategy('xiaohongshu'), call=lambda *_: good_response(mood='bold'))
    assert (again['palette'], again['style']) == (result['palette'], result['style'])  # same clip, same look
    looks = {tuple(packaging.choose_look('podcast_en', 'calm', f'{n}.0-{n + 60}.0').values()) for n in range(40)}
    assert len(looks) > 2  # different clips vary within the mood


def test_an_unknown_mood_keeps_the_golden_default_look():
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: good_response(mood='angry'))
    assert (result['mood'], result['palette'], result['style']) == (None, None, None)


def test_rejected_translation_is_repaired_before_decoration():
    sent = []
    replies = iter([{'lines': []}, good_response(), good_response(), good_response(), good_response()])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda _, data: sent.append(data) or next(replies))
    assert not result['fallback'] and len(result['cues']) == 3
    assert 'repair' not in sent[0] and 'repair' in sent[1]
    assert sent[-1]['task'] == 'decorate_captions'


def test_titles_are_plain_text_in_the_audience_language():
    clean = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'),
                                      call=lambda *_: good_response(title_lines=['*好的*投资人', 'R&amp;D 像飞行教练']))
    assert clean['title_lines'] == ['好的投资人', 'R&D 像飞行教练']
    japanese = packaging.build_packaging({'title': '好的投资人像飞行教练', 'hook': ''}, LINES, platform_strategy('douyin'),
                                         call=lambda *_: good_response(title_lines=['最高検査は最新作']))
    assert japanese['title_lines'] == ['好的投资人像飞行教练']


def test_fallback_titles_keep_whole_clauses():
    title = packaging._fallback_title({'hook': '《死亡搁浅》不是先有玩法再讲故事：主题即机制，故事与玩法同时诞生'}, 'zh')
    assert title == ['《死亡搁浅》不是先有玩法', '再讲故事：主题即机制']  # not "…主题即机制，故"
    assert packaging._fallback_title({'hook': 'Starting a Startup *Is* Your Move'}, 'en') == ['Starting a Startup Is Your Move']


def test_a_batch_does_not_repeat_the_last_palettes_when_the_mood_allows():
    palettes, _ = packaging.MOOD_LOOKS['bold']
    for seed in ('1.0-60.0', '2.0-61.0', '3.0-62.0'):
        assert packaging.choose_look('interview_zh', 'bold', seed, avoid=(palettes[0],))['palette'] == palettes[1]


def test_failed_translation_preserves_source_captions_instead_of_silent_video():
    replies = iter([{'lines': []}, {'lines': ['没有编号的译文']}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=lambda *_: next(replies))
    assert result['fallback']
    assert [c['text'] for c in result['cues']] == [line['text'] for line in LINES]
    assert [(c['start'], c['end']) for c in result['cues']] == [(l['start'], l['end']) for l in LINES]
    assert all(not c['original'] for c in result['cues'])


def test_translation_recovery_uses_row_ids_and_retains_bilingual_source():
    sent = []
    def call(prompt, data):
        sent.append(data)
        if data.get('task') == 'translate_captions':
            return {'lines': [{'id': i, 'text': f'译文{i}'} for i in (2, 0, 1)]}
        return good_response(segments=[{'from': 0, 'to': 0, 'text': '第一句'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=call)
    assert not result['fallback'] and len(sent) == 4
    assert [c['text'] for c in result['cues']] == ['译文0', '译文1', '译文2']
    assert [c['original'] for c in result['cues']] == [line['text'] for line in LINES]
    assert [row['id'] for data in sent[:-1] for row in data['lines']] == [0, 1, 2]
    assert sent[-1]['task'] == 'decorate_captions'


def test_duplicate_translation_ids_cannot_replace_a_missing_caption():
    def call(prompt, data):
        if data.get('task') == 'translate_captions':
            return {'lines': [{'id': 0, 'text': '重复一'}, {'id': 0, 'text': '重复二'}, {'id': 2, 'text': '第三句'}]}
        return good_response(segments=None)
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=call)
    assert [c['text'] for c in result['cues']] == [LINES[0]['text'], LINES[1]['text'], '第三句']
    assert result['translation_status'] == 'partial' and result['translated_rows'] == 1


def test_failed_english_translation_does_not_burn_unreadable_chinese():
    zh = [{'start': 0., 'end': 2., 'text': '这是一段原始中文内容，需要翻译'}]
    result = packaging.build_packaging(DRAFT, zh, platform_strategy('tiktok'), call=lambda *_: {})
    assert result['fallback'] and result['cues'] == []


def test_negligible_tail_of_a_previous_subtitle_is_not_replayed():
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:02,000', 'text': 'Previous question?'},
               {'start_time': '00:00:02,010', 'end_time': '00:00:04,000', 'text': 'The answer starts here.'}]
    lines = packaging.draft_lines(entries, [{'start': 1.93, 'end': 4.}])
    assert [l['text'] for l in lines] == ['The answer starts here.']


@pytest.mark.parametrize('edge', ['start', 'end'])
def test_sentence_cut_inside_one_srt_row_trims_the_caption_text_as_well(edge):
    text = 'Earlier thought. The next complete thought. But now we can'
    offset = text.index(' But now')
    cut = 10. + 8. * offset / len(text)
    entries = [{'start_time': '00:00:10,000', 'end_time': '00:00:18,000', 'text': text}]
    scene = {'start': 10., 'end': cut + .2} if edge == 'end' else {'start': cut + .1, 'end': 18.}
    lines = packaging.draft_lines(entries, [scene])
    assert ' '.join(row['text'] for row in lines) == (text[:offset] if edge == 'end' else text[offset:].strip())


def test_chinese_fallback_title_breaks_on_a_clause_not_inside_a_word():
    assert packaging._fallback_title({'title': '我们曾掉队，现在执行力全球最强'}, 'zh') == ['我们曾掉队，', '现在执行力全球最强']


def test_unchanged_english_response_cannot_be_claimed_as_a_chinese_translation():
    def call(prompt, data):
        if data.get('task') == 'translate_captions':
            return {'lines': [line['text'] for line in LINES]}
        return good_response(segments=[{'from': 0, 'to': 2, 'text': 'Unchanged English source words.'}])
    result = packaging.build_packaging(DRAFT, LINES, platform_strategy('douyin'), call=call)
    assert result['fallback'] and all(not c['original'] for c in result['cues'])
    assert [c['text'] for c in result['cues']] == [line['text'] for line in LINES]


def test_person_names_from_mixed_title_survive_malformed_group_and_row_translation():
    draft = {'title': 'Fiji离开后，我和Greg配合很好', 'hook': ''}
    lines = [{'start': 0., 'end': 2., 'text': 'Fiji is very hard to replace.'},
             {'start': 2., 'end': 4., 'text': 'Greg and I work well together.'}]
    wrong = ['斐济很难被替代。', '我和格雷格配合很好。']
    calls = []
    def call(prompt, data):
        calls.append(data)
        if data.get('task') == 'translate_captions':
            return {'lines': [{'id': i, 'text': text} for i, text in enumerate(wrong)]}
        return good_response(title_lines=['斐济离开后', '新搭档配合很好'],
                             segments=[{'from': i, 'to': i, 'text': text} for i, text in enumerate(wrong)])
    result = packaging.build_packaging(draft, lines, platform_strategy('douyin'), call=call)
    assert result['fallback'] and len(calls) == 4
    assert [cue['text'] for cue in result['cues']] == [line['text'] for line in lines]
    assert all(not cue['original'] for cue in result['cues'])
    assert all(name in ''.join(result['title_lines']) for name in ('Fiji', 'Greg'))


def test_correct_captions_keep_original_names_when_model_rewrites_title_entities():
    draft = {'title': 'Fiji离开后，我和Greg配合很好', 'hook': ''}
    lines = [{'start': 0., 'end': 2., 'text': 'Fiji and Greg worked here.'}]
    result = packaging.build_packaging(draft, lines, platform_strategy('douyin'),
        call=lambda *_: good_response(title_lines=['斐济离开后', '格雷格配合很好'],
                                      segments=[{'from': 0, 'to': 0, 'text': 'Fiji 和 Greg 在这里共事。'}]))
    assert not result['fallback'] and result['cues'][0]['text'] == 'Fiji 和 Greg 在这里共事。'
    assert all(name in ''.join(result['title_lines']) for name in ('Fiji', 'Greg'))
    assert '斐济' not in ''.join(result['title_lines'])


def test_full_source_names_are_protected_even_without_a_mixed_language_title():
    lines = [{'start': 0., 'end': 5., 'text': 'Dana K. Morgan played Casey Reed in Winter Garden.'}]
    terms = packaging._protected_terms({'title': 'An interview'}, lines, 'zh')
    assert terms == ['Dana K. Morgan', 'Casey Reed', 'Winter Garden']
    with pytest.raises(ValueError):
        packaging._check_preserved_terms(lines[0]['text'], 'Dana Kelly Morgan出演了Casey Reed，作品是Winter Garden。', terms)


def test_name_translation_can_recover_with_one_bounded_packaging_retry():
    draft = {'title': 'Fiji离开后，我和Greg配合很好', 'hook': ''}
    lines = [{'start': 0., 'end': 2., 'text': 'Fiji and Greg worked here.'}]
    replies = iter([good_response(segments=[{'from': 0, 'to': 0, 'text': '斐济和格雷格在这里共事。'}]),
                    good_response(title_lines=['Fiji离开后', '我和Greg配合很好'],
                                  segments=[{'from': 0, 'to': 0, 'text': 'Fiji 和 Greg 在这里共事。'}]),
                    good_response(title_lines=['Fiji离开后', '我和Greg配合很好'])])
    calls = []
    result = packaging.build_packaging(draft, lines, platform_strategy('douyin'),
                                      call=lambda _, data: calls.append(data) or next(replies))
    assert len(calls) == 3 and not result['fallback']
    assert result['cues'][0]['text'] == 'Fiji 和 Greg 在这里共事。'


def test_an_omitted_speaker_comes_from_the_listing_title_not_the_cover_line():
    """Street nameplate: the public title names the guest when the model leaves speakers empty."""
    lines = [
        {'start': 0.0, 'end': 4.0, 'text': 'You said we did not have our best last 12 months'},
        {'start': 9.0, 'end': 14.0, 'text': 'Best 12 months yet'},
    ]

    def call(_prompt, _data):
        return {
            'lines': [{'id': 0, 'text': '你说我们过去没有最好的那12个月'}, {'id': 1, 'text': '未来12个月将是最佳'}],
            'title_lines': ['未来十二个月将是最佳'], 'accent_line': 0,
            'segments': [
                {'from': 0, 'to': 0, 'text': '你说我们过去没有最好的那12个月'},
                {'from': 1, 'to': 1, 'text': '未来十二个月将是最佳'},
            ],
            'speakers': [], 'tags': [], 'highlights': [], 'marks': [],
        }

    listed = packaging.build_packaging(
        {'title': '', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='Sam Altman on Astra, AGI, and the future of OpenAI Sources Podcast', call=call,
    )
    assert [item['name'] for item in listed['speakers']] == ['Sam Altman']
    assert listed['speakers'][0]['role'] == ''
    assert '未来十二个月' not in listed['speakers'][0]['name']

    colon = packaging.build_packaging(
        {'title': '', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='Sam Altman: Never a Better Time YC', call=call,
    )
    assert [item['name'] for item in colon['speakers']] == ['Sam Altman']

    chinese = packaging.build_packaging(
        {'title': '', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='黄仁勋：五层蛋糕', call=call,
    )
    assert [item['name'] for item in chinese['speakers']] == ['黄仁勋']

    topic = packaging.build_packaging(
        {'title': '未来十二个月将是最佳', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='Sources Podcast', call=call,
    )
    assert topic['speakers'] == []
    assert topic['title_lines'] == ['未来十二个月将是最佳']


def test_title_term_is_not_inferred_from_an_unrelated_source_word():
    result = packaging.build_packaging({'title': 'Greg谈合作', 'hook': ''},
        [{'start': 0., 'end': 2., 'text': 'We are gregarious and cooperative.'}], platform_strategy('douyin'),
        call=lambda *_: good_response(title_lines=['友善与合作'],
                                      segments=[{'from': 0, 'to': 0, 'text': '我们很友善，也乐于合作。'}]))
    assert not result['fallback'] and result['title_lines'] == ['友善与合作']
