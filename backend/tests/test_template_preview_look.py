"""Editorial and street overlays match the editing-style preview, not the old bars."""
import json
import os
import re
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

import pytest

from backend.services.studio import packaging_html as html
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill, paint_fill

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'backend' / 'assets' / 'templates'
SANDBOX = ROOT / 'frontend' / 'tests' / 'vm-sandbox.cjs'
CHROME = os.environ.get('CHROME_BIN', 'google-chrome')

# Preview lime and the magazine butter. Sampled from the 1080 CSS, not the old restyle.
STREET_MARK = (0xD7, 0xFF, 0x3A)
EDITORIAL_GOLD = (0xF2, 0xD9, 0x8C)


def _paint(template, **kwargs):
    body = dict(version=2, template=template, audience_language='zh', title_lines=['标题'])
    body.update(kwargs)
    packaging = Packaging(**body)
    return paint_fill(build_fill(packaging, 8, template=template), packaging), packaging


def _render(template, fill):
    script = r'''
const fs = require('fs')
const { runInSandbox } = require(process.argv[1])
const template = process.argv[2]
const root = process.argv[3]
const payload = JSON.parse(fs.readFileSync(0, 'utf8'))
function element() {
  const node = { innerHTML: '', textContent: '', className: '', style: {}, children: [] }
  node.appendChild = child => { node.children.push(child) }
  return node
}
const elements = new Map()
const document = {
  getElementById: id => {
    if (!elements.has(id)) elements.set(id, element())
    return elements.get(id)
  },
  createElement: () => element(),
}
const sandbox = { window: {}, document, console }
sandbox.window = sandbox
runInSandbox(fs.readFileSync(root + '/' + template + '/template.js', 'utf8'), sandbox, { filename: template + '.js' })
sandbox.setData(payload.fill)
const frames = {}
for (const t of payload.times) {
  sandbox.renderFrame(Number(t))
  const read = id => {
    const node = document.getElementById(id)
    return { html: node.innerHTML, text: node.textContent, display: node.style.display || '', className: node.className || '' }
  }
  frames[String(t)] = {
    hook: read('h-l'),
    kick: read('kick'),
    trk: read('trk'),
    zh: read('zh'),
    en: read('en'),
    topic: read('topic'),
    title: read('title-hook'),
    folio: read('f-l'),
    rects: sandbox.occupiedRects(Number(t)),
  }
}
process.stdout.write(JSON.stringify(frames))
'''
    done = subprocess.run(
        ['node', '-e', script, str(SANDBOX), template, str(TEMPLATES)],
        input=json.dumps({'fill': fill, 'times': ['0.5', '1.6', '3.0']}),
        capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)


def _png_size_and_rows(path: Path):
    data = path.read_bytes()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos = 8
    width = height = None
    idat = b''
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            width, height, _bit, color, *_rest = struct.unpack('>IIBBBBB', chunk)
            assert color == 2
        elif kind == b'IDAT':
            idat += chunk
        elif kind == b'IEND':
            break
    raw = zlib.decompress(idat)
    rows = []
    stride = width * 3
    index = 0
    prev = bytearray(stride)
    for _y in range(height):
        filt = raw[index]
        index += 1
        row = bytearray(raw[index:index + stride])
        index += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 0:
            pass
        elif filt == 3:
            for x in range(stride):
                left = row[x - 3] if x >= 3 else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - 3] if x >= 3 else 0
                b = prev[x]
                c = prev[x - 3] if x >= 3 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (row[x] + pr) & 255
        else:
            raise AssertionError(f'unexpected png filter {filt}')
        rows.append(row)
        prev = row
    return width, height, rows


def _near(rows, target, slack=48):
    count = 0
    for row in rows:
        for x in range(0, len(row), 3):
            if all(abs(row[x + channel] - target[channel]) <= slack for channel in range(3)):
                count += 1
                if count > 40:
                    return count
    return count


def _shoot(template, fill, t, dest: Path):
    folder = TEMPLATES / template
    body = (folder / 'index.html').read_text(encoding='utf-8').split('<body>', 1)[1].rsplit('</body>', 1)[0]
    body = body.replace('<script src="template.js"></script>', '')
    driver = dest.with_suffix('.html')
    driver.write_text(
        '<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">'
        f'<link rel="stylesheet" href="{(folder / "style.css").as_uri()}">'
        '<style>html,body{background:#12110f !important;}</style></head><body>'
        f'{body}<script src="{(folder / "template.js").as_uri()}"></script>'
        f'<script>window.setData({json.dumps(fill, ensure_ascii=False)});window.renderFrame({t});</script>'
        '</body></html>',
        encoding='utf-8',
    )
    subprocess.run(
        ['timeout', '20', CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
         '--force-device-scale-factor=1', '--window-size=1080,1920', f'--screenshot={dest}', driver.as_uri()],
        capture_output=True, check=False,
    )
    driver.unlink(missing_ok=True)
    assert dest.is_file() and dest.stat().st_size > 1000, template


def test_fill_keeps_the_source_line_and_the_speaker():
    long_original = 'AI can do probably half or more of those jobs right now and the rest keeps going past two short lines of the source caption'
    fill, _packaging = _paint(
        'street',
        title_lines=['白领工作会最先没'],
        speakers=[{'at': 0.2, 'name': '马斯克', 'role': '特斯拉'}],
        emphasis=[{'at': 0.2, 'text': '一半'}],
        cues=[{'start': 0.2, 'end': 3.0, 'text': 'AI现在就能干一半', 'original': long_original}],
    )
    assert fill['speakers'] == [{'name': '马斯克', 'role': '特斯拉'}]
    assert fill['words']
    original = fill['words'][0]['original']
    assert original == long_original
    assert '\n' not in original
    assert all(word['original'] == original for word in fill['words'])
    assert ' '.join(word['w'] for word in fill['moments'][0]['en']) == long_original
    assert ''.join(word['text'].replace('\n', '') for word in fill['words']) == 'AI现在就能干一半'


def test_emphasis_is_a_word_and_the_editorial_headline_stays_up():
    street, _ = _paint(
        'street',
        title_lines=['白领工作会最先没'],
        speakers=[{'at': 0, 'name': '马斯克', 'role': '特斯拉'}],
        emphasis=[{'at': 0.2, 'text': 'AI'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI现在就能干一半', 'original': 'AI can do half or more'}],
    )
    painted = _render('street', street)
    zh = painted['0.5']['zh']
    source = painted['0.5']['en']['html']
    assert zh['html'] == 'AI现在就能干一半' and zh['className'] == 'k'
    assert re.search(r'class="w k[^"]*">AI<', source)
    assert not re.search(r'class="w k[^"]*">half<', source, re.I)
    # The cue never named a speaker, so the only guest is not written onto this line.
    assert painted['0.5']['topic']['text'] == '白领工作会最先没'
    assert '特斯拉' not in painted['0.5']['topic']['text']
    assert any(rect['slot'] == 'hook' and rect['y'] == 1812 for rect in painted['0.5']['rects'])

    editorial, _ = _paint(
        'editorial',
        title_lines=['AI是五层蛋糕，', '最底层是能源'],
        deck='Jensen Huang on the five-layer cake',
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        emphasis=[{'at': 0.2, 'text': '五层蛋糕'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
    )
    frames = _render('editorial', editorial)
    assert 'AI是五层蛋糕，' in frames['0.5']['hook']['html']
    assert '最底层是能源' in frames['0.5']['hook']['html'] and 'ln acc' in frames['0.5']['hook']['html']
    assert frames['3.0']['hook']['html'] == frames['0.5']['hook']['html']
    assert '五层蛋糕' in frames['0.5']['zh']['html'] and 'acc' in frames['0.5']['zh']['html']
    assert 'five' in frames['0.5']['en']['html']
    assert frames['0.5']['kick']['text'] == 'Jensen Huang on the five-layer cake'
    assert frames['0.5']['trk']['text'] == 'FIVE-LAYER CAKE · JENSEN HUANG'
    hook = next(rect for rect in frames['3.0']['rects'] if rect['slot'] == 'hook')
    assert hook['y'] == 1192

    # Captions-off drops cues inside build_fill. Editorial clears the painted hook so the classic
    # title can be burned beside it. Street keeps the title in the lower band.
    off_editorial = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['AI是五层蛋糕，', '最底层是能源'],
        kicker='访谈', speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
        captions_enabled=False,
    )
    hidden = _render('editorial', paint_fill(build_fill(off_editorial, 8, template='editorial'), off_editorial, 'editorial'))
    assert hidden['3.0']['hook']['html'] == ''
    assert hidden['3.0']['zh']['html'] == ''
    off_street = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['白领工作会最先没'],
        speakers=[{'at': 0, 'name': '马斯克', 'role': '特斯拉'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI现在就能干一半', 'original': 'AI can do half or more'}],
        captions_enabled=False,
    )
    blank = _render('street', paint_fill(build_fill(off_street, 8, template='street'), off_street, 'street'))
    assert blank['0.5']['zh']['html'] == ''
    assert '白领工作会最先没' in blank['0.5']['title']['text']
    assert blank['0.5']['topic']['text'] == '马斯克：白领工作会最先没'
    assert '马斯克：马斯克' not in blank['0.5']['topic']['text']
    assert '白领工作会最先没' in blank['3.0']['title']['text']


def test_prepare_overlay_paints_the_preview_marks(tmp_path, monkeypatch):
    if subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode != 0:
        pytest.skip('ffmpeg unavailable')
    if subprocess.run(['timeout', '5', CHROME, '--version'], capture_output=True).returncode != 0:
        pytest.skip('chrome unavailable')
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '120')
    shots = tmp_path / 'shots'
    shots.mkdir()

    def overlay(template, packaging, duration=4.0):
        seen = {}

        def capture(count, _fps):
            fill = paint_fill(build_fill(packaging, duration, template=template), packaging)
            for t, name in ((0.5, 'early'), (3.0, 'late')):
                dest = shots / f'{template}-{name}.png'
                _shoot(template, fill, t, dest)
                seen[name] = dest
            return [{'index': 0, 'count': count, 'png': seen['late'].read_bytes()}]

        job = html.prepare_overlay(
            'p-look', template, packaging, duration,
            features={'pkg_templates_v1': True}, capture=capture,
        )
        assert job.path and job.path.is_file() and job.downgraded is False
        assert job.template == template
        return seen

    street = Packaging(
        version=2, template='street', audience_language='zh',
        title_lines=['白领工作会最先没'],
        speakers=[{'at': 0, 'name': '马斯克', 'role': '特斯拉'}],
        emphasis=[{'at': 0.2, 'text': '一半'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI现在就能干一半', 'original': 'AI CAN DO HALF OR MORE'}],
    )
    editorial = Packaging(
        version=2, template='editorial', audience_language='zh',
        title_lines=['AI是五层蛋糕，', '最底层是能源'],
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        emphasis=[{'at': 0.2, 'text': '五层蛋糕'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
    )
    street_shots = overlay('street', street)
    editorial_shots = overlay('editorial', editorial)
    for name in ('early', 'late'):
        _width, _height, rows = _png_size_and_rows(street_shots[name])
        assert _near(rows, STREET_MARK) > 40, name
        _width, _height, rows = _png_size_and_rows(editorial_shots[name])
        assert _near(rows, EDITORIAL_GOLD) > 40, name


def test_packaging_parse_carries_one_phrase_and_the_current_speaker():
    """Emphasis and the speaker come from the real packaging parse, not a hand-filled overlay."""
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio import packaging as packaging_mod

    lines = [
        {'start': 0.2, 'end': 2.0, 'text': 'I think for most people this opens more opportunities'},
        {'start': 2.0, 'end': 6.0, 'text': 'Jensen says the economy grows 8 times'},
    ]
    draft = {'title': '黄仁勋', 'hook': ''}

    def reply(**extra):
        body = {
            'title_lines': ['黄仁勋：更闲的工作', '还是更有意义'],
            'accent_line': 0,
            'segments': [
                {'from': 0, 'to': 0, 'text': '我认为对大多数人来说，AI会打开更多机会'},
                {'from': 1, 'to': 1, 'text': '黄仁勋说，经济会增长到 8 倍'},
            ],
            'speakers': [
                {'line': 0, 'name': '主持人', 'role': '访谈'},
                {'line': 1, 'name': '黄仁勋', 'role': '英伟达 CEO'},
            ],
            'tags': [],
            'highlights': [],
            'deck': 'Jensen Huang on the five-layer cake',
            'marks': [
                {'line': 0, 'text': '更多机会', 'speaker': '主持人'},
                {'line': 1, 'text': '8 倍', 'speaker': '黄仁勋'},
            ],
        }
        body.update(extra)
        return body

    prompts = []

    def call(prompt, _data):
        prompts.append(prompt)
        return reply()

    result = packaging_mod.build_packaging(
        draft, lines, platform_strategy('douyin'), known_names='黄仁勋 主持人 Jensen', call=call,
    )
    assert 'marks' in prompts[0]
    assert result['version'] == 1 and result['template'] == 'interview_zh'
    assert result['deck'] == 'Jensen Huang on the five-layer cake'
    assert [cue['emphasis'] for cue in result['cues']] == ['更多机会', '8 倍']
    assert [cue['speaker'] for cue in result['cues']] == ['主持人', '黄仁勋']
    for cue in result['cues']:
        assert cue['emphasis'] in cue['text'] and cue['emphasis'] != cue['text']

    bare = packaging_mod.build_packaging(
        draft, lines, platform_strategy('douyin'), known_names='黄仁勋 主持人 Jensen',
        call=lambda _prompt, _data: reply(marks=[], deck=''),
    )
    again = packaging_mod.build_packaging(
        draft, lines, platform_strategy('douyin'), known_names='黄仁勋 主持人 Jensen',
        call=lambda _prompt, _data: reply(marks=[], deck=''),
    )
    assert [cue['emphasis'] for cue in bare['cues']] == [cue['emphasis'] for cue in again['cues']]
    for cue in bare['cues']:
        assert cue['emphasis'] and cue['emphasis'] in cue['text'] and cue['emphasis'] != cue['text']

    model = Packaging.model_validate(result)
    fill = paint_fill(build_fill(model, 8, template='street'), model, 'street')
    # A long host sentence pages into more than one screen; every page keeps that cue's speaker.
    speakers = [word['speaker'] for word in fill['words']]
    assert speakers[0] == '主持人' and speakers[-1] == '黄仁勋'
    assert set(speakers) == {'主持人', '黄仁勋'}
    host = [word for word in fill['words'] if word['speaker'] == '主持人']
    guest = [word for word in fill['words'] if word['speaker'] == '黄仁勋']
    assert any(word['emphasis'] == '更多机会' for word in host)
    assert any(word['emphasis'] == '8 倍' for word in guest)
    painted = _render('street', fill)
    assert painted['0.5']['topic']['text'] == '主持人：更闲的工作'
    assert '黄仁勋：黄仁勋' not in painted['0.5']['topic']['text']
    assert painted['3.0']['topic']['text'] == '黄仁勋：更闲的工作'
    assert re.search(r'class="w k[^"]*">8<', painted['3.0']['en']['html'])
    assert 'class="w k' not in painted['0.5']['en']['html']
    editorial_fill = paint_fill(build_fill(model, 8, template='editorial'), model, 'editorial')
    frames = _render('editorial', editorial_fill)
    assert frames['0.5']['kick']['text'] == 'Jensen Huang on the five-layer cake'
    assert frames['0.5']['trk']['text'] == 'FIVE-LAYER CAKE · JENSEN HUANG'
    assert frames['3.0']['trk']['text'] == frames['0.5']['trk']['text']
    quiet = {**editorial_fill, 'words': [], 'moments': []}
    still = _render('editorial', quiet)
    hook_on = next(rect for rect in frames['0.5']['rects'] if rect['slot'] == 'hook')
    hook_off = next(rect for rect in still['0.5']['rects'] if rect['slot'] == 'hook')
    assert hook_on['y'] == hook_off['y'] == 1192
    street_css = (TEMPLATES / 'street' / 'style.css').read_text(encoding='utf-8')
    assert 'text-align: center' in street_css and 'font-size: 100px' in street_css and '#D7FF3A' in street_css
    editorial_css = (TEMPLATES / 'editorial' / 'style.css').read_text(encoding='utf-8')
    assert '#F4EFE6' in editorial_css and '#F2D98C' in editorial_css and '#C7243A' in editorial_css


def test_chinese_audience_sees_the_guest_name_only_on_the_guest_line():
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio import packaging as packaging_mod

    lines = [
        {'start': 0.2, 'end': 2.0, 'text': 'I completely disagree with that'},
        {'start': 2.0, 'end': 6.0, 'text': 'Jensen says the dream is still alive'},
    ]

    def call(_prompt, _data):
        return {
            'title_lines': ['黄仁勋谈梦想'],
            'accent_line': 0,
            'segments': [
                {'from': 0, 'to': 0, 'text': '我完全不同意'},
                {'from': 1, 'to': 1, 'text': '黄仁勋说美国梦还在'},
            ],
            'speakers': [{'line': 1, 'name': 'Jensen Huang', 'role': 'Nvidia'}],
            'tags': [],
            'highlights': [],
            'marks': [
                {'line': 1, 'text': '美国梦', 'speaker': 'Jensen Huang'},
            ],
        }

    result = packaging_mod.build_packaging(
        {'title': '黄仁勋', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='黄仁勋 主持人 Jensen', call=call,
    )
    assert result['speakers'][0]['name'] == '黄仁勋'
    assert [cue['speaker'] for cue in result['cues']] == ['', '黄仁勋']
    fill = build_fill(Packaging.model_validate(result), 8, template='street')
    painted = _render('street', fill)
    assert painted['0.5']['topic']['text'] == '黄仁勋谈梦想'
    assert 'Jensen' not in painted['0.5']['topic']['text']
    assert painted['3.0']['topic']['text'] == '黄仁勋：黄仁勋谈梦想'


def test_street_picture_pads_a_1290_window_without_moving_the_draft():
    from backend.services.studio.models import Draft, Scene
    from backend.services.studio.packaging_render import street_picture

    scene = Scene(id='s', start=0, end=4, crop_x=0.2)
    draft = Draft(id='d', title='t', scenes=[scene], layout='crop', crop_x=0.2)
    graph, label = street_picture(draft, scene, 1920, 1080)
    assert 'crop=1080:1290' in graph
    assert 'pad=1080:1920:0:0:black' in graph
    assert 'crop=1080:1920' not in graph
    assert label == 'base'
    assert scene.crop_x == 0.2 and draft.crop_x == 0.2


def test_word_times_light_only_a_textual_or_digit_keyword():
    shared = dict(version=2, template='street', audience_language='zh', title_lines=['一半'])
    chinese = Packaging(
        **shared,
        cues=[{'start': 0.2, 'end': 3.0, 'text': 'AI现在就能干一半', 'original': 'AI can do half or more', 'emphasis': '一半'}],
    )
    timing = [{'start': 0.2, 'end': 3.0, 'text': 'AI can do half or more', 'words': [
        {'text': 'AI', 'start': 0.2, 'end': 0.5},
        {'text': 'can', 'start': 0.5, 'end': 0.8},
        {'text': 'do', 'start': 0.8, 'end': 1.1},
        {'text': 'half', 'start': 1.1, 'end': 1.6},
        {'text': 'or', 'start': 1.6, 'end': 1.9},
        {'text': 'more', 'start': 1.9, 'end': 2.4},
    ]}]
    fill = build_fill(chinese, 4, template='street', word_timing=timing)
    words = fill['moments'][0]['en']
    assert [word['w'] for word in words] == ['AI', 'can', 'do', 'half', 'or', 'more']
    assert [word['key'] for word in words] == [False, False, False, False, False, False]
    assert words[3]['t0'] == pytest.approx(1.1)
    assert fill['moments'][0]['zh'][0]['key'] is True

    numbered = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['八倍'],
        cues=[{'start': 0.0, 'end': 2.0, 'text': '经济会增长到 8 倍', 'original': 'grows 8 times', 'emphasis': '8 倍'}],
    )
    numbered_fill = build_fill(numbered, 2, template='street')
    marked = {word['w']: word['key'] for word in numbered_fill['moments'][0]['en']}
    assert marked['8'] is True and marked['times'] is False and marked['grows'] is False

    plain = build_fill(chinese, 4, template='street')
    starts = [word['t0'] for word in plain['moments'][0]['en']]
    assert starts == sorted(starts) and starts[0] < starts[-1]
