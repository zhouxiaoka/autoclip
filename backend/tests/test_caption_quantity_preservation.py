import pytest

from backend.services.studio.caption_translation import translate


@pytest.mark.parametrize(('source', 'target', 'audience'), [
    ('每周一次，普通档为6万，最高档为17万。', 'Once a week. The standard tier costs 60,000 and the top tier costs 170,000.', 'en'),
    ('Revenue was 2.5 billion in that period.', '那段时期的收入为25亿。', 'zh'),
])
def test_equivalent_explicit_magnitudes_pass_without_content_retry(source, target, audience):
    calls = []

    def model(_, payload):
        calls.append(payload)
        return {'lines': [{'id': 0, 'text': target}]}

    assert translate([{'text': source}], audience, call=model) == {0: target}
    assert len(calls) == 1


def test_wrong_magnitude_triggers_repair_with_expected_values():
    source = '普通档为6万，最高档为17万。'
    calls = []

    def model(_, payload):
        calls.append(payload)
        target = 'The tiers cost 6 and 17.' if len(calls) == 1 else 'The tiers cost 60,000 and 170,000.'
        return {'lines': [{'id': 0, 'text': target}]}

    assert translate([{'text': source}], 'en', call=model) == {0: 'The tiers cost 60,000 and 170,000.'}
    assert calls[1]['repair_hint']['missing_number_values'] == ['170000', '60000']


def test_retry_identifies_an_ordinary_word_left_in_the_source_language():
    source = 'I was the unofficial spokesperson at the meeting.'
    calls = []

    def model(_, payload):
        calls.append(payload)
        fixed = payload.get('repair_hint', {}).get('untranslated_words') == ['unofficial']
        text = '我是这场会议的非正式发言人。' if fixed else '我是会议的unofficial发言人。'
        return {'lines': [{'id': 0, 'text': text}]}

    assert translate([{'text': source}], 'zh', call=model) == {0: '我是这场会议的非正式发言人。'}
