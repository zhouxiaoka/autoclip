const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { captionsAtWords } = require('./helpers/caption-at.cjs')

const repro = path.join(__dirname, '../../backend/tests/fixtures/editorial_repro')
const fill = JSON.parse(fs.readFileSync(path.join(repro, 'fill-ed1-92df5145.json'), 'utf8'))

function assertOneSentence(template) {
  const rows = captionsAtWords(template, fill)
  assert.equal(rows.length, fill.words.length)
  for (const row of rows) {
    const current = fill.words[row.index].text
    const visible = template === 'street' ? current.replace(/[，。、！？：；,.!?]+$/g, '') : current
    assert.match(row.html, new RegExp(visible.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.equal(row.html.includes('class="w"'), false)
    for (const other of fill.words) {
      if (other.text === current) continue
      assert.equal(row.html.includes(other.text.slice(0, 12)), false, `${template} cue ${row.index} still shows another sentence`)
    }
  }
}

test('editorial shows one repro sentence at a time', () => {
  assertOneSentence('editorial')
})

test('street shows one repro sentence at a time', () => {
  assertOneSentence('street')
})

test('a phrase is one line, and the next phrase replaces it', () => {
  const paged = {
    fps: 30,
    T: 2,
    words: [
      { text: '有史以来最好的12个月', start_frame: 0, end_frame: 30, emphasis: '' },
      { text: '我们显然犯了一些错误', start_frame: 30, end_frame: 60, emphasis: '错误' },
    ],
  }
  for (const template of ['editorial', 'street']) {
    const rows = captionsAtWords(template, paged)
    assert.equal(rows[0].html.includes('<br>'), false)
    assert.equal(rows[0].html.includes('有史以来最好的12个月'), true)
    assert.equal(rows[0].html.includes('我们显然'), false)
    assert.equal(rows[0].html.includes('class="w"'), false)
    assert.equal(rows[1].html.includes('我们显然犯了一些错误'), true)
    assert.equal(rows[1].html.includes('<br>'), false)
    assert.equal(rows[1].html.includes('有史以来'), false)
  }
})
