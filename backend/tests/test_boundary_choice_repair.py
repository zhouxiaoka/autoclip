from backend.services.studio import boundaries


def test_out_of_range_model_choice_gets_one_bounded_candidate_only_repair():
    rows = [(0., 10., 'A complete opening.'), (10., 20., 'The answer is complete.'),
            (20., 24., 'A new question for you?'), (24., 30., 'Because'),
            (30., 40., 'This belongs to the next topic.')]
    calls = []
    def model(prompt, data):
        calls.append(data)
        return {'end_line': 999 if len(calls) == 1 else 1}
    result = boundaries.refine_with_model(rows, 0., 22., model)
    assert result is not None and result[1] == 20.
    assert len(calls) == 2
    assert all(row['id'] in calls[1]['end_candidates'] for row in calls[1]['lines'])


def test_repeated_invalid_choices_stop_after_one_repair():
    rows = [(0., 10., 'Opening.'), (10., 20., 'Answer.'), (20., 30., 'Next question?')]
    calls = []
    result = boundaries.refine_with_model(rows, 0., 19., lambda _, data: calls.append(data) or {'end_line': 999})
    assert result is None and len(calls) == 2


def test_unfinished_negation_and_complete_negative_answer_are_distinguished():
    assert boundaries.unfinished('Anybody who is not')
    assert not boundaries.unfinished('Absolutely not.')


def test_sentence_cut_does_not_treat_a_name_initial_as_an_ending():
    text = 'I met Hunter S. Thompson. Then we talked.'
    offsets = boundaries._inner_ends(text)
    assert [text[:offset] for offset in offsets] == ['I met Hunter S. Thompson.']


def test_model_cannot_extend_without_a_supported_sentence_completion():
    rows = [(0., 10., 'The original answer is complete.'),
            (10., 13., 'I have another question about people who'),
            (13., 18., 'might be worried that well'),
            (18., 23., 'they could choose something else'),
            (23., 28., 'and then they might'),
            (28., 60., 'continue this unrelated topic for much longer.')]
    seen = []
    def call(_, data):
        seen.append(data)
        return {'end_line': 0}
    result = boundaries.refine_with_model(rows, 0., 13., call)
    assert result == (0., 10.)
    assert seen[0]['end_candidates'] == [0]
