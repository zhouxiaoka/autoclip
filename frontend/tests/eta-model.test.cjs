const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const eta = loadTs('etaModel.ts', {}, require('node:path').join(__dirname, '../src/features/studio'))

function memory() {
  const map = new Map()
  return {
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => { map.set(key, value) },
  }
}

test('median of last 5 same-provider successes beats builtin', () => {
  const storage = memory()
  for (const elapsed of [60, 120, 180, 240, 300]) {
    eta.recordSuccess({ provider: 'ollama', source_min: 10, elapsed_sec: elapsed }, storage)
  }
  // rates: 6,12,18,24,30 → median 18 sec/source_min
  assert.equal(eta.medianSecPerSourceMin('ollama', eta.readHistory(storage)), 18)
  const view = eta.estimate('ollama', 10, 1, 0, { storage, runKey: 'run-a' })
  assert.equal(view.initialMin, Math.max(1, Math.round((18 * 10) / 60)))
  assert.equal(view.overrun, false)
  assert.ok(view.etaMin >= 1)
})

test('builtin sec_per_source_min is used without history', () => {
  const storage = memory()
  const builtin = eta.builtinSecPerSourceMin('gemini')
  assert.ok(builtin > 0)
  const view = eta.estimate('gemini', 60, 1, 0, { storage, runKey: 'g1', builtin })
  assert.ok(view.initialMin >= 1)
  assert.equal(view.overrun, false)
})

test('overrun when elapsed exceeds 2× initial ETA', () => {
  const storage = memory()
  const view = eta.estimate('deepseek', 10, 1, 0, { storage, runKey: 'o1', builtin: 6 })
  // initial = max(1, round(60/60)) = 1 min = 60 sec; elapsed 121 → ratio > 2
  const later = eta.estimate('deepseek', 10, 1, 121, { storage, runKey: 'o1', builtin: 6 })
  assert.equal(later.overrun, true)
  assert.equal(later.etaMin, null)
  assert.equal(view.initialMin, later.initialMin)
})

test('history keeps at most 20 samples', () => {
  const storage = memory()
  for (let i = 0; i < 25; i++) {
    eta.recordSuccess({ provider: 'api88', source_min: 5, elapsed_sec: 50 + i }, storage)
  }
  assert.equal(eta.readHistory(storage).length, 20)
})
