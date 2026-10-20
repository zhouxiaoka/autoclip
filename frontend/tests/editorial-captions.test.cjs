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
    assert.match(row.html, new RegExp(current.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
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
