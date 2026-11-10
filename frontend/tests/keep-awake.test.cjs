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

function fakeController(m, invoke, extra = {}) {
  const timers = []
  const ctrl = m.createKeepAwakeController({
    invoke,
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
    ...extra,
  })
  return { ctrl, timers }
}

test('pill is not shown from a confirmed lock after the last source stops', async () => {
  const m = loadKeepAwake()
  const { ctrl, timers } = fakeController(m, async () => {})
  ctrl.setSource('workspace:p', true)
  await ctrl.flush()
  assert.equal(ctrl.isHeld(), true)
  assert.equal(ctrl.showsActivityLock(), true)
  ctrl.setSource('workspace:p', false)
  assert.equal(timers.length, 1)
  assert.equal(ctrl.isHeld(), true)
  assert.equal(ctrl.showsActivityLock(), false)
})

test('failed release does not stick held and a later retry converges', async () => {
  const m = loadKeepAwake()
  const calls = []
  let releaseFailures = 1
  const { ctrl, timers } = fakeController(m, async (_cmd, args) => {
    calls.push(args.on)
    if (args.on === false && releaseFailures > 0) {
      releaseFailures -= 1
      throw new Error('release failed')
    }
  })
  ctrl.syncProjects([{ status: 'processing' }])
  await ctrl.flush()
  assert.equal(ctrl.showsActivityLock(), true)

  ctrl.syncProjects([{ status: 'failed', processing_config: { studio_generation_status: 'failed' } }])
  await ctrl.flush()
  assert.equal(timers.length, 1)
  assert.equal(timers[0].ms, 10_000)
  timers[0].fn()
  await ctrl.flush()
  assert.equal(ctrl.lockState(), 'unknown')
  assert.equal(ctrl.isHeld(), false)
  assert.equal(ctrl.showsActivityLock(), false)
  const retry = timers.find(timer => timer.ms === 1_000)
  assert.ok(retry)

  retry.fn()
  await ctrl.flush()
  assert.equal(ctrl.lockState(), 'released')
  assert.equal(ctrl.isHeld(), false)
  assert.equal(ctrl.showsActivityLock(), false)
  assert.deepEqual(calls, [true, false, false])
})

test('release retries stay bounded, then a later sync can try again', async () => {
  const m = loadKeepAwake()
  const calls = []
  let clock = 0
  const { ctrl, timers } = fakeController(m, async (_cmd, args) => {
    calls.push(args.on)
    if (args.on === false) throw new Error('release failed')
  }, { retryBackoffMs: [1_000, 2_000], now: () => clock })

  ctrl.setSource('projects', true)
  await ctrl.flush()
  ctrl.setSource('projects', false)
  timers[0].fn()
  await ctrl.flush()
  assert.equal(timers.at(-1).ms, 1_000)
  timers.at(-1).fn()
  await ctrl.flush()
  assert.equal(timers.at(-1).ms, 2_000)
  timers.at(-1).fn()
  await ctrl.flush()
  const failedReleases = calls.filter(on => on === false).length
  assert.equal(failedReleases, 3)
  assert.equal(ctrl.lockState(), 'unknown')
  assert.equal(ctrl.showsActivityLock(), false)

  ctrl.syncProjects([{ status: 'failed', processing_config: { studio_generation_status: 'failed' } }])
  await ctrl.flush()
  assert.equal(calls.filter(on => on === false).length, 3)

  clock = 1_999
  ctrl.syncProjects([{ status: 'failed', processing_config: { studio_generation_status: 'failed' } }])
  await ctrl.flush()
  assert.equal(calls.filter(on => on === false).length, 3)

  clock = 2_000
  ctrl.syncProjects([{ status: 'failed', processing_config: { studio_generation_status: 'failed' } }])
  await ctrl.flush()
  assert.equal(calls.filter(on => on === false).length, 4)
  assert.equal(ctrl.lockState(), 'unknown')
  assert.equal(ctrl.showsActivityLock(), false)
})

test('last mounted source is the only one that starts release', async () => {
  const m = loadKeepAwake()
  const calls = []
  const { ctrl, timers } = fakeController(m, async (_cmd, args) => { calls.push(args.on) })
  ctrl.setSource('workspace:a', true)
  ctrl.setSource('statusbar:b', true)
  await ctrl.flush()
  assert.deepEqual(calls, [true])

  ctrl.setSource('workspace:a', false)
  await ctrl.flush()
  assert.deepEqual(calls, [true])
  assert.equal(timers.length, 0)
  assert.deepEqual([...ctrl.getSources().keys()], ['statusbar:b'])
  assert.equal(ctrl.showsActivityLock(), true)

  ctrl.setSource('statusbar:b', false)
  assert.equal(timers.length, 1)
  assert.equal(timers[0].ms, 10_000)
  assert.deepEqual(calls, [true])
  timers[0].fn()
  await ctrl.flush()
  assert.deepEqual(calls, [true, false])
  assert.equal(ctrl.lockState(), 'released')
})

test('a terminal project list does not clear a mounted workspace source', async () => {
  const m = loadKeepAwake()
  const calls = []
  const { ctrl, timers } = fakeController(m, async (_cmd, args) => { calls.push(args.on) })
  ctrl.syncProjects([{ status: 'processing' }])
  ctrl.setSource('workspace:c8e29eb0', true)
  await ctrl.flush()
  ctrl.syncProjects([{ status: 'failed', processing_config: { studio_generation_status: 'failed' } }])
  await ctrl.flush()
  assert.deepEqual([...ctrl.getSources().keys()], ['workspace:c8e29eb0'])
  assert.equal(timers.length, 0)
  assert.equal(ctrl.isHeld(), true)
  assert.equal(ctrl.showsActivityLock(), true)
  assert.deepEqual(calls, [true])
})

test('a new source cancels a pending release retry and acquires again', async () => {
  const m = loadKeepAwake()
  const calls = []
  let releaseFailures = 1
  const { ctrl, timers } = fakeController(m, async (_cmd, args) => {
    calls.push(args.on)
    if (args.on === false && releaseFailures > 0) {
      releaseFailures -= 1
      throw new Error('release failed')
    }
  })
  ctrl.setSource('workspace:p', true)
  await ctrl.flush()
  ctrl.setSource('workspace:p', false)
  timers.find(timer => timer.ms === 10_000).fn()
  await ctrl.flush()
  assert.equal(ctrl.lockState(), 'unknown')
  const retry = timers.find(timer => timer.ms === 1_000)
  assert.ok(retry)
  ctrl.setSource('workspace:p', true)
  await ctrl.flush()
  assert.equal(timers.includes(retry), false)
  assert.equal(calls.at(-1), true)
  assert.equal(ctrl.isHeld(), true)
  assert.equal(ctrl.showsActivityLock(), true)
  if (timers.includes(retry)) retry.fn()
  await ctrl.flush()
  assert.equal(ctrl.isHeld(), true)
  assert.equal(calls.filter(on => on === false).length, 1)
})

test('a late acquire cannot overwrite a release that was requested while it was in flight', async () => {
  const m = loadKeepAwake()
  const calls = []
  let finishAcquire
  const { ctrl } = fakeController(m, async (_cmd, args) => {
    calls.push(args.on)
    if (calls.length === 1) await new Promise(resolve => { finishAcquire = resolve })
  })
  ctrl.setSource('workspace:p', true)
  for (let i = 0; i < 8 && typeof finishAcquire !== 'function'; i++) await Promise.resolve()
  assert.equal(typeof finishAcquire, 'function')
  ctrl.setSource('workspace:p', false)
  finishAcquire()
  await ctrl.flush()
  assert.deepEqual(calls, [true, false])
  assert.equal(ctrl.lockState(), 'released')
  assert.equal(ctrl.isHeld(), false)
  assert.equal(ctrl.showsActivityLock(), false)
})
