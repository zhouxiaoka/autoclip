const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const ts = require('typescript')

function loadKeepAwake() {
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/keepAwake.ts'), 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const safe = compiled.replace(/await import\([^)]+\)/g, 'Promise.reject(new Error("no import in tests"))')
  const storage = new Map()
  const storageApi = {
    getItem: k => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => { storage.set(k, String(v)) },
  }
  const tmp = path.join(__dirname, '.keep-awake.tmp.cjs')
  fs.writeFileSync(tmp, safe)
  try {
    delete require.cache[require.resolve(tmp)]
    const prev = global.localStorage
    global.localStorage = storageApi
    const api = require(tmp)
    global.localStorage = prev
    return api
  } finally {
    try { fs.unlinkSync(tmp) } catch {}
  }
}

function quitGuardSource() {
  return fs.readFileSync(path.join(__dirname, '../src/features/studio/quitGuard.tsx'), 'utf8')
}

test('quitGuard runningCount uses shared projectIsProducing (single source of truth)', () => {
  const src = quitGuardSource()
  assert.match(src, /from ['"]\.\/keepAwake['"]/)
  assert.match(src, /projectIsProducing/)
  assert.match(src, /export function runningCount/)
  assert.doesNotMatch(src, /project\.status\s*===\s*['"]processing['"]/)
})

test('runningCount semantics match projectIsProducing filter', () => {
  const { projectIsProducing } = loadKeepAwake()
  const runningCount = projects => projects.filter(projectIsProducing).length
  assert.equal(runningCount([]), 0)
  assert.equal(runningCount([{ status: 'completed' }]), 0)
  assert.equal(runningCount([{ status: 'error' }]), 0)
  assert.equal(runningCount([{ status: 'processing' }]), 1)
  assert.equal(runningCount([{ status: 'pending' }]), 1)
  assert.equal(runningCount([{ status: 'completed', settings: { studio_generation_status: 'screening' } }]), 1)
  assert.equal(runningCount([{ status: 'completed', processing_config: { studio_generation_status: 'production' } }]), 1)
  assert.equal(runningCount([{ status: 'completed', settings: { studio_generation_status: 'rendering' } }]), 1)
  assert.equal(runningCount([{ status: 'completed', settings: { studio_generation_status: 'idle' } }]), 0)
  assert.equal(runningCount([
    { status: 'completed' },
    { status: 'pending' },
    { status: 'processing' },
    { status: 'error', settings: { studio_generation_status: 'screening' } },
  ]), 3)
})
