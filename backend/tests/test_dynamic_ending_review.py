import pytest

from backend.core.job_budget import JobDurationExceeded, bound_clip_job
from backend.core.project_cancellation import JobStopped
from backend.services.studio import boundaries


ROWS = [
    (0., 17., 'The failing prototype looked promising.'),
    (17., 21., 'The lighter version finally worked.'),
    (21.24, 23.7, 'That changed how we thought about the whole design.'),
    (23.71, 25., 'There are people here who'),
    (25., 48., 'have a different question about'),
    (48., 59., 'next year and what follows.'),
]


def test_early_model_cut_is_reviewed_against_the_nearby_conclusion():
    seen = []

    def select(_, payload):
        seen.append(payload)
        if len(seen) == 1:
            assert payload['lines'][2]['start'] == 21.24
            return {'end_line': 1, 'next_topic_line': 3}
        assert payload['end_candidates'] == [1, 2]
        assert payload['selected_end_line'] == 1
        return {'end_line': 2, 'next_topic_line': 3, 'later_is_part_of_answer': True}

    result = boundaries.refine_with_model(ROWS, 0., 24.5, select)
    assert result.end_anchor == (2, len(ROWS[2][2]))
    assert 23.7 <= result[1] <= 23.71
    assert not result.needs_review
    assert len(seen) == 2


def test_a_new_topic_can_keep_the_earlier_cut():
    rows = list(ROWS)
    rows[2] = (21.24, 23.7, "Next, let's talk about our pricing.")
    seen = []

    def select(_, payload):
        seen.append(payload)
        return {'end_line': 1, 'next_topic_line': 2, 'later_is_part_of_answer': False}

    result = boundaries.refine_with_model(rows, 0., 24.5, select)
    assert result.end_anchor == (1, len(rows[1][2]))
    assert not result.needs_review
    assert len(seen) == 2


def test_an_explicit_speaker_turn_does_not_trigger_extension_review():
    rows = list(ROWS)
    rows[2] = (21.24, 23.7, '>> I have an unrelated update.')
    seen = []

    def select(_, payload):
        seen.append(payload)
        return {'end_line': 1, 'next_topic_line': 2}

    result = boundaries.refine_with_model(rows, 0., 24.5, select)
    assert result.end_anchor[0] == 1 and not result.needs_review
    assert len(seen) == 1


@pytest.mark.parametrize('answer', [
    {'end_line': 3, 'later_is_part_of_answer': True},
    {'end_line': 2, 'next_topic_line': 2, 'later_is_part_of_answer': True},
    {'end_line': 2, 'later_is_part_of_answer': False},
    {'end_line': 2, 'later_is_part_of_answer': 'true'},
    {'needs_review': True},
    RuntimeError('provider unavailable'),
])
def test_inconclusive_or_invalid_review_keeps_original_with_warning(answer):
    def select(_, payload):
        if 'selected_end_line' not in payload:
            return {'end_line': 1, 'next_topic_line': 3}
        if isinstance(answer, Exception):
            raise answer
        return answer

    result = boundaries.refine_with_model(ROWS, 0., 24.5, select)
    assert result.end_anchor[0] == 1 and result.needs_review


def test_repair_and_ambiguity_share_one_extra_model_request():
    seen = []

    def select(_, payload):
        seen.append(payload)
        return {'end_line': 700 if len(seen) == 1 else 1, 'next_topic_line': 3}

    result = boundaries.refine_with_model(ROWS, 0., 24.5, select)
    assert result.end_anchor[0] == 1 and result.needs_review
    assert len(seen) == 2


@pytest.mark.parametrize('error', [JobStopped, JobDurationExceeded])
def test_extra_model_call_preserves_cancellation_and_parent_deadlines(error):
    def select(_, payload):
        if 'selected_end_line' not in payload:
            return {'end_line': 1, 'next_topic_line': 3}
        raise error()

    with bound_clip_job(seconds=60), pytest.raises(error):
        boundaries.refine_with_model(ROWS, 0., 24.5, select)
