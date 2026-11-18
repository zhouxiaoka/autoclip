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
    joined = ''.join(texts)
    for phrase in ('人们说我们会有更多时间', '我完全不同意', '这就是未来', '我认为对大多数人来说', '这种智能会解锁更多机会'):
        assert joined.count(phrase) == 1, (phrase, texts)
    third_shot = (1249.57 - 1245.63) + (1245.1 - 1227.17)
    most = next(item for item in shown if '大多数人' in item[0])
    assert third_shot - 1e-6 <= most[1] <= third_shot + 1.0, shown
    starts = [start for _text, start, _end in shown]
    assert starts == sorted(starts)


def _srt(seconds):
    minutes, rest = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    return f'{hours:02d}:{minutes:02d}:{rest:06.3f}'.replace('.', ',')


MORE_TIME_ROWS = [
    (1227.303, 1232.883, "The more I've learned in life, the more I realize there's more to do."),
    (1232.883, 1236.223, "And that's because every time you learn something, it opens a new door."),
    (1242.883, 1244.923, "And so that's the future."),
    (1245.783, 1247.403, "People say we're going to have more time."),
    (1247.743, 1249.363, 'I completely disagree.'),
    (1250.283, 1254.923, 'I think for most people, this intelligence is going to unlock more opportunities.'),
]
MORE_TIME_SCENES = [{'start': 1245.63, 'end': 1249.57}, {'start': 1227.17, 'end': 1236.4}, {'start': 1242.8, 'end': 1245.1},
                    {'start': 1250.17, 'end': 1255.0}]


def _more_time_packaging(segments):
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio import packaging
    entries = [{'start_time': _srt(a), 'end_time': _srt(b), 'text': text} for a, b, text in MORE_TIME_ROWS]
    lines = packaging.draft_lines(entries, MORE_TIME_SCENES)
    response = {'title_lines': ['黄仁勋：AI不会', '让你更清闲'], 'accent_line': 1, 'segments': segments, 'speakers': [], 'tags': []}
    return lines, packaging.build_packaging({'title': 'More time', 'hook': ''}, lines, platform_strategy('xiaohongshu'),
                                            call=lambda prompt, data: response)


def test_packaged_sentence_that_runs_backwards_is_split_on_its_subtitle_timing():
    # Live DeepSeek output for more_time: lines 0-3 (cold open, then the second shot) as one sentence.
    lines, result = _more_time_packaging([
        {'from': 0, 'to': 3, 'text': '人们说我们会有更多时间。我完全不同意。人生学得越多，我越发现还有更多事要做。因为每次你学到东西，就会打开一扇新门。'},
        {'from': 4, 'to': 5, 'text': '这就是未来。我认为对大多数人来说，这种智能会解锁更多机会。'},
    ])
    assert not result['fallback']
    cues = [(cue['start'], cue['end'], cue['text']) for cue in result['cues']]
    assert all(start < end for start, end, _text in cues), cues
    assert cues[0] == (lines[0]['start'], lines[1]['end'], '人们说我们会有更多时间。我完全不同意。')
    assert cues[1][:2] == (lines[2]['start'], lines[3]['end']) and cues[1][2].startswith('人生学得越多')
    assert ''.join(text for _a, _b, text in cues) == '人们说我们会有更多时间。我完全不同意。人生学得越多，我越发现还有更多事要做。因为每次你学到东西，就会打开一扇新门。这就是未来。我认为对大多数人来说，这种智能会解锁更多机会。'
    # "And so that's the future." skips the cold-open lines before "I think..." in the source: split there too.
    assert [text for _a, _b, text in cues[2:]] == ['这就是未来。', '我认为对大多数人来说，这种智能会解锁更多机会。']


def test_forward_sentence_across_a_plain_cut_stays_one_cue():
    lines, result = _more_time_packaging([
        {'from': 0, 'to': 1, 'text': '人们说我们会有更多时间。我完全不同意。'},
        {'from': 2, 'to': 3, 'text': '人生学得越多，我越发现还有更多事要做。因为每次你学到东西，就会打开一扇新门。'},
        {'from': 4, 'to': 4, 'text': '这就是未来。'},
        {'from': 5, 'to': 5, 'text': '我认为对大多数人来说，这种智能会解锁更多机会。'},
    ])
    assert len(result['cues']) == 4 and result['cues'][1]['start'] == lines[2]['start'] and result['cues'][1]['end'] == lines[3]['end']


def test_cue_that_runs_backwards_across_the_cold_open_still_captions_it():
    # The model grouped the cold-open line with the next lines in timeline order:
    # start 1245.78 (cold open) > end 1236.22 (second shot). It used to be dropped: 13s with no captions.
    scenes = [Scene(id='c', start=1245.63, end=1249.57), Scene(id='a', start=1227.17, end=1245.1)]
    rows = [
        (1245.783, 1247.403, "People say we're going to have more time."),
        (1247.743, 1249.363, 'I completely disagree.'),
        (1227.303, 1232.883, "The more I've learned in life, the more I realize there's more to do."),
        (1232.883, 1236.223, "And that's because every time you learn something, it opens a new door."),
    ]
    cue = {'start': 1245.783, 'end': 1236.223,
           'text': '人们说我们会有更多时间。我完全不同意。人生学得越多，我越发现还有更多事要做。因为每次你学到东西，就会打开一扇新门。',
           'original': ' '.join(row[2] for row in rows)}
    for template in ('street', 'editorial'):
        shown = _on_screen(_fill(template, scenes, [cue], rows))
        assert shown and shown[0][1] < 0.5, (template, shown)
        joined = ''.join(text for text, _a, _b in shown)
        assert joined == '人们说我们会有更多时间我完全不同意人生学得越多我越发现还有更多事要做因为每次你学到东西就会打开一扇新门', (template, joined)
        disagree = next(item for item in shown if '不同意' in item[0])
        assert disagree[2] <= 1249.57 - 1245.63 + 0.2, shown


def test_no_name_without_turn_markers():
    # more_time's subtitles have no ">>". The model named the guest on every cue, host lines included.
    from backend.services.studio.overlay_fill import _agree_speaker
    speakers = [{'at': 0.0, 'name': '黄仁勋', 'role': '英伟达 CEO'}]
    rows = [(1242.883, 1244.923, "And so that's the future."), (1245.783, 1247.403, "People say we're going to have more time.")]
    assert _agree_speaker('黄仁勋', 1242.883, 1247.403, rows, speakers, None) == ''
    assert _agree_speaker('', 1242.883, 1247.403, rows, speakers, None) == ''
