const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')

const root = path.join(__dirname, '../../backend/assets/templates')
const goldenPath = path.join(__dirname, 'fixtures/template-goldens.json')

function element() {
  const node = { innerHTML: '', textContent: '', className: '', style: {}, children: [] }
  node.appendChild = child => { node.children.push(child) }
  return node
}

function load(template) {
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
  runInSandbox(fs.readFileSync(path.join(root, template, 'template.js'), 'utf8'), sandbox, { filename: template + '.js' })
  return sandbox
}

const fills = {
  editorial: {
    fps: 30,
    kicker: '访谈',
    hook: { text: '好的投资人像飞行教练', until_frame: 36 },
    words: [
      { text: '好的', start_frame: 12, end_frame: 24, emphasis: '' },
      { text: '投资人', start_frame: 24, end_frame: 48, emphasis: '投资人' },
      { text: '像', start_frame: 48, end_frame: 60, emphasis: '' },
    ],
    gloss: [{ id: 'g1', title: '飞行教练', body: '带着人起飞', start_frame: 48, end_frame: 90 }],
    number: { value: 70, unit: '秒', start_frame: 30, end_frame: 54, hold_frame: 72, steps: 4 },
  },
  street: {
    fps: 30,
    safe_area: 'xiaohongshu',
    title_lines: ['街头一问', '七十秒'],
    words: [
      { text: '你', start_frame: 0, end_frame: 10, emphasis: '' },
      { text: '怎么', start_frame: 10, end_frame: 20, emphasis: '' },
      { text: '看', start_frame: 20, end_frame: 40, emphasis: '看' },
      { text: '这个', start_frame: 40, end_frame: 55, emphasis: '' },
    ],
    number: { value: 70, unit: '秒', start_frame: 15, end_frame: 45, hold_frame: 60, steps: 5 },
    stickers: [
      { id: 's1', text: '追问', start_frame: 20, end_frame: 50, x: 480, y: 360 },
      { id: 's2', text: '第二枚', start_frame: 20, end_frame: 40, x: 500, y: 460 },
      { id: 's3', text: '不该出现', start_frame: 20, end_frame: 50, x: 40, y: 40 },
    ],
  },
}

const times = [0, 0.5, 1.0, 1.6, 2.4]

function sample(template) {
  const page = load(template)
  page.setData(fills[template])
  return times.map(time => ({
    t: time,
    hash: page.renderFrame(time),
    rects: page.occupiedRects(time),
    sub: page.document.getElementById('zh').innerHTML,
    topic: page.document.getElementById('topic') ? page.document.getElementById('topic').textContent : '',
  }))
}

test('editorial and street match the golden frames at fixed timestamps', () => {
  const actual = JSON.parse(JSON.stringify({ editorial: sample('editorial'), street: sample('street') }))
  // UPDATE_TEMPLATE_GOLDENS=1 rewrites the fixture after an intended template change.
  if (process.env.UPDATE_TEMPLATE_GOLDENS) fs.writeFileSync(goldenPath, JSON.stringify(actual, null, 2) + '\n')
  const expected = JSON.parse(fs.readFileSync(goldenPath, 'utf8'))
  assert.deepEqual(actual, expected)
  const streetAt = actual.street.find(frame => frame.t === 1.0)
  assert.equal(streetAt.rects.filter(rect => rect.slot === 'sticker').length, 2)
  assert.equal(JSON.stringify(streetAt).includes('不该出现'), false)
})

test('the clip does not burn the cover title', () => {
  // Editorial leaves the magazine headline off the clip. The deck is not in this fill.
  // Street captions-off no longer paints an opening title sticker or the topic label.

  for (const template of ['editorial', 'street']) {
    const page = load(template)
    const fill = {...fills[template], words: []}
    page.setData(fill)
    page.renderFrame(0)
    assert.equal(page.occupiedRects(0).find(rect => rect.slot === 'hook'), undefined, template)
    if (template === 'editorial') {
      assert.equal(page.document.getElementById('zh').innerHTML, '')
      assert.equal(page.document.getElementById('h-l').innerHTML, '')
      page.renderFrame(3)
      assert.equal(page.document.getElementById('h-l').innerHTML, '')
      assert.equal(page.occupiedRects(3).find(rect => rect.slot === 'hook'), undefined)
    } else {
      assert.equal(page.document.getElementById('zh').innerHTML, '')
      assert.equal(page.document.getElementById('title-hook').textContent, '')
      assert.equal(page.document.getElementById('topic').textContent, '')
      page.renderFrame(4)
      assert.equal(page.document.getElementById('title-hook').textContent, '')
      assert.equal(page.document.getElementById('topic').textContent, '')
    }
  }
})

test('a moving progress bar is not a new overlay frame', () => {
  const street = load('street')
  street.setData({
    fps: 30,
    T: 90,
    title_lines: ['话题'],
    topic: '话题',
    speakers: [{name: '黄仁勋'}],
    moments: [{
      t0: 0,
      t1: 90,
      speaker: '黄仁勋',
      zh: [
        {s: '第一句完整的话', t0: 0, t1: 30, key: true, acc: false},
        {s: '第二句完整的话', t0: 30, t1: 60, key: false, acc: false},
        {s: '第三句完整的话', t0: 60, t1: 90, key: false, acc: false},
      ],
      en: [
        {w: 'FIRST', t0: 0, t1: 30, key: true},
        {w: 'SECOND', t0: 30, t1: 60, key: false},
        {w: 'THIRD', t0: 60, t1: 90, key: false},
      ],
    }],
  })
  let runs = 0
  let prev = null
  for (let i = 0; i < 90 * 30; i++) {
    const hash = street.renderFrame(i / 30)
    if (hash !== prev) {
      runs += 1
      prev = hash
    }
  }
  assert.ok(runs < 40, `street captured ${runs} states in 90s`)

  const editorial = load('editorial')
  editorial.setData(fills.editorial)
  assert.equal(editorial.renderFrame(0.5), editorial.renderFrame(0.53))
})

test('street and editorial css match the measured preview', () => {
  const street = fs.readFileSync(path.join(root, 'street', 'style.css'), 'utf8')
  const editorial = fs.readFileSync(path.join(root, 'editorial', 'style.css'), 'utf8')
  assert.match(street, /#field[\s\S]*top:\s*1290px/)
  assert.match(street, /#zh[\s\S]*font-size:\s*48px/)
  assert.doesNotMatch(street, /#zh\.k/)
  assert.doesNotMatch(street, /font-size:\s*100px/)
  assert.match(street, /-webkit-text-stroke:\s*4px #000/)
  assert.match(street, /text-shadow:\s*0 2px 0 #000/)
  assert.match(street, /#en \.w\.k\.past, #en \.w\.k\.now \{ color: #D7FF3A/)
  assert.match(street, /#en[\s\S]*Anton/)
  assert.match(street, /#en[\s\S]*font-size:\s*36px/)
  assert.match(street, /#topic[\s\S]*top:\s*1812px/)
  assert.match(street, /border-left:\s*10px solid #D7FF3A/)
  assert.match(street, /#prog[\s\S]*height:\s*12px/)
  assert.match(street, /NotoSansSC\.ttf/)
  assert.doesNotMatch(street, /NotoSansSC-Medium/)
  assert.match(editorial, /#scrim[\s\S]*height:\s*1000px/)
  assert.match(editorial, /#hook[\s\S]*top:\s*1110px/)
  assert.match(editorial, /Instrument Serif/)
  assert.match(editorial, /#F2D98C/)
  assert.match(editorial, /#F4EFE6/)
  assert.match(editorial, /#C7243A/)
  assert.match(editorial, /Noto Serif SC/)
  assert.match(editorial, /letter-spacing:\s*\.34em/)
  assert.match(editorial, /#cap[\s\S]*top:\s*1560px/)
  assert.match(editorial, /#folio[\s\S]*top:\s*1842px/)
  assert.match(editorial, /skewX\(-9deg\)/)
  assert.doesNotMatch(editorial, /text-shadow/)
  assert.doesNotMatch(editorial, /-webkit-text-stroke/)
  assert.match(editorial, /NotoSansSC\.ttf/)
})
