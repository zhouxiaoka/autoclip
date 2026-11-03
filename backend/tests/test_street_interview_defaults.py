"""Street vertical and interview packaging defaults from the Dalio highlight packs.

A1–A4: 1080×1920 at about 2 Mbps, wrapping subtitles, fitZh not blocked, 64px / 10px stroke.
B5–B6: interview Street has no BGM bed; Chinese captions do not burn 「主持人：」.
"""
import json
import re
import subprocess
from pathlib import Path

from backend.services.studio.models import Packaging, Scene
from backend.services.studio.overlay_fill import build_fill
from backend.services.studio.packaging_render import scene_ass
from backend.services.studio.templates.registry import load_shipping
from backend.services.video_encoder import STREET_INTERVIEW_BITRATE, STREET_INTERVIEW_SIZE, packaging_h264_args

ROOT = Path(__file__).resolve().parents[2]
STREET = ROOT / 'backend' / 'assets' / 'templates' / 'street'
SANDBOX = ROOT / 'frontend' / 'tests' / 'vm-sandbox.cjs'
HOST = '主持人：现在只专注于面向用户的高度智能服务。'
GUEST = '黄仁勋：经济会增长八倍。'


def _block(css: str, selector: str) -> str:
    match = re.search(rf'{re.escape(selector)}\s*\{{([^}}]*)\}}', css)
    assert match, selector
    return match.group(1)


def _rate(args: list[str]) -> int:
    return int(args[args.index('-b:v') + 1])


def test_street_vertical_is_1080x1920_between_1_5_and_2_mbps():
    street = load_shipping()['street']
    assert street.canvas.overlay_px == STREET_INTERVIEW_SIZE == (1080, 1920)
    assert 1_500_000 <= STREET_INTERVIEW_BITRATE <= 2_000_000
    for name in ('libx264', 'h264_videotoolbox', 'h264_nvenc'):
        args = packaging_h264_args(*STREET_INTERVIEW_SIZE, visual='street', packaging='interview_zh', name=name)
        assert _rate(args) == STREET_INTERVIEW_BITRATE
        assert args[args.index('-maxrate') + 1] == str(STREET_INTERVIEW_BITRATE)
    software = packaging_h264_args(1080, 1920, visual='street', name='libx264')
    assert '-crf' not in software
    # A 720p frame is not the Street profile. Editorial keeps the shared CRF rate.
    small = packaging_h264_args(720, 1280, visual='street', name='libx264')
    assert '-crf' in small and '-b:v' not in small
    editorial = packaging_h264_args(1080, 1920, visual='editorial', packaging='interview_zh', name='libx264')
    assert editorial[editorial.index('-crf') + 1] == '20'
    podcast = packaging_h264_args(1080, 1920, packaging='podcast_en', name='libx264')
    assert '-crf' in podcast
    classic = packaging_h264_args(1080, 1920, packaging='interview_zh', name='libx264')
    assert _rate(classic) == STREET_INTERVIEW_BITRATE


def test_street_subtitles_wrap_and_fitzh_is_not_blocked():
    css = (STREET / 'style.css').read_text(encoding='utf-8')
    zh, en = _block(css, '#zh'), _block(css, '#en')
    assert 'nowrap' not in zh and 'nowrap' not in en
    assert 'white-space: normal' in zh and 'white-space: normal' in en
    assert '!important' not in zh
    assert 'font-size: 64px' in zh and 'font-size: 116px' not in css
    assert '-webkit-text-stroke: 10px #000' in zh
    script = (STREET / 'template.js').read_text(encoding='utf-8')
    assert 'function fitZh' in script and 'node.style.fontSize' in script
    assert 'trimTo' not in script and '…' not in script
    painted = _paint_street()
    assert painted['zh']['fontSize'] == '64px'
    assert painted['zh']['whiteSpace'] == 'normal' and painted['en']['whiteSpace'] == 'normal'
    assert '…' not in painted['zh']['html'] and '…' not in painted['en']['html']
    assert '不会停在半句' in painted['zh']['html']
    assert 'WAITING' in painted['en']['html']


def test_interview_street_has_no_bgm_bed():
    audio = load_shipping()['street'].audio
    assert audio.bgm == 'none' and audio.optional_bed is False


def test_interview_captions_omit_speaker_prefixes_by_default():
    street = Packaging(
        version=2, template='street', audience_language='zh', title_lines=['标题'],
        cues=[
            {'start': 0.2, 'end': 2.0, 'text': HOST, 'speaker': '主持人'},
            {'start': 2.0, 'end': 4.0, 'text': GUEST, 'speaker': '黄仁勋'},
        ],
    )
    body = _zh(build_fill(street, 4, template='street'))
    assert body.startswith('现在只专注') and '主持人' not in body
    assert '经济会增长八倍' in body and '黄仁勋' not in body

    kept = street.model_copy(update={'speaker_prefix': True})
    prefixed = _zh(build_fill(kept, 4, template='street'))
    # Phrase breaks drop the colon, but the name itself stays on the line.
    assert prefixed.startswith('主持人') and '黄仁勋' in prefixed

    scene = Scene(id='a', label='a', start=0, end=4)
    interview = Packaging(
        template='interview_zh', audience_language='zh', title_lines=['标题'],
        cues=[{'start': 0.2, 'end': 3.5, 'text': HOST, 'speaker': '主持人'}],
    )
    assert '主持人' not in _ass_body(scene_ass(interview, [scene], 0))
    forced = interview.model_copy(update={'speaker_prefix': True})
    assert '主持人' in _ass_body(scene_ass(forced, [scene], 0))

    editorial = Packaging(
        version=2, template='editorial', audience_language='zh', title_lines=['标题'],
        cues=[{'start': 0.2, 'end': 3.5, 'text': HOST, 'speaker': '主持人'}],
    )
    editorial_body = _zh(build_fill(editorial, 4, template='editorial'))
    assert editorial_body.startswith('主持人')


def _zh(fill: dict) -> str:
    return ''.join(phrase['s'] for moment in fill['moments'] for phrase in moment['zh'])


def _ass_body(doc: str) -> str:
    lines = [line.split(',,0,0,0,,', 1)[-1] for line in doc.splitlines() if line.startswith('Dialogue:')]
    return '\n'.join(lines)


def _paint_street() -> dict:
    words = 'EVERY TIME YOU OPEN A NEW DOOR THERE IS ANOTHER ONE WAITING'.split()
    fill = {
        'fps': 30,
        'audience_language': 'zh',
        'moments': [{
            't0': 0, 't1': 4, 'speaker': '主持人',
            'zh': [{'s': '这种智能会解锁更多机会而且不会停在半句', 't0': 0.2, 't1': 3.8}],
            'en': [{'w': word, 't0': 0.2, 't1': 3.8, 'key': False} for word in words],
            'en_screens': [[0, len(words)]],
        }],
    }
    script = r'''
const fs = require('fs')
const { runInSandbox } = require(process.argv[1])
function element() {
  const node = { textContent: '', className: '', style: {}, children: [], scrollWidth: 8000, scrollHeight: 80, _html: '' }
  Object.defineProperty(node, 'innerHTML', {
    get() { return node._html },
    set(value) { node._html = String(value); node.textContent = String(value).replace(/<[^>]+>/g, '') },
  })
  node.removeChild = (child) => { node.children = node.children.filter((item) => item !== child) }
  return node
}
const elements = new Map()
const document = { getElementById: (id) => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id) } }
const sandbox = { window: {}, document, console }
sandbox.window = sandbox
runInSandbox(fs.readFileSync(process.argv[2], 'utf8'), sandbox, { filename: 'street.js' })
sandbox.setData(JSON.parse(fs.readFileSync(0, 'utf8')))
sandbox.renderFrame(1)
const read = (id) => {
  const node = document.getElementById(id)
  return { html: node.innerHTML, fontSize: node.style.fontSize || '', whiteSpace: node.style.whiteSpace || '' }
}
process.stdout.write(JSON.stringify({ zh: read('zh'), en: read('en') }))
'''
    done = subprocess.run(
        ['node', '-e', script, str(SANDBOX), str(STREET / 'template.js')],
        input=json.dumps(fill), capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout)
