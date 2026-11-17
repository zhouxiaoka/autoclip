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


def test_open_service_request_cannot_displace_a_completed_answer():
    rows = [
        (0., 6., 'Here the server brings the menu.'),
        (6., 7., 'Let me get'),
        (7., 11., 'The prices at this place are pretty good.'),
    ]
    seen = []

    def model(_, data):
        seen.extend(data['end_candidates'])
        return {'end_line': 0}

    result = boundaries.refine_with_model(rows, 0., 6.9, model)
    assert result is not None and result[1] == 6.
    assert 1 not in seen
    assert boundaries.unfinished('Let me get')
    assert not boundaries.unfinished('Let me get the menu.')


def test_unpunctuated_transcript_end_does_not_authorize_an_unrelated_extension():
    rows = [
        (0., 5., '先聊一个公告'),
        (5., 10., '公告就说到这里'),
        (10., 16., '今天的话题是咖啡怎么保存'),
        (16., 20.4, '密封后放在阴凉处就可以了'),
        (20.4, 24., '下面来看看烤箱怎么选'),
        (24., 32., '需要先看烤箱的体积'),
        (32., 41., '按照各自的空间挑选'),
    ]
    seen = []

    def model(_, data):
        seen.extend(data['end_candidates'])
        return {'end_line': max(data['end_candidates'])}

    result = boundaries.refine_with_model(rows, 10.1, 20.1, model)
    assert result is not None and result[0] == 10. and result[1] == 20.4
    assert seen and max(seen) == 3


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
