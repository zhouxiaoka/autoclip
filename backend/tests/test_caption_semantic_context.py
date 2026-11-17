"""Content failures observed with real transcripts, represented by synthetic dialogue."""
from types import SimpleNamespace

import pytest

from backend.services.studio import boundaries, caption_translation, packaging
from backend.services.studio.caption_units import translation_units


def test_names_are_not_invented_across_subtitle_rows_or_from_discourse_words():
    rows = [{'text': 'So'}, {'text': 'Mostly we work with Dana K. Morgan.'},
            {'text': 'Well Maybe this is useful.'}]
    assert packaging._protected_terms({'title': 'An interview'}, rows, 'zh') == ['Dana K. Morgan']


def test_only_names_in_the_current_unit_reach_the_real_request(monkeypatch):
    from backend.utils import llm_client
    seen = []
    def call(_prompt, data, **_kwargs):
        seen.append(data)
        return '所以。' if len(seen) == 1 else data['protected_terms'][0] + '加入了。'
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=call))
    lines = [{'text': 'So.'}, {'text': 'Dana K. Morgan joined.'}]
    assert len(caption_translation.translate(lines, 'zh', terms=('Dana K. Morgan',))) == 2
    assert seen[0]['protected_terms'] == []
    assert seen[1]['protected_terms'] == ['__AC_NAME_0__']
    assert 'Dana' not in seen[1]['text']


@pytest.mark.parametrize('response', ['那位演员加入了。', '__AC_NAME_9__加入了。'])
def test_missing_or_corrupt_name_tokens_are_not_accepted(monkeypatch, response):
    from backend.utils import llm_client
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=lambda *_a, **_kw: response))
    assert caption_translation.translate([{'text': 'Dana Morgan joined.'}], 'zh', terms=('Dana Morgan',)) == {}


def test_repeated_names_and_initials_are_restored_exactly(monkeypatch):
    from backend.utils import llm_client
    def call(_prompt, data, **_kwargs):
        return data['protected_terms'][0] + '出演了' + data['protected_terms'][1] + '。'
    monkeypatch.setattr(llm_client, 'get_llm_manager', lambda: SimpleNamespace(call=call))
    result = caption_translation.translate([{'text': 'Dana K. Morgan portrayed Dana K. Morgan.'}],
                                           'zh', terms=('Dana K. Morgan',))
    assert result == {0: 'Dana K. Morgan出演了Dana K. Morgan。'}


@pytest.mark.parametrize('target', ['比例达到百分之十五、百分之二十和百分之二十五。', '比例达到15%、20%和25%。'])
def test_equivalent_written_numbers_do_not_erase_a_valid_translation(target):
    source = 'The proportions reached 15, 20 and 25 percent.'
    assert caption_translation._valid(source, target, 'zh', ()) == target


@pytest.mark.parametrize('target', ['比例达到百分之十六、百分之二十和百分之二十五。',
                                    '比例达到一百一十五、二十和二十五。'])
def test_changed_or_suffix_only_numbers_are_still_rejected(target):
    assert caption_translation._valid('The proportions reached 15, 20 and 25 percent.', target, 'zh', ()) is None


def test_chinese_indefinite_article_does_not_require_an_arabic_one_in_english():
    text = 'How can a person leave this world?'
    assert caption_translation._valid('一个人怎么从这样的世界里退出去', text, 'en', ()) == text


def test_complete_source_passage_keeps_an_idiom_with_its_reference():
    text = ('I wore the old director\'s coat. We worked in his original studio. '
            'It felt like meeting a ghost. That was cool and helped my performance.')
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:27,000', 'text': text}]
    units = translation_units(packaging.draft_lines(entries, [{'start': 0., 'end': 27.}]))
    assert units == [{'start': 0., 'end': 27., 'text': text}]


def test_unpunctuated_sentence_survives_breaths_between_its_clauses():
    rows = [{'start': 0., 'end': 4., 'text': 'I want to make sure that this power gets'},
            {'start': 4.8, 'end': 8., 'text': 'widely distributed throughout our community'},
            {'start': 9.3, 'end': 12., 'text': 'and is not limited to just a few people'}]
    units = translation_units(rows)
    assert len(units) == 1 and units[0]['text'] == ' '.join(r['text'] for r in rows)
    assert (units[0]['start'], units[0]['end']) == (0., 12.)


def test_rhetorical_self_question_does_not_remove_the_conclusion():
    rows = [(0., 35., 'The tools have improved.'), (35., 40., 'This change makes the work possible.'),
            (40., 45., 'So now I tell myself, you know what?'),
            (45., 52., 'I can finally build the ambitious project I always wanted.'),
            (53., 60., 'We will take a short break now.')]
    result = boundaries.sentence_bounds(rows, 0., 52.)
    assert result[1] >= 52.


def test_a_real_next_question_is_still_removed():
    rows = [(0., 40., 'The answer is complete.'), (40., 45., 'What is your next project?'),
            (45., 48., 'I am considering several options.'), (49., 60., 'We will discuss them later.')]
    result = boundaries.sentence_bounds(rows, 0., 48.)
    assert result[1] == 40.


def test_model_cannot_cut_before_a_self_question_and_discard_its_conclusion():
    rows = [(0., 35., 'We have better tools.'), (35., 40., 'This makes the work possible.'),
            (40., 45., 'So I tell myself, you know what?'),
            (45., 52., 'I can finally build the ambitious project I always wanted.'),
            (52., 55., 'That is a big change.'), (55., 60., 'Now I want to ask about people who'),
            (60., 65., 'might worry because')]
    result = boundaries.refine_with_model(rows, 0., 58., lambda _, data: {'end_line': data['end_candidates'][0]})
    assert result is not None and result[1] >= 52.
