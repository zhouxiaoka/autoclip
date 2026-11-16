"""Source words, scene cuts and negation survive subtitle display pagination."""
from backend.services.studio import packaging
from backend.services.studio.caption_units import translation_units


def test_negation_is_translated_with_its_predicate_across_asr_rows():
    rows = [
        {'start': 0., 'end': 3., 'text': 'Anybody who is not'},
        {'start': 3.9, 'end': 8., 'text': 'taking this seriously is not'},
        {'start': 8.8, 'end': 10., 'text': 'prepared enough.'},
    ]
    assert translation_units(rows) == [{'start': 0., 'end': 10.,
        'text': 'Anybody who is not taking this seriously is not prepared enough.'}]


def test_paragraph_sentences_are_not_split_into_display_sized_translation_fragments():
    text = 'It was actually a gift at the end of the shoot and I wear it to this day. It helps a great deal.'
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:20,000', 'text': text}]
    rows = packaging.draft_lines(entries, [{'start': 0., 'end': 20.}])
    units = translation_units(rows)
    assert [u['text'] for u in units] == [text[:text.index('.') + 1], 'It helps a great deal.']
    assert units[0]['start'] == 0 and units[-1]['end'] == 20
    assert units[0]['end'] <= units[1]['start']


def test_speaker_changes_and_noncontiguous_scenes_are_not_merged():
    rows = [{'start': 0., 'end': 1., 'text': 'I think'},
            {'start': 1., 'end': 2., 'text': '>> Do you agree?'},
            {'start': 20., 'end': 21., 'text': 'Yes.'}]
    assert translation_units(rows) == rows


def test_adjacent_scene_cuts_remain_separate_translation_units():
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:02,000', 'text': 'I think'},
               {'start_time': '00:00:02,000', 'end_time': '00:00:04,000', 'text': 'this belongs to another shot'}]
    rows = packaging.draft_lines(entries, [{'start': 0., 'end': 2.}, {'start': 2., 'end': 4.}])
    assert [r['text'] for r in translation_units(rows)] == [r['text'] for r in rows]


def test_abbreviations_and_numbers_are_not_sentence_boundaries():
    text = 'Dr. Lee met Hunter S. Thompson at 3.5 pm. They agreed.'
    units = translation_units([{'start': 0., 'end': 10., 'text': text}])
    assert [u['text'] for u in units] == ['Dr. Lee met Hunter S. Thompson at 3.5 pm.', 'They agreed.']


def test_chinese_quotes_stay_with_the_finished_sentence():
    units = translation_units([{'start': 0., 'end': 10., 'text': '他说“明天见。”然后离开。'}])
    assert [u['text'] for u in units] == ['他说“明天见。”', '然后离开。']


def test_short_sentences_in_one_paragraph_keep_their_shared_context():
    text = 'We filmed in his house. It felt like meeting a ghost. That was cool.'
    entries = [{'start_time': '00:00:00,000', 'end_time': '00:00:09,000', 'text': text}]
    units = translation_units(packaging.draft_lines(entries, [{'start': 0., 'end': 9.}]))
    assert units == [{'start': 0., 'end': 9., 'text': text}]


def test_chinese_connector_keeps_the_rest_of_the_sentence_after_a_breath():
    rows = [{'start': 0., 'end': 4., 'text': '一个人怎么从这些光鲜的东西里就'},
            {'start': 4.64, 'end': 7., 'text': '退出去了'}]
    assert translation_units(rows) == [{'start': 0., 'end': 7., 'text': '一个人怎么从这些光鲜的东西里就退出去了'}]


def test_all_source_words_survive_a_long_unpunctuated_run():
    rows = [{'start': i*3., 'end': i*3.+3., 'text': f'word{i} ' * 20} for i in range(40)]
    units = translation_units(rows)
    assert ' '.join(u['text'] for u in units).split() == ' '.join(r['text'] for r in rows).split()
    assert all(len(u['text']) <= 600 for u in units)
    assert units[0]['start'] == 0 and units[-1]['end'] == 120
