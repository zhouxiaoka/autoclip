"""Content quality regressions: validate captions and endings across their real boundaries."""
from types import SimpleNamespace
import pytest

from backend.services.studio import boundaries, packaging


def test_translation_is_independent_of_decoration_and_keeps_source_clock():
    rows = [{'start': i * 2., 'end': i * 2. + 2., 'text': f'This is source sentence number {i}.'} for i in range(20)]
    calls = []

    def call(_prompt, data):
        calls.append(data)
        if data.get('task') == 'translate_captions':
            assert len(data['lines']) <= 8
            return {'lines': [{'id': row['id'], 'text': f"这是第{row['id']}句译文。"} for row in data['lines']]}
        raise ValueError('decorative response invalid')

    result = packaging.build_packaging({'title': '测试'}, rows,
                                       SimpleNamespace(template='interview_zh', audience_language='zh'), call=call)
    assert result.get('translation_status') == 'complete'
    assert len(result['cues']) == len(rows)
    assert all('译文' in cue['text'] for cue in result['cues'])
    assert [(c['start'], c['end']) for c in result['cues']] == [(r['start'], r['end']) for r in rows]
    assert calls[0].get('task') == 'translate_captions'


def test_translation_only_repairs_missing_ids_and_preserves_success():
    rows = [{'start': i * 2., 'end': i * 2. + 2., 'text': f'This is source sentence number {i}.'} for i in range(3)]
    batches = []

    def call(_prompt, data):
        if data.get('task') != 'translate_captions':
            return {}
        ids = [row['id'] for row in data['lines']]
        batches.append(ids)
        return {'lines': [{'id': i, 'text': f'这是第{i}句译文。'} for i in ids if batches.count([1]) > 1 or i != 1]}

    result = packaging.build_packaging({'title': '测试'}, rows,
                                       SimpleNamespace(template='interview_zh', audience_language='zh'), call=call)
    assert batches == [[0], [1], [1], [2]]
    assert result.get('translation_status') == 'complete'


def test_end_search_exhaustion_retreats_to_a_complete_sentence():
    rows = [(0., 60., 'We have explained this point in full.'),
            (60., 63., 'Some people in this room who'),
            (63., 75., 'worry, about the next question and'),
            (75., 87., 'the next subject because'),
            (90., 100., 'have not heard the answer yet.')]
    _, end = boundaries.sentence_bounds(rows, 0., 63.)
    assert end <= 60., 'exhausting the forward search must not accept the dangling last row'


def test_a_breath_after_because_is_not_a_complete_ending():
    rows = [(0., 8., 'Here is a finished answer.'), (8., 12., 'This happens because'),
            (13., 17., 'the cause comes after the pause.')]
    assert not boundaries.ends_sentence(rows, 1, False)


def test_audio_alignment_does_not_cross_a_chosen_semantic_end():
    rows = [(0., 8., 'Our complete conclusion.'), (8.01, 12., 'Here begins a different topic.'),
            (14., 20., 'there is another issue.')]
    _, end = boundaries.sentence_bounds(rows, 0., 8., lambda *_: [(12., 13.5)])
    assert end <= 8.01


def test_unresolved_ending_is_explicit_instead_of_claiming_completion():
    rows = [(float(i), float(i + 1), 'and then because') for i in range(100)]
    result = boundaries.sentence_bounds(rows, 10., 30.)
    assert getattr(result, 'needs_review', False), 'keep a draft but disclose that no complete ending was found'


def test_model_must_choose_an_eligible_ending_without_dangling_connective():
    rows = [(0., 10., 'A whole answer.'), (10., 20., 'Another complete thought.'),
            (20., 24., 'The next subject because'), (24., 28., 'its explanation follows.')]

    def invalid(_prompt, data):
        assert 'end_candidates' in data
        return {'start_line': 0, 'end_line': 2}

    assert boundaries.refine_with_model(rows, 0., 20., invalid) is None


def test_complete_pronoun_objects_are_not_mistaken_for_subject_stubs():
    for text in ['Thank you.', 'This is for you.', 'We will help you']:
        assert not boundaries.unfinished(text)
    assert boundaries.unfinished('I')


@pytest.mark.parametrize('s_id,e_id', [(False, 1), (0, True), (0, 99), (1, 0), (-1, 1)])
def test_model_boundaries_reject_invalid_ids(s_id, e_id):
    rows = [(0., 10., 'One complete thought.'), (10., 20., 'Another complete thought.'), (20., 30., 'A new topic.')]
    assert boundaries.refine_with_model(rows, 0, 20, lambda *_: {'start_line': s_id, 'end_line': e_id}) is None


def test_model_semantic_end_is_not_extended_by_a_second_sentence_search():
    rows = [(0., 10., 'A point, with punctuation but no final stop'), (10., 20., 'the answer is now complete'),
            (20.01, 30., 'Another topic, because'), (30., 40., 'there is much more to discuss.')]
    result = boundaries.refine_with_model(rows, 0., 20., lambda *_: {'start_line': 0, 'end_line': 1}, lambda *_: [(30., 32.)])
    assert result is not None and result[1] <= 20.01 and not result.needs_review
