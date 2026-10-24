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


def _render(template, fill, times=('0.5', '1.6', '3.0')):
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
        input=json.dumps({'fill': fill, 'times': [str(t) for t in times]}),
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


def test_emphasis_is_a_word_and_the_headline_stays_on_the_cover():
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
    assert zh['html'] == 'AI现在就能干一半' and zh['className'] == ''
    assert re.search(r'class="w k[^"]*">AI<', source)
    assert not re.search(r'class="w k[^"]*">half<', source, re.I)
    # The cue never named a speaker, and the topic is the cover title, so the bottom label is empty.
    assert painted['0.5']['topic']['text'] == ''
    assert painted['0.5']['title']['text'] == ''
    assert '白领工作会最先没' not in json.dumps(painted['0.5'], ensure_ascii=False)
    assert not any(rect['slot'] in ('hook', 'title') for rect in painted['0.5']['rects'])

    editorial, _ = _paint(
        'editorial',
        title_lines=['AI是五层蛋糕，', '最底层是能源'],
        deck='Jensen Huang on the five-layer cake',
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        emphasis=[{'at': 0.2, 'text': '五层蛋糕'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
    )
    frames = _render('editorial', editorial)
    assert frames['0.5']['hook']['html'] == '' and frames['3.0']['hook']['html'] == ''
    assert 'AI是五层蛋糕' not in json.dumps(frames['0.5'], ensure_ascii=False)
    assert not any(rect['slot'] == 'hook' for rect in frames['0.5']['rects'])
    # Preview: 「AI其实」 stays sans and only the key words take the gold serif.
    # A screen holds about 6-8 characters, so the sentence turns once: AI其实是 / 一块五层蛋糕.
    first = re.sub(r'<[^>]+>', '', frames['0.5']['zh']['html'])
    second = re.sub(r'<[^>]+>', '', frames['3.0']['zh']['html'])
    assert first + second == 'AI其实是一块五层蛋糕', (first, second)
    accented = re.findall(r'class="p acc[^"]*"[^>]*>([^<]*)<', frames['0.5']['zh']['html'] + frames['3.0']['zh']['html'])
    assert accented == ['五层蛋糕'], frames['3.0']['zh']['html']
    # Each screen carries its own part of the English: AI is a / five layer cake.
    assert 'five' in frames['3.0']['en']['html'] and 'five' not in frames['0.5']['en']['html']
    assert frames['0.5']['kick']['text'] == 'Jensen Huang on the five-layer cake'
    assert frames['0.5']['trk']['text'] == 'FIVE-LAYER CAKE · JENSEN HUANG'
    assert any(rect['slot'] == 'kicker' for rect in frames['3.0']['rects'])
    assert any(rect['slot'] == 'credit' for rect in frames['3.0']['rects'])

    # Captions-off drops cues inside build_fill. The headline and the street topic stay off the clip.
    off_editorial = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['AI是五层蛋糕，', '最底层是能源'],
        kicker='访谈', speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
        captions_enabled=False,
    )
    hidden = _render('editorial', paint_fill(build_fill(off_editorial, 8, template='editorial'), off_editorial, 'editorial'))
    assert hidden['3.0']['hook']['html'] == ''
    assert 'AI是五层蛋糕' not in json.dumps(hidden['3.0'], ensure_ascii=False)
    assert hidden['3.0']['zh']['html'] == ''
    assert not any(rect['slot'] == 'hook' for rect in hidden['3.0']['rects'])
    off_street = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['白领工作会最先没'],
        speakers=[{'at': 0, 'name': '马斯克', 'role': '特斯拉'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI现在就能干一半', 'original': 'AI can do half or more'}],
        captions_enabled=False,
    )
    blank = _render('street', paint_fill(build_fill(off_street, 8, template='street'), off_street, 'street'))
    assert blank['0.5']['zh']['html'] == ''
    assert blank['0.5']['title']['text'] == '' and blank['3.0']['title']['text'] == ''
    # Captions off: no cue says who is talking, and the topic is not burned in its place.
    assert blank['0.5']['topic']['text'] == '' and blank['3.0']['topic']['text'] == ''
    assert '马斯克' not in blank['3.0']['topic']['text']
    assert '白领工作会最先没' not in json.dumps(blank['0.5'], ensure_ascii=False)


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
        # The Chinese line stays a white caption. Lime is the English keyword, not a yellow title.
        assert _near(rows, (255, 255, 255)) > 40, name
        assert _near(rows, STREET_MARK) <= 40, name
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
    transcript = [
        (0.2, 2.0, 'I think for most people this opens more opportunities?'),
        (2.0, 6.0, '>> Jensen says the economy grows 8 times'),
    ]
    fill = paint_fill(build_fill(model, 8, template='street', transcript=transcript), model, 'street')
    # A long host sentence pages into more than one screen; every page keeps that cue's speaker.
    speakers = [word['speaker'] for word in fill['words']]
    assert speakers[0] == '主持人' and speakers[-1] == '黄仁勋'
    assert set(speakers) == {'主持人', '黄仁勋'}
    host = [word for word in fill['words'] if word['speaker'] == '主持人']
    guest = [word for word in fill['words'] if word['speaker'] == '黄仁勋']
    assert any(word['emphasis'] == '更多机会' for word in host)
    assert any(word['emphasis'] == '8 倍' for word in guest)
    painted = _render('street', fill)
    assert painted['0.5']['topic']['text'] == '主持人'
    assert '更闲的工作' not in painted['0.5']['topic']['text']
    assert painted['3.0']['topic']['text'] == '黄仁勋'
    assert '更闲的工作' not in painted['3.0']['topic']['text']
    eight = next(word for word in fill['words'] if '8' in word['text'])
    spoken = f'{(eight["start_frame"] + 1) / fill["fps"]:.3f}'
    at_eight = _render('street', fill, times=[spoken, '0.5'])
    assert re.search(r'class="w k[^"]*">8<', at_eight[spoken]['en']['html'])
    assert 'class="w k' not in at_eight['0.5']['en']['html']
    assert '8' not in painted['0.5']['en']['html']
    editorial_fill = paint_fill(build_fill(model, 8, template='editorial', transcript=transcript), model, 'editorial')
    frames = _render('editorial', editorial_fill)
    assert frames['0.5']['kick']['text'] == 'Jensen Huang on the five-layer cake'
    assert frames['0.5']['trk']['text'] == 'FIVE-LAYER CAKE · JENSEN HUANG'
    assert frames['3.0']['trk']['text'] == frames['0.5']['trk']['text']
    quiet = {**editorial_fill, 'words': [], 'moments': []}
    still = _render('editorial', quiet)
    assert not any(rect['slot'] == 'hook' for rect in frames['0.5']['rects'])
    assert not any(rect['slot'] == 'hook' for rect in still['0.5']['rects'])
    assert any(rect['slot'] == 'kicker' for rect in frames['0.5']['rects'])
    assert any(rect['slot'] == 'credit' for rect in still['0.5']['rects'])
    street_css = (TEMPLATES / 'street' / 'style.css').read_text(encoding='utf-8')
    assert 'text-align: center' in street_css and 'font-size: 48px' in street_css and '#D7FF3A' in street_css
    assert 'font-size: 100px' not in street_css and '#zh.k' not in street_css
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
    transcript = [
        (0.2, 2.0, 'I completely disagree?'),
        (2.0, 6.0, '>> Jensen says the dream is still alive'),
    ]
    fill = build_fill(Packaging.model_validate(result), 8, template='street', transcript=transcript)
    painted = _render('street', fill)
    assert painted['0.5']['topic']['text'] == ''
    assert 'Jensen' not in painted['0.5']['topic']['text']
    assert painted['3.0']['topic']['text'] == '黄仁勋'
    assert '黄仁勋谈梦想' not in painted['3.0']['topic']['text']


def test_street_paints_the_listing_guest_and_not_the_cover_title():
    """Windows nameplate_or_speakers: empty model speakers, Latin guest, cover title stays off the clip."""
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio import packaging as packaging_mod

    lines = [
        {'start': 0.0, 'end': 4.0, 'text': 'You said we did not have our best last 12 months'},
        {'start': 9.0, 'end': 14.0, 'text': 'Best 12 months yet'},
    ]

    def call(_prompt, _data):
        return {
            'title_lines': ['未来十二个月将是最佳'], 'accent_line': 0,
            'segments': [
                {'from': 0, 'to': 0, 'text': '你说我们过去没有最好的那12个月'},
                {'from': 1, 'to': 1, 'text': '研究我们落后于目标'},
            ],
            'speakers': [], 'tags': [], 'highlights': [], 'marks': [],
        }

    result = packaging_mod.build_packaging(
        {'title': '', 'hook': ''}, lines, platform_strategy('douyin'),
        known_names='Sam Altman on Astra, AGI, and the future of OpenAI Sources Podcast', call=call,
    )
    assert [item['name'] for item in result['speakers']] == ['Sam Altman']
    transcript = [
        (0.0, 4.0, 'You said we did not have our best last 12 months?'),
        (9.0, 14.0, '>> Best 12 months yet'),
    ]
    model = Packaging.model_validate(result)
    fill = paint_fill(build_fill(model, 14, template='street', transcript=transcript), model, 'street')
    painted = _render('street', fill, times=['1.0', '10.0'])
    assert painted['1.0']['topic']['text'] == ''
    assert painted['10.0']['topic']['text'] == 'Sam Altman'
    assert painted['10.0']['title']['text'] == ''
    blob = json.dumps(painted['10.0'], ensure_ascii=False)
    assert '未来十二个月将是最佳' not in blob
    assert any(rect['slot'] == 'hook' for rect in painted['10.0']['rects'])


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


def _head_zone(template: str) -> tuple[int, int]:
    text = (TEMPLATES / template / 'template.yaml').read_text(encoding='utf-8')
    match = re.search(r'head_zone:\s*\[(\d+),\s*(\d+)\]', text)
    assert match, template
    return int(match.group(1)), int(match.group(2))


def _hits_zone(rect: dict, zone: tuple[int, int]) -> bool:
    return rect['y'] < zone[1] and rect['y'] + rect['h'] > zone[0]


def test_street_english_keeps_the_sentence_up_across_its_phrases():
    # The preview keeps the whole English sentence up while its Chinese phrases change
    # (29 Chinese phrases, 14 English lines). It used to change with every phrase.
    packaging = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['话题'],
        cues=[{
            'start': 0, 'end': 8,
            'text': '对大多数人来说，智能会解锁更多机会',
            'original': 'FOR MOST PEOPLE INTELLIGENCE UNLOCKS MORE OPPORTUNITY',
        }],
    )
    fill = build_fill(packaging, 8, template='street')
    phrases = fill['moments'][0]['zh']
    assert len(phrases) >= 2
    early = f"{phrases[0]['t0'] + 0.05:.3f}"
    late = f"{phrases[-1]['t0'] + 0.05:.3f}"
    painted = _render('street', fill, times=[early, late])
    for at in (early, late):
        text = re.sub(r'<[^>]+>', '', painted[at]['en']['html'])
        assert text == 'FOR MOST PEOPLE INTELLIGENCE UNLOCKS MORE OPPORTUNITY'
    # Words still light up as they are spoken.
    assert 'class="w now">FOR' in painted[early]['en']['html']
    assert 'class="w past">FOR' in painted[late]['en']['html']
    quiet = {**fill, 'moments': [{**fill['moments'][0], 'en': []}]}
    blank = _render('street', quiet, times=[late])
    assert blank[late]['en']['html'] == ''
    assert all(rect['slot'] != 'source' for rect in blank[late]['rects'])


def test_captions_off_does_not_paint_a_title_on_the_clip():
    street = Packaging(
        version=2, template='street', audience_language='zh',
        title_lines=['AI来了会更闲？', '我完全不同意'],
        captions_enabled=False,
        cues=[{'start': 0.2, 'end': 4, 'text': '原话'}],
    )
    fill = paint_fill(build_fill(street, 8, template='street'), street, 'street')
    painted = _render('street', fill, times=['1.0', '3.0', '4.0'])
    zone = _head_zone('street')
    assert zone == (0, 1290)
    for stamp in ('1.0', '3.0', '4.0'):
        assert painted[stamp]['title']['text'] == ''
        assert painted[stamp]['topic']['text'] == ''
        assert 'AI来了会更闲' not in json.dumps(painted[stamp], ensure_ascii=False)
        assert not any(rect['slot'] in ('title', 'hook') for rect in painted[stamp]['rects'])
        assert all(not _hits_zone(rect, zone) for rect in painted[stamp]['rects'])

    editorial = Packaging(
        version=2, template='editorial', audience_language='zh',
        title_lines=['AI来了会更闲？', '我完全不同意'],
        captions_enabled=False,
    )
    frames = _render(
        'editorial',
        paint_fill(build_fill(editorial, 8, template='editorial'), editorial, 'editorial'),
        times=['1.0', '3.0'],
    )
    ezone = _head_zone('editorial')
    assert ezone == (280, 820)
    for stamp in ('1.0', '3.0'):
        assert frames[stamp]['hook']['html'] == ''
        assert 'AI来了会更闲' not in json.dumps(frames[stamp], ensure_ascii=False)
        assert not any(rect['slot'] == 'hook' for rect in frames[stamp]['rects'])
        assert all(not _hits_zone(rect, ezone) for rect in frames[stamp]['rects'])


def _bright_runs(rows, top, bottom, left=30, right=1050):
    """Row runs in [top, bottom) holding caption fill (white or lime), with their x extent."""
    runs, current = [], None
    for y in range(top, bottom):
        row = rows[y]
        xs = [x // 3 for x in range(left * 3, right * 3, 3) if row[x + 1] > 200 and row[x] + row[x + 1] + row[x + 2] > 520]
        if len(xs) >= 3:
            if current and current[1] == y - 1:
                current[1] = y
                current[2], current[3] = min(current[2], xs[0]), max(current[3], xs[-1])
            else:
                current = [y, y, xs[0], xs[-1]]
                runs.append(current)
    return [run for run in runs if run[1] - run[0] >= 12]


def test_street_caption_is_the_preview_size_and_shrinks_only_on_overflow(tmp_path):
    if subprocess.run(['timeout', '5', CHROME, '--version'], capture_output=True).returncode != 0:
        pytest.skip('chrome unavailable')
    # _shoot loads Anton from faces.css and Noto from the bundled TTF. CI has fonts-noto-cjk
    # but not a system Anton face, so gating on fc-list skipped this regression there.
    fonts = ROOT / 'backend' / 'assets' / 'fonts'
    if not (fonts / 'preview' / 'faces.css').is_file() or not (fonts / 'NotoSansSC.ttf').is_file():
        pytest.skip('preview fonts unavailable')
    measured = {}
    for name, text in (('short', 'AI现在就能干一半'), ('full', '这种智能会解锁更多机')):
        packaging = Packaging(
            version=2, template='street', audience_language='zh', title_lines=['白领工作会最先没'],
            cues=[{'start': 0.2, 'end': 4.0, 'text': text, 'original': 'AI CAN DO HALF OR MORE'}],
        )
        fill = paint_fill(build_fill(packaging, 4.0, template='street'), packaging)
        assert [phrase['s'] for phrase in fill['moments'][0]['zh']] == [text]
        dest = tmp_path / f'{name}.png'
        _shoot('street', fill, 1.0, dest)
        _width, _height, rows = _png_size_and_rows(dest)
        runs = _bright_runs(rows, 1300, 1520)
        assert len(runs) == 2, (name, runs)
        measured[name] = runs
    zh, en = measured['short']
    assert abs(zh[0] - 1326) <= 16 and 32 <= zh[1] - zh[0] + 1 <= 56, zh
    assert abs((zh[2] + zh[3]) / 2 - 540) <= 8, zh
    assert abs(en[0] - 1406) <= 20, en
    # A caption-sized line stays inside the 1000px column. The English line does not jump when the phrase grows.
    full_zh, full_en = measured['full']
    assert 32 <= full_zh[1] - full_zh[0] + 1 <= 56 and full_zh[3] - full_zh[2] <= 1000, full_zh
    assert abs(full_en[0] - en[0]) <= 8, (full_en, en)


def test_mac_acceptance_captions_stay_and_cover_titles_do_not():
    """The 1.5.7 Mac frames kept the cover title off, then painted the caption as a title.

    Editorial 「走过弯路」 was a whole-line gold serif above the English line.
    Street 「我们公司确实走过弯路」 was a 100px yellow billboard on the black lower half.
    Both strings are the dialogue caption and must remain. The cover lines must not.
    """
    editorial, _ = _paint(
        'editorial',
        title_lines=['我们曾掉队', '现在执行力最强'],
        emphasis=[{'at': 0.2, 'text': '走过弯路'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': '走过弯路', 'original': 'had some missteps as a company'}],
    )
    frame = _render('editorial', editorial, times=['1.0'])['1.0']
    painted = json.dumps(frame, ensure_ascii=False)
    assert '我们曾掉队' not in painted and '现在执行力最强' not in painted
    assert '走过弯路' in frame['zh']['html']
    assert 'missteps' in frame['en']['html']
    assert 'class="p acc' not in frame['zh']['html']
    assert frame['hook']['html'] == ''
    assert not any(rect['slot'] == 'hook' for rect in frame['rects'])

    street, _ = _paint(
        'street',
        title_lines=['我们曾掉队', '现在执行力全球最强'],
        emphasis=[{'at': 0.2, 'text': '我们公司确实走过弯路'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': '我们公司确实走过弯路', 'original': 'I think we clearly had some missteps as'}],
    )
    shot = _render('street', street, times=['1.0'])['1.0']
    body = json.dumps(shot, ensure_ascii=False)
    assert '我们曾掉队' not in body and '现在执行力全球最强' not in body
    assert shot['zh']['html'] == '我们公司确实走过弯路' and shot['zh']['className'] == ''
    assert 'missteps' in shot['en']['html']
    assert shot['title']['text'] == ''
    css = (TEMPLATES / 'street' / 'style.css').read_text(encoding='utf-8')
    assert 'font-size: 48px' in css and 'font-size: 100px' not in css
