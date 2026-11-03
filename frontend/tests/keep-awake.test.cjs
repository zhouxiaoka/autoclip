const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const ts = require('typescript')
const Module = require('node:module')
const { runInSandbox } = require('./vm-sandbox.cjs')

function loadKeepAwake() {
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/keepAwake.ts'), 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  // Drop dynamic import() used only by the singleton factory so require() works.
  const safe = compiled.replace(/await import\([^)]+\)/g, 'Promise.reject(new Error("no import in tests"))')
  const storage = new Map()
  const storageApi = {
    getItem: k => (storage.has(k) ? storage.get(k) : null),
    setItem: (k, v) => { storage.set(k, String(v)) },
  }
  const tmp = path.join(__dirname, '.keep-awake.tmp.cjs')
  fs.writeFileSync(tmp, safe)
  try {
    // Fresh load each time
    delete require.cache[require.resolve(tmp)]
    const prev = global.localStorage
    global.localStorage = storageApi
    const api = require(tmp)
    global.localStorage = prev
    return { ...api, storage: storageApi, _map: storage }
  } finally {
    try { fs.unlinkSync(tmp) } catch {}
  }
}

test('keep-awake setting defaults on and persists', () => {
  const m = loadKeepAwake()
  assert.equal(m.isKeepAwakeEnabled(m.storage), true)
  m.setKeepAwakeEnabled(false, m.storage)
  assert.equal(m.isKeepAwakeEnabled(m.storage), false)
  m.setKeepAwakeEnabled(true, m.storage)
  assert.equal(m.isKeepAwakeEnabled(m.storage), true)
})

test('projectIsProducing matches screening/production/rendering and processing', () => {
  const m = loadKeepAwake()
  assert.equal(m.projectIsProducing({ status: 'completed' }), false)
  assert.equal(m.projectIsProducing({ status: 'processing' }), true)
  assert.equal(m.projectIsProducing({ status: 'pending' }), true)
  assert.equal(m.projectIsProducing({ status: 'completed', settings: { studio_generation_status: 'screening' } }), true)
  assert.equal(m.projectIsProducing({ status: 'completed', processing_config: { studio_generation_status: 'rendering' } }), true)
  assert.equal(m.projectIsProducing({ status: 'completed', settings: { studio_generation_status: 'completed' } }), false)
})

test('controller holds immediately and releases after delay', async () => {
  const m = loadKeepAwake()
  const calls = []
  const timers = []
  let enabled = true
  const ctrl = m.createKeepAwakeController({
    invoke: async (cmd, args) => { calls.push([cmd, args]) },
    isDesktop: () => true,
    getEnabled: () => enabled,
    releaseDelayMs: 10_000,
    setTimeout: (fn, ms) => {
      const id = { fn, ms }
      timers.push(id)
      return id
    },
    clearTimeout: id => {
      const i = timers.indexOf(id)
      if (i >= 0) timers.splice(i, 1)
    },
  })

  ctrl.syncProjects([{ status: 'processing' }])
  await ctrl.flush()
  assert.equal(ctrl.isHeld(), true)
  assert.deepEqual(calls, [['set_keep_awake', { on: true }]])

  ctrl.syncProjects([{ status: 'processing' }, { status: 'completed' }])
  await ctrl.flush()
  assert.equal(calls.length, 1)

  ctrl.syncProjects([{ status: 'completed' }])
  await ctrl.flush()
  assert.equal(calls.length, 1)
  assert.equal(timers.length, 1)
  assert.equal(timers[0].ms, 10_000)

  timers[0].fn()
  await ctrl.flush()
  assert.deepEqual(calls[1], ['set_keep_awake', { on: false }])
  assert.equal(ctrl.isHeld(), false)
})

test('controller cancels pending release if production resumes', async () => {
  const m = loadKeepAwake()
  const calls = []
  const timers = []
  const ctrl = m.createKeepAwakeController({
    invoke: async (cmd, args) => { calls.push([cmd, args]) },
    isDesktop: () => true,
    getEnabled: () => true,
    releaseDelayMs: 10_000,
    setTimeout: (fn, ms) => {
      const id = { fn, ms }
      timers.push(id)
      return id
    },
    clearTimeout: id => {
      const i = timers.indexOf(id)
      if (i >= 0) timers.splice(i, 1)
    },
  })

  ctrl.setSource('workspace:p1', true)
  await ctrl.flush()
  assert.equal(ctrl.isHeld(), true)

  ctrl.setSource('workspace:p1', false)
  assert.equal(timers.length, 1)

  ctrl.setSource('workspace:p1', true)
  assert.equal(timers.length, 0)
  await ctrl.flush()
  assert.equal(calls.length, 1)
})

test('disabling setting releases immediately', async () => {
  const m = loadKeepAwake()
  const calls = []
  let enabled = true
  const ctrl = m.createKeepAwakeController({
    invoke: async (cmd, args) => { calls.push([cmd, args]) },
    isDesktop: () => true,
    getEnabled: () => enabled,
    storage: m.storage,
  })
  ctrl.syncProjects([{ status: 'processing' }])
  await ctrl.flush()
  enabled = false
  ctrl.onEnabledChange(false)
  await ctrl.flush()
  assert.deepEqual(calls.at(-1), ['set_keep_awake', { on: false }])
  assert.equal(ctrl.isHeld(), false)
  assert.equal(m._map.get(m.KEEP_AWAKE_SETTING_KEY), '0')
})
