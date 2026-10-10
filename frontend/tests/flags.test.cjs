const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const defaults = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/analytics/flags.defaults.json'), 'utf8'))
const WEEK = 7 * 24 * 60 * 60 * 1000

function memory() {
  const data = new Map()
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key), data }
}

function load(options = {}) {
  const file = path.join(__dirname, '../src/analytics/flags.ts')
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true, resolveJsonModule: true,
  } }).outputText
  const calls = []
  let enabled = options.analytics === true
  const remote = { ...(options.remote || {}) }
  const storage = options.storage || memory()
  const module = { exports: {} }
  vm.runInNewContext(js, {
    exports: module.exports, module, console,
    __env: { DEV: options.dev === true, VITE_FLAGS: options.vite || '' },
    require: (id) => {
      if (id === 'react') return { useSyncExternalStore: (_subscribe, get) => get() }
      if (id.endsWith('flags.defaults.json')) return { __esModule: true, default: defaults }
      if (id === './posthog') return {
        isAnalyticsEnabled: () => enabled,
        onAnalyticsPreferenceChange: () => () => {},
        subscribeRemoteFlags: () => () => {},
        readLoadedFlag: (name) => { calls.push(name); return Object.prototype.hasOwnProperty.call(remote, name) ? remote[name] : undefined },
      }
      throw new Error(`Unexpected dependency: ${id}`)
    },
  }, { filename: file })
  module.exports.bindFlagStorage(storage)
  if (options.now) module.exports.bindFlagClock(options.now)
  return { flags: module.exports, calls, storage, remote, setAnalytics: value => { enabled = value } }
}

test('build defaults are the safe off value for every flag', () => {
  const { flags } = load()
  for (const name of flags.FLAG_NAMES) {
    assert.equal(flags.flagEnabled(name), false, name)
    assert.equal(flags.flagValue(name), defaults[name], name)
  }
  assert.equal(JSON.stringify(flags.featureSnapshot()).includes('http'), false)
})

test('analytics off never reads remote flags or a stale cache', () => {
  const storage = memory()
  storage.setItem('autoclip.flags.cache.v1', JSON.stringify({ savedAt: Date.now(), values: { remember_platforms: true, render_top_first: 'top3' } }))
  const { flags, calls } = load({ analytics: false, remote: { remember_platforms: true }, storage })
  assert.equal(flags.flagValue('remember_platforms'), false)
  assert.equal(flags.flagValue('render_top_first'), 'limit10')
  assert.deepEqual(calls, [])
  assert.equal(storage.getItem('autoclip.flags.cache.v1').includes('top3'), true)
})

test('analytics on uses the loaded remote value and writes a cache', () => {
  const now = () => 1_700_000_000_000
  const { flags, calls, storage } = load({ analytics: true, remote: { remember_platforms: true, render_top_first: 'top3', clip_reasons: 'nope' }, now })
  assert.equal(flags.flagEnabled('remember_platforms'), true)
  assert.equal(flags.flagValue('render_top_first'), 'top3')
  assert.equal(flags.flagValue('clip_reasons'), false)
  assert.ok(calls.includes('remember_platforms'))
  const cache = JSON.parse(storage.getItem('autoclip.flags.cache.v1'))
  assert.equal(cache.values.remember_platforms, true)
  assert.equal(cache.values.render_top_first, 'top3')
  assert.equal(cache.values.clip_reasons, undefined)
})

test('a fresh cache is used only while analytics stays on and expires after seven days', () => {
  let time = 1_700_000_000_000
  const storage = memory()
  storage.setItem('autoclip.flags.cache.v1', JSON.stringify({ savedAt: time, values: { notify_on_done: true } }))
  const on = load({ analytics: true, storage, now: () => time })
  assert.equal(on.flags.flagEnabled('notify_on_done'), true)
  time += WEEK + 1
  assert.equal(on.flags.flagEnabled('notify_on_done'), false)
  const off = load({ analytics: false, storage, now: () => time - WEEK })
  assert.equal(off.flags.flagEnabled('notify_on_done'), false)
})

test('local override beats remote values and safe mode, and safe mode forces the rest off', () => {
  const { flags } = load({ analytics: true, remote: { remember_platforms: true, clip_reasons: true, autoclip_safe_mode: false } })
  flags.setFlagOverride('autoclip_safe_mode', true)
  flags.setFlagOverride('clip_reasons', true)
  assert.equal(flags.flagEnabled('autoclip_safe_mode'), true)
  assert.equal(flags.flagEnabled('clip_reasons'), true)
  assert.equal(flags.flagEnabled('remember_platforms'), false)
  flags.setFlagOverride('autoclip_safe_mode', null)
  flags.setFlagOverride('clip_reasons', null)
  assert.equal(flags.flagEnabled('remember_platforms'), true)
})

test('remote safe mode closes every flag that has no local override', () => {
  const { flags, calls } = load({ analytics: true, remote: { autoclip_safe_mode: true, remember_platforms: true, qa_gate_blocking: 'block' } })
  assert.equal(flags.flagEnabled('autoclip_safe_mode'), true)
  assert.equal(flags.flagEnabled('remember_platforms'), false)
  assert.equal(flags.flagValue('qa_gate_blocking'), 'off')
  assert.equal(calls.includes('remember_platforms'), false)
})

test('dev VITE_FLAGS applies when remote has no value and is ignored in production', () => {
  const dev = load({ analytics: false, dev: true, vite: 'notify_on_done=on,render_top_first=top3,not_a_flag=on,clip_reasons=maybe' })
  assert.equal(dev.flags.flagEnabled('notify_on_done'), true)
  assert.equal(dev.flags.flagValue('render_top_first'), 'top3')
  assert.equal(dev.flags.flagEnabled('clip_reasons'), false)
  const prod = load({ analytics: false, dev: false, vite: 'notify_on_done=on' })
  assert.equal(prod.flags.flagEnabled('notify_on_done'), false)
  const remote = load({ analytics: true, dev: true, vite: 'notify_on_done=on', remote: { notify_on_done: false } })
  assert.equal(remote.flags.flagEnabled('notify_on_done'), false)
})

test('an unassigned default does not count as an experiment assignment', () => {
  const silent = load()
  assert.equal(silent.flags.flagOrigin('one_click_paste_start'), 'default')
  assert.equal(silent.flags.flagAssigned('one_click_paste_start'), false)
  const remote = load({ analytics: true, remote: { one_click_paste_start: 'button', remember_platforms: true } })
  assert.equal(remote.flags.flagOrigin('one_click_paste_start'), 'remote')
  assert.equal(remote.flags.flagAssigned('one_click_paste_start'), true)
  assert.equal(remote.flags.flagEnabled('one_click_paste_start'), false)
  assert.equal(remote.flags.flagAssigned('remember_platforms'), true)
  const safe = load({ analytics: true, remote: { autoclip_safe_mode: true, remember_platforms: true } })
  assert.equal(safe.flags.flagOrigin('remember_platforms'), 'safe_mode')
  assert.equal(safe.flags.flagAssigned('remember_platforms'), false)
})
test('quality gate defaults to shadow and block is not the safe value', () => {
  const { flags } = load()
  assert.equal(flags.flagValue('qa_gate_blocking'), 'shadow')
  assert.equal(flags.flagEnabled('qa_gate_blocking'), false)
  flags.setFlagOverride('qa_gate_blocking', 'block')
  assert.equal(flags.flagValue('qa_gate_blocking'), 'block')
  flags.setFlagOverride('autoclip_safe_mode', true)
  assert.equal(flags.flagValue('qa_gate_blocking'), 'off')
  assert.equal(flags.flagOrigin('qa_gate_blocking'), 'safe_mode')
  flags.setFlagOverride('qa_gate_blocking', null)
  assert.equal(flags.flagValue('qa_gate_blocking'), 'off')
})

test('invalid overrides are dropped and the snapshot stays enumerable', () => {
  const { flags, storage } = load()
  flags.setFlagOverride('publish_pack_v2', 'combined')
  flags.setFlagOverride('one_click_paste_start', 'sometimes')
  assert.equal(flags.flagValue('publish_pack_v2'), 'combined')
  assert.equal(flags.flagValue('one_click_paste_start'), 'button')
  const stored = JSON.parse(storage.getItem('autoclip.flags.overrides.v1'))
  assert.deepEqual(Object.keys(stored), ['publish_pack_v2'])
  flags.setFlagOverride('publish_pack_v2', null)
  assert.equal(storage.getItem('autoclip.flags.overrides.v1'), null)
})
