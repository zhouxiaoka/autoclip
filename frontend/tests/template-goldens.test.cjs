const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

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
  vm.runInNewContext(fs.readFileSync(path.join(root, template, 'template.js'), 'utf8'), sandbox, { filename: template + '.js' })
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
  }))
}

test('editorial and street match the golden frames at fixed timestamps', () => {
  const actual = JSON.parse(JSON.stringify({ editorial: sample('editorial'), street: sample('street') }))
  const expected = JSON.parse(fs.readFileSync(goldenPath, 'utf8'))
  assert.deepEqual(actual, expected)
  const streetAt = actual.street.find(frame => frame.t === 1.0)
  assert.equal(streetAt.rects.filter(rect => rect.slot === 'sticker').length, 2)
  assert.equal(JSON.stringify(streetAt).includes('不该出现'), false)
})
