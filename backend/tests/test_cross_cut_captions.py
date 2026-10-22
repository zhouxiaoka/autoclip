"""Captions for sentences that cross a cut, from the Bg2 clips used in the 1.5.7 acceptance run."""
from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import build_fill

FPS = 30


def _fill(template, scenes, cues, rows):
    packaging = Packaging(
        version=1, template='interview_zh', audience_language='zh', source_language='en',
        title_lines=['我爸连西装都没有', '24小时买好赶去白宫'], cues=cues,
    )
    duration = sum(scene.end - scene.start for scene in scenes)
    return build_fill(packaging, duration, fps=FPS, scenes=scenes, template=template, transcript=rows)


def _on_screen(fill):
    return [(w['text'], w['start_frame'] / FPS, w['end_frame'] / FPS) for w in fill['words']]


def test_phrase_after_a_cut_is_shown_on_the_kept_shot():
    # dad_suit: the cut removes 143.37-147.37, where nobody speaks. "brand new suit" is in the second shot.
    scenes = [Scene(id='s0', start=129.07, end=143.37), Scene(id='s1', start=147.37, end=161.17)]
    rows = [
        (139.127, 140.287, 'And my dad didn\'t even have a suit.'),
        (141.207, 143.207, 'Yeah, so he ran out and bought a suit.'),
        (147.447, 149.367, 'Yeah, it was a brand new suit and he showed up,'),
    ]
    cue = {'start': 139.127, 'end': 149.367, 'text': '我爸连西装都没有，他赶紧跑出去买了一套。全新的西装，他就这么来了。',
           'original': ' '.join(row[2] for row in rows)}
    for template in ('editorial', 'street'):
        shown = _on_screen(_fill(template, scenes, [cue], rows))
        texts = [text for text, _a, _b in shown]
        assert ''.join(texts) == '我爸连西装都没有他赶紧跑出去买了一套全新的西装他就这么来了', (template, texts)
        second_shot = 143.37 - 129.07
        new_suit = [item for item in shown if '全新的西装' in item[0]]
        assert len(new_suit) == 1 and new_suit[0][1] >= second_shot - 1e-6, (template, shown)


def test_sentence_after_a_cold_open_keeps_its_middle():
    # more_time: the cue spans 1242.88-1257.88, which also covers the cold open (1245.63-1249.57)
    # played first. "I think for most people" is at 1250.28 in the third shot.
    scenes = [Scene(id='c', start=1245.63, end=1249.57), Scene(id='a', start=1227.17, end=1245.1), Scene(id='b', start=1250.17, end=1306.07)]
    rows = [
        (1242.883, 1244.923, "And so that's the future."),
        (1245.783, 1247.403, "People say we're going to have more time."),
        (1247.743, 1249.363, 'I completely disagree.'),
        (1250.283, 1254.923, 'I think for most people, this intelligence is going to unlock more opportunities.'),
        (1255.0, 1257.88, "And they're going to want to pursue it because they're ambitious."),
    ]
    cues = [
        {'start': 1245.783, 'end': 1249.363, 'text': '人们说我们会有更多时间。我完全不同意。', 'original': rows[1][2] + ' ' + rows[2][2]},
        {'start': 1242.883, 'end': 1257.88, 'text': '这就是未来。我认为对大多数人来说，这种智能会解锁更多机会。他们会想去追求，因为他们有野心。',
         'original': ' '.join(row[2] for row in (rows[0], rows[3], rows[4]))},
    ]
    shown = _on_screen(_fill('street', scenes, cues, rows))
    texts = [text for text, _a, _b in shown]
    for phrase in ('人们说我们会有更多时间', '我完全不同意', '这就是未来', '我认为对大多数人来说', '这种智能会解锁更多机会'):
        assert sum(phrase in text for text in texts) == 1, (phrase, texts)
    third_shot = (1249.57 - 1245.63) + (1245.1 - 1227.17)
    most = next(item for item in shown if '大多数人' in item[0])
    assert third_shot - 1e-6 <= most[1] <= third_shot + 1.0, shown
    starts = [start for _text, start, _end in shown]
    assert starts == sorted(starts)
