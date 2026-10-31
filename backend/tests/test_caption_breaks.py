"""Caption lines break between words, from the more_time and bottleneck clips of the 1.5.7 run."""
from pathlib import Path

from backend.services.studio.cjk_segment import break_units
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import _hold_phrases, _phrases, build_fill, caption_line_limit

ROOT = Path(__file__).resolve().parents[2]
STREET = caption_line_limit('street')


def test_words_numbers_and_counted_nouns_stay_whole():
    assert '八倍' in break_units('他说一百年后经济会增长八倍')
    assert '生产力' in break_units('富足和生产力提升')
    assert break_units('只是我们每周工作80小时')[-3:] == ['每周', '工作', '80小时']
    assert '一项预测' in break_units('凯恩斯对工业革命做了一项预测')


def test_lines_never_split_a_word_or_leave_a_two_character_orphan():
    cases = {
        '他说一百年后经济会增长八倍': ('增长八倍', '倍'),
        '我们获得了巨大的富足和生产力提升': ('生产力', '产力'),
        '只是我们每周工作80小时': ('工作80小时', '作80小时'),
        '回到1930年凯恩斯对工业革命做了一项预测': ('一项预测', '预测'),
    }
    for text, (kept, orphan) in cases.items():
        for limit in (STREET, 10, 8):
            pieces = _phrases(text, limit)
            assert ''.join(pieces) == text
            assert all(len(piece) >= 3 for piece in pieces), (limit, pieces)
            assert orphan not in pieces, (limit, pieces)
            assert any(kept in piece for piece in pieces), (limit, pieces)
    # Production more_time run: 就越发|现还有更多事要做 cut 发现 although 越发 is a word too.
    assert all(not piece.endswith('越发') for piece in _phrases('我学得越多就越发现还有更多事要做', 10))
    assert _phrases('人们说我们会有更多时间', 10) in (['人们说我们会', '有更多时间'], ['人们说', '我们会有更多时间'])


def test_highlight_is_one_unit():
    # 解锁更多机会 is the cue's emphasis in more_time; the break moves before it, not inside it.
    pieces = _phrases('这种智能会解锁更多机会', 8, emphasis='解锁更多机会')
    assert any('解锁更多机会' in piece for piece in pieces), pieces
    assert any('更多的机会' in piece for piece in _phrases('而这些东西会打开更多的机会', 8, emphasis='更多的机会'))


def test_short_phrase_that_cannot_share_a_line_borrows_time():
    fps = 30
    placed = [('经济会增长八倍了吧', 1.0, 2.8, 30, 84), ('就这样', 2.8, 3.1, 84, 93), ('但每周工作时间会降', 3.1, 5.0, 93, 150)]
    held = _hold_phrases(placed, line_limit=10)
    assert [item[0] for item in held] == [item[0] for item in placed]
    assert all(item[4] - item[3] >= 0.6 * fps for item in held), held
    assert all(a[4] == b[3] for a, b in zip(held, held[1:]))
    assert held[0][3] == 30 and held[-1][4] == 150


def test_real_cue_has_no_phrase_under_six_tenths_of_a_second():
    # more_time, 46-66s: 倍 was on screen for 0.27s and 预测 for 0.53s.
    cues = [{'start': 45.0, 'end': 56.4, 'text': '回到1930年，凯恩斯对工业革命做了一项预测。他说一百年后经济会增长八倍，但每周工作时间会降到15小时。'},
            {'start': 56.6, 'end': 65.6, 'text': '他说对了，经济确实增长了八倍。我们获得了巨大的富足和生产力提升，只是我们每周工作80小时，并没有变成15小时工作周。'}]
    packaging = Packaging(version=2, template='street', audience_language='zh', title_lines=['标题'], cues=cues)
    fill = build_fill(packaging, 66.0, template='street')
    words = fill['words']
    assert all(w['end_frame'] - w['start_frame'] >= 18 for w in words), [(w['text'], w['end_frame'] - w['start_frame']) for w in words]
    texts = [w['text'] for w in words]
    assert not any(t in ('倍', '预测', '作80小时', '产力提升') for t in texts), texts


def test_word_list_is_small_and_packaged():
    lexicon = ROOT / 'backend/assets/lexicon/zh_words.txt.gz'
    assert lexicon.stat().st_size < 5 * 1024 * 1024
    assert (ROOT / 'backend/assets/lexicon/zh_words-LICENSE.txt').is_file()
    assert 'assets/lexicon/*.txt.gz' in (ROOT / 'pyproject.toml').read_text(encoding='utf-8')


def test_a_long_highlight_keeps_its_own_line_and_does_not_split_a_word():
    # more_time: emphasis 还有更多事要做 pulled 现 down with it and showed 就越发 / 现还有更多事要做.
    from backend.services.studio.overlay_fill import _phrases
    pieces = _phrases('我这一生学得越多，就越发现还有更多事要做。', 10, '还有更多事要做')
    assert pieces == ['我这一生学得越多', '就越发现', '还有更多事要做']
    joined = '|'.join(pieces)
    assert '越发|现' not in joined and '发|现' not in joined


def test_a_short_highlight_moves_down_whole_words():
    from backend.services.studio.overlay_fill import _attach_emphasis
    # 机会 is not its own line; the characters that move down with it are a whole word.
    left, right = _attach_emphasis('这种智能会解锁更多', '机会', 8)
    assert right.endswith('机会') and not left.endswith('解') and not right.startswith('锁')
