const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const ts = require('typescript')

const root = path.resolve(__dirname, '../..')
const hintSource = fs.readFileSync(path.join(root, 'frontend/src/features/diagnostics/failureHint.ts'), 'utf8')
const viewSource = fs.readFileSync(path.join(root, 'frontend/src/features/diagnostics/FailureHint.tsx'), 'utf8')
const compiled = ts.transpileModule(hintSource, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
const hintModule = { exports: {} }
const loadHint = new Function('module', 'exports', 'localStorage', compiled)
loadHint(hintModule, hintModule.exports, { getItem: () => null, setItem: () => undefined })
const hint = hintModule.exports

test('the startup card and the import prompt are gone', () => {
  const app = fs.readFileSync(path.join(root, 'frontend/src/App.tsx'), 'utf8')
  const importer = fs.readFileSync(path.join(root, 'frontend/src/features/studio/CreativeImport.tsx'), 'utf8')
  assert.equal(fs.existsSync(path.join(root, 'frontend/src/features/diagnostics/DiagnosticsNotice.tsx')), false)
  assert.doesNotMatch(app, /DiagnosticsNotice/)
  assert.doesNotMatch(importer, /FailureHint|一小段视频|自动发送/)
  assert.match(viewSource, /aria-live="polite"/)
  assert.match(viewSource, /FAILURE_HINT_MS/)
  assert.match(viewSource, /FAILURE_HINT_MAX_MS/)
  assert.match(viewSource, /navigate\('\/settings\?section=diagnostics'\)/)
  assert.doesNotMatch(viewSource, /setConsent|aria-modal|ac-dialog-backdrop|autoFocus/)
  assert.doesNotMatch(viewSource, /已发送|成功发送/)
})

test('wording follows origin and an explicit off choice', () => {
  const on = { diagnostics: true, media: true }
  assert.equal(hint.hintKind('file', on), 'excerpt')
  assert.equal(hint.hintKind('link', on), 'errors')
  assert.equal(hint.hintKind('unknown', on), 'errors')
  assert.equal(hint.hintKind('file', { diagnostics: true, media: false }), 'errors')
  assert.equal(hint.hintKind('file', { diagnostics: false, media: true }), 'off')
  assert.equal(hint.hintKind('link', { diagnostics: false, media: false }), 'off')
  assert.equal(hint.hintKind('file', { diagnostics: true, media: true, unreadable: true }), 'off')
  assert.match(hint.HINT_COPY.excerpt, /一小段视频/)
  assert.match(hint.HINT_COPY.errors, /不会发送视频/)
  assert.match(hint.HINT_COPY.off, /不会自动发送/)
  assert.doesNotMatch(hint.HINT_COPY.off, /一小段视频|不会发送视频/)
  assert.equal(hint.taskOrigin({ source_file: '/tmp/a.mp4' }), 'file')
  assert.equal(hint.taskOrigin({ source_url: 'https://example.com/v' }), 'link')
  assert.equal(hint.taskOrigin({ source_url: 'https://example.com/v', source_file: '/tmp/a.mp4' }), 'unknown')
})

test('the first failure is remembered across a restart and does not repeat', () => {
  const memory = new Map()
  const storage = {
    getItem: key => memory.has(key) ? memory.get(key) : null,
    setItem: (key, value) => memory.set(key, value),
  }
  const first = hint.createHintGate(storage)
  assert.equal(first.claim(), true)
  assert.equal(first.claim(), false)
  const restarted = hint.createHintGate(storage)
  assert.equal(restarted.claim(), false)
  assert.equal(memory.get(hint.FAILURE_HINT_KEY), '1')
})

test('the hint dismisses itself and pauses while hovered', () => {
  const pending = []
  const schedule = (fn, ms) => { const id = pending.length; pending.push({ fn, ms, id }); return id }
  const cancel = id => { const item = pending.find(entry => entry.id === id); if (item) item.cancelled = true }
  let done = 0
  const clock = hint.createHintTimer(hint.FAILURE_HINT_MS, () => { done += 1 }, schedule, cancel)
  clock.start(1_000)
  assert.equal(pending[0].ms, 7000)
  clock.pause(3_000)
  assert.equal(clock.paused, true)
  assert.equal(clock.remaining, 5000)
  clock.resume(4_000)
  assert.equal(pending.at(-1).ms, 5000)
  pending.at(-1).fn()
  assert.equal(done, 1)
  clock.resume(9_000)
  assert.equal(done, 1)
})
