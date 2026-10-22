"""Editorial and street overlays match the editing-style preview, not the old bars."""
import json
import os
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

# Yellow-green key word (street) and the gold rule / quote (editorial).
STREET_MARK = (0xD6, 0xEF, 0x4A)
EDITORIAL_GOLD = (0xE6, 0xC5, 0x6A)


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
    return { html: node.innerHTML, text: node.textContent, display: node.style.display || '' }
  }
  frames[String(t)] = {
    hook: read('hook'),
    sub: read('sub'),
    source: read('source'),
    lineA: read('line-a'),
    lineB: read('line-b'),
    tick: read('tick'),
    kicker: read('kicker'),
    rects: sandbox.occupiedRects(t),
  }
}
process.stdout.write(JSON.stringify(frames))
'''
    done = subprocess.run(
        ['node', '-e', script, str(SANDBOX), template, str(TEMPLATES)],
        input=json.dumps({'fill': fill, 'times': ['0.5', '3.0']}),
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
         '--force-device-scale-factor=1', '--window-size=720,1280', f'--screenshot={dest}', driver.as_uri()],
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
    assert original.count('\n') == 1
    assert original.endswith('…')
    assert all(word['original'] == original for word in fill['words'])
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
    sub = painted['0.5']['sub']['html']
    source = painted['0.5']['source']['html']
    assert '<em>AI</em>' in sub and '<em>AI现在就能干一半</em>' not in sub
    assert '<em>AI</em>' in source
    assert painted['0.5']['lineA']['text'] == '马斯克：白领工作会最先没'
    assert painted['0.5']['lineB']['text'] == '特斯拉'
    assert painted['0.5']['tick']['display'] == 'block'
    assert any(rect['slot'] == 'hook' and rect['y'] > 900 for rect in painted['0.5']['rects'])

    editorial, _ = _paint(
        'editorial',
        title_lines=['AI是五层蛋糕，', '最底层是能源'],
        kicker='访谈',
        speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        emphasis=[{'at': 0.2, 'text': '五层蛋糕'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
    )
    frames = _render('editorial', editorial)
    assert frames['0.5']['hook']['text'] == 'AI是五层蛋糕，\n最底层是能源'
    assert frames['3.0']['hook']['text'] == frames['0.5']['hook']['text']
    assert '<em>五层蛋糕</em>' in frames['0.5']['sub']['html']
    assert 'five layer cake' in frames['0.5']['source']['html']
    assert frames['0.5']['kicker']['text'] == '黄仁勋  英伟达'
    hook = next(rect for rect in frames['3.0']['rects'] if rect['slot'] == 'hook')
    assert hook['y'] >= 700

    # Captions-off drops cues inside build_fill and clears the painted hook / title lines.
    # The classic title is burned beside the overlay; the template must not keep either.
    off_editorial = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['AI是五层蛋糕，', '最底层是能源'],
        kicker='访谈', speakers=[{'at': 0, 'name': '黄仁勋', 'role': '英伟达'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI其实是一块五层蛋糕', 'original': 'AI is a five layer cake'}],
        captions_enabled=False,
    )
    hidden = _render('editorial', paint_fill(build_fill(off_editorial, 8, template='editorial'), off_editorial))
    assert hidden['3.0']['hook']['text'] == ''
    assert hidden['3.0']['sub']['html'] == ''
    off_street = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['白领工作会最先没'],
        speakers=[{'at': 0, 'name': '马斯克', 'role': '特斯拉'}],
        cues=[{'start': 0.2, 'end': 4.0, 'text': 'AI现在就能干一半', 'original': 'AI can do half or more'}],
        captions_enabled=False,
    )
    blank = _render('street', paint_fill(build_fill(off_street, 8, template='street'), off_street))
    assert blank['0.5']['lineA']['text'] == '' and blank['0.5']['lineB']['text'] == ''
    assert blank['0.5']['sub']['html'] == ''
    assert blank['0.5']['tick']['display'] == 'none'


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
