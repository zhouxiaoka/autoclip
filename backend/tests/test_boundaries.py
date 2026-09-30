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


def test_end_moves_forward_until_the_sentence_is_finished():
    start, end = b.sentence_bounds(ROWS, 104.0, 116.0)  # pipeline ended after "One,"
    assert start == 104.0 and end >= 120.0 and end < 121.0


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
