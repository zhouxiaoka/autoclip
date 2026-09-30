"""Clip boundaries land on complete sentences and complete thoughts (no model calls)."""
from backend.services.studio import boundaries as b

# Shaped like real Dwarkesh/YC subtitles: rows are half sentences.
ROWS = [
    (100.0, 104.0, 'So I will basically tell you where I think we are.'),
    (104.0, 108.0, 'But let me ask it in a very specific question so that we can'),
    (108.0, 112.0, 'figure out exactly what kinds of capabilities matter.'),
    (112.0, 116.0, 'I think that is dependent on several things. One,'),
    (116.0, 120.0, 'that is dependent on computer use getting good enough.'),
    (120.0, 124.0, 'It seems like'),
    (124.0, 128.0, 'we have different definitions of a genius.'),
]


def test_end_inside_a_row_cuts_at_its_sentence_end():
    start, end = b.sentence_bounds(ROWS, 104.0, 116.0)  # pipeline ended after "several things. One,"
    assert start == 104.0 and 114.5 < end < 116.0      # keeps "…several things." and drops "One,"


def test_a_row_that_ends_with_a_new_sentence_is_cut_before_it():
    rows = [(0.0, 4.0, 'We have thought carefully about this.'),
            (4.0, 8.0, "That's what I mean when I say we're responsible. It seems like"),
            (9.0, 13.0, 'we have different definitions of a genius.')]
    _, end = b.sentence_bounds(rows, 0.0, 8.0)
    assert 6.5 < end < 8.0  # after "responsible.", not on "It seems like"


def test_a_start_on_the_tail_of_a_sentence_begins_at_the_next_one():
    rows = [(0.0, 4.0, 'so it is about more than'),
            (4.0, 8.0, 'white collar work. And so it might be more productive'),
            (8.0, 12.0, 'to talk about what the models can do.')]
    start, _ = b.sentence_bounds(rows, 4.0, 12.0)
    assert 5.0 < start < 6.5  # begins at "And so", not "white collar work."


def test_the_next_question_is_not_left_at_the_end():
    rows = [(0.0, 4.0, 'Games will go beyond film.'), (4.0, 8.0, 'That is why I joined the industry.'),
            (8.0, 11.0, 'Which director influenced you most?')]
    _, end = b.sentence_bounds(rows, 0.0, 11.0)
    assert end < 8.5


def test_japanese_question_endings_are_recognised():
    rows = [(0.0, 4.0, 'ゲーム業界に来た'), (4.0, 6.0, 'という事でございます'), (6.4, 8.0, '最も影響を与えた監督は誰だと思いますか')]
    _, end = b.sentence_bounds(rows, 0.0, 8.0)
    assert end <= 6.4  # ends on 「ございます」, before the next question


def test_start_moves_back_to_the_beginning_of_its_sentence():
    start, _ = b.sentence_bounds(ROWS, 108.0, 112.0)  # pipeline started on "figure out exactly…"
    assert start == 104.0


def test_a_dangling_opener_is_not_left_at_the_end():
    _, end = b.sentence_bounds(ROWS, 112.0, 124.0)  # ended on "It seems like"
    assert end >= 128.0


def test_pauses_end_sentences_when_asr_has_no_punctuation():
    rows = [(10.0, 12.0, 'ゲーム業界に来た'), (12.0, 13.0, 'という事でございます'), (14.2, 16.0, '次の質問です'), (16.0, 18.0, 'どう思いますか')]
    assert b.sentence_bounds(rows, 10.0, 12.0) == (10.0, 13.4)  # finishes the phrase, stops at the 1.2 s pause


def test_extension_is_bounded():
    rows = [(float(i), float(i + 1), f'word {i} and') for i in range(0, 200)]  # never a sentence end
    start, end = b.sentence_bounds(rows, 50.0, 60.0)
    assert end - 60.0 <= b.MAX_TAIL_SEC + 1 and 50.0 - start <= b.MAX_LEAD_SEC + 1


def test_model_can_finish_the_answer_but_not_pick_another_clip():
    finish = lambda *_: {'start_line': 1, 'end_line': 6}      # window ids: row 0 is id 0
    assert b.refine_with_model(ROWS, 104.0, 116.0, finish) == (104.0, 128.4)
    wander = lambda *_: {'start_line': 6, 'end_line': 6}      # a single unrelated row
    assert b.refine_with_model(ROWS, 104.0, 124.0, wander) is None
    broken = lambda *_: {'start_line': 'x'}
    assert b.refine_with_model(ROWS, 104.0, 116.0, broken) is None


def test_refine_clips_falls_back_to_sentence_bounds_when_the_model_fails():
    def boom(*_):
        raise RuntimeError('provider down')
    assert b.refine_clips(ROWS, [(104.0, 116.0)], boom) == [b.sentence_bounds(ROWS, 104.0, 116.0)]
    assert b.refine_clips(ROWS, [(104.0, 116.0)], None) == [b.sentence_bounds(ROWS, 104.0, 116.0)]
