"""Overlay motion survives the changed-frames capture: what the preview animates, the output animates."""
import json
import subprocess
from pathlib import Path

from backend.services.studio import packaging_html as html
from backend.services.studio.models import Packaging
from backend.services.studio.overlay_fill import build_fill, paint_fill

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'backend' / 'assets' / 'templates'
SANDBOX = ROOT / 'frontend' / 'tests' / 'vm-sandbox.cjs'

_SCRIPT = r'''
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
const out = []
for (let i = 0; i < payload.frames; i++) {
  const t = i / payload.fps
  const hash = sandbox.renderFrame(t)
  const zh = document.getElementById('zh')
  const en = document.getElementById('en')
  out.push({ hash, transform: zh.style.transform || '', zh: zh.innerHTML, en: en.innerHTML, text: en.textContent })
}
process.stdout.write(JSON.stringify(out))
'''


def frames(template: str, fill: dict, count: int, fps: int = 30) -> list[dict]:
    done = subprocess.run(
        ['node', '-e', _SCRIPT, str(SANDBOX), template, str(TEMPLATES)],
        input=json.dumps({'fill': fill, 'frames': count, 'fps': fps}),
        capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)


def captured(rows: list[dict]) -> list[dict]:
    """The frames capture_changed would screenshot: one per run of equal hashes."""
    runs = html.collapse_hashes([row['hash'] for row in rows])
    return [dict(rows[run['index']], index=run['index'], count=run['count']) for run in runs]


def _street(**kwargs):
    body = dict(version=2, template='street', audience_language='zh', title_lines=['标题'])
    body.update(kwargs)
    packaging = Packaging(**body)
    return paint_fill(build_fill(packaging, 6, template='street'), packaging, 'street')


def _scale(row) -> float:
    return float(row['transform'][len('scale('):-1]) if row['transform'] else 1.0


def test_street_pop_eases_out_over_three_frames_in_the_captured_movie():
    fill = _street(cues=[
        {'start': 0.0, 'end': 2.0, 'text': '我真的觉得', 'original': 'I really think'},
        {'start': 2.0, 'end': 4.0, 'text': '这个想法很好', 'original': 'this is a good idea'},
    ])
    shots = captured(frames('street', fill, 120))
    for start in (0, 60):
        ease = [round(_scale(shot), 2) for shot in shots if start <= shot['index'] < start + 6]
        # Preview: 1.18 -> 1.05 -> 1.01 -> 1.0 within about 3 frames, not three frozen 1.18 frames then a jump.
        assert ease[0] == 1.18
        assert len(ease) >= 4, ease
        assert ease == sorted(ease, reverse=True)
        assert 1.03 <= ease[1] <= 1.10 and 1.0 <= ease[2] <= 1.03 and ease[-1] == 1.0
        first = next(shot for shot in shots if shot['index'] == start)
        assert first['count'] == 1


def _editorial(**kwargs):
    body = dict(version=2, template='editorial', audience_language='zh', title_lines=['标题'], deck='Deck')
    body.update(kwargs)
    packaging = Packaging(**body)
    return paint_fill(build_fill(packaging, 6, template='editorial'), packaging, 'editorial')


def test_editorial_underline_sweeps_in_and_the_screen_pops_within_four_frames():
    import re

    fill = _editorial(cues=[
        {'start': 0.0, 'end': 1.6, 'text': '我们包了架飞机', 'original': 'We chartered a plane'},
        {'start': 1.6, 'end': 3.2, 'text': '把他们接过去', 'original': 'to fly them over'},
    ])
    rows = frames('editorial', fill, 120)
    shots = captured(rows)
    for start in (0, 48):
        run = [shot for shot in shots if start <= shot['index'] < start + 8]
        sweep = [int(re.search(r'--u:(\d+)%', shot['zh']).group(1)) for shot in run]
        # Preview: the bar draws over about 4 frames, then holds full; not a bar that is simply there.
        assert sweep[:4] == [25, 50, 75, 100], sweep
        scale = [_scale(shot) for shot in run]
        assert 1.02 <= scale[0] <= 1.06 and scale == sorted(scale, reverse=True) and scale[3] == 1.0, scale
    # Bounded capture: the motion adds at most 3 frames per phrase and per screen, not a frame per tick.
    still = [re.sub(r'--u:\d+%', '', row['hash']).rsplit('|', 1)[0] for row in rows]
    baseline = len(html.collapse_hashes(still))
    phrases = sum(len(moment['zh']) for moment in fill['moments'])
    assert len(shots) - baseline <= 3 * (phrases + len(fill['moments'])), (len(shots), baseline)
