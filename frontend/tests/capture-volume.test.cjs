const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

const timers = []
let clock = 0
let timerSerial = 0
const realSetTimeout = global.setTimeout
const realClearTimeout = global.clearTimeout
const realNow = Date.now

function installClock() {
  clock = 0
  timers.length = 0
  timerSerial = 0
  global.setTimeout = (fn, ms) => {
    const id = ++timerSerial
    timers.push({ id, fn, at: clock + (ms || 0) })
    return id
  }
  global.clearTimeout = (id) => {
    const at = timers.findIndex(item => item.id === id)
    if (at >= 0) timers.splice(at, 1)
  }
  Date.now = () => 1_000 + clock
}

function tick(ms) {
  clock += ms
  const due = timers.filter(item => item.at <= clock).sort((a, b) => a.at - b.at || a.id - b.id)
  for (const item of due) {
    const at = timers.indexOf(item)
    if (at < 0) continue
    timers.splice(at, 1)
    item.fn()
  }
}

function restoreClock() {
  global.setTimeout = realSetTimeout
  global.clearTimeout = realClearTimeout
  Date.now = realNow
  timers.length = 0
}

function loadExperience(events) {
  return loadTs(path.join(__dirname, '../src/analytics/experience.ts'), {
    './posthog': { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } },
    './observer': { workflow: { generation: () => 1, active: () => true } },
    __globals: { Date, Math },
  })
}

function loadStudio(events) {
  return loadTs(path.join(__dirname, '../src/analytics/studio.ts'), {
    './posthog': { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } },
    './observer': { workflow: { generation: () => 1, active: () => true, list: () => [], rememberProject() {}, observeStudio() {}, context: () => ({}) } },
    './flags': { flagAssigned: () => false },
    __globals: { Date, Math },
  })
}

function loadPosthog(events, window) {
  const file = path.join(__dirname, '../src/analytics/posthog.ts')
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText
  const module = { exports: {} }
  const storage = { getItem: () => 'false', setItem() {}, removeItem() {} }
  runInSandbox(js, {
    exports: module.exports, module, Date, Math, URL, console,
    localStorage: storage,
    window,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'phc_test', VITE_PUBLIC_POSTHOG_HOST: 'https://us.i.posthog.com' },
    require: (id) => {
      if (id === 'posthog-js') return {
        init(_key, config) { config.loaded?.({ onFeatureFlags() {}, register() {}, setPersonPropertiesForFlags() {} }) },
        capture(name, props) { events.push({ event: name, props }); return {} },
        opt_in_capturing() {}, opt_out_capturing() {}, get_distinct_id: () => '',
        identify() {}, reset() {},
      }
      if (id === './workflow') return loadTs(path.join(__dirname, '../src/analytics/workflow.ts'), { __globals: { Date, Math } })
      if (id === './runtime') return { nativeRuntime: () => ({}), runtimeProperties: () => ({}) }
      if (id === '../utils/apiConfig') return { apiConfigManager: { getBaseUrl: () => '/api/v1', isReady: () => true, addListener: () => () => {} } }
      throw new Error(id)
    },
  }, { filename: file })
  return module.exports
}

test('edit discovery emits one pair per burst and keeps a failure', () => {
  installClock()
  try {
    const events = []
    const experience = loadExperience(events)
    const first = experience.beginDebouncedEditDiscovery({ placement: 'settings_model', provider: 'openai', trigger: 'edit' })
    const second = experience.beginDebouncedEditDiscovery({ placement: 'settings_model', provider: 'deepseek', trigger: 'edit' })
    first('completed', { source: 'live', result_count: 3 })
    second('failed', { source: 'cache' })
    assert.equal(events.length, 0)
    tick(experience.CAPTURE_QUIET_MS - 1)
    assert.equal(events.length, 0)
    tick(1)
    assert.deepEqual(events.map(item => item.event), ['model_discovery_requested', 'model_discovery_finished'])
    assert.equal(events[0].props.trigger, 'edit')
    assert.equal(events[0].props.provider, 'deepseek')
    assert.equal(events[1].props.outcome, 'error')
    assert.equal(events[1].props.provider, 'deepseek')
    const again = experience.beginDebouncedEditDiscovery({ placement: 'home_setup', provider: 'openai', trigger: 'edit' })
    again('completed', { source: 'catalog', result_count: 1 })
    tick(experience.CAPTURE_QUIET_MS)
    assert.equal(events.filter(item => item.props.placement === 'home_setup').length, 2)
    assert.equal(events.filter(item => item.event === 'model_discovery_requested').length, 2)
  } finally { restoreClock() }
})

test('load, manual, and provider_change discovery stay immediate', () => {
  installClock()
  try {
    const events = []
    const experience = loadExperience(events)
    for (const trigger of ['load', 'manual', 'provider_change']) {
      const finish = experience.beginExperience('model_discovery', { placement: 'import_card', provider: 'openai', trigger })
      finish('completed', { source: 'live', result_count: 1 })
    }
    assert.equal(events.length, 6)
    assert.deepEqual(events.filter(item => item.event === 'model_discovery_requested').map(item => item.props.trigger), ['load', 'manual', 'provider_change'])
  } finally { restoreClock() }
})

test('settings load emits once per document and again when it changes', () => {
  const events = []
  const experience = loadExperience(events)
  const first = { saved: true, connections: [{ id: 'c', provider: 'openai' }] }
  assert.equal(experience.claimModelSettingsLoad('settings_model', first), true)
  assert.equal(experience.claimModelSettingsLoad('settings_model', first), false)
  assert.equal(experience.claimModelSettingsLoad('home_setup', first), true)
  assert.equal(experience.claimModelSettingsLoad('settings_model', { ...first, saved: false }), true)
})

test('unchanged loaded settings are not an edit', () => {
  const { shouldReportModelDiscovery, connectionSignature } = loadExperience([])
  const loaded = connectionSignature({ connections: [{ id: 'c', provider: 'openai', base_url: 'https://api.openai.com/v1', api_key: 'sk-secret', image_base_url: '' }] })
  assert.equal(shouldReportModelDiscovery('load', loaded, loaded), true)
  assert.equal(shouldReportModelDiscovery('manual', loaded, loaded), true)
  assert.equal(shouldReportModelDiscovery('provider_change', loaded, loaded), true)
  assert.equal(shouldReportModelDiscovery('edit', loaded, loaded), false)
  const edited = connectionSignature({ connections: [{ id: 'c', provider: 'openai', base_url: 'https://api.openai.com/v1', api_key: 'sk-next', image_base_url: '' }] })
  assert.equal(shouldReportModelDiscovery('edit', edited, loaded), true)
  assert.equal(loaded.includes('sk-secret'), true)
})

test('identical validation collapses inside the quiet window and a new result does not', () => {
  installClock()
  try {
    const events = []
    const experience = loadExperience(events)
    const failed = { provider: 'openai', base_url_host: 'api.openai.com', result: 'failed', upstream_error_type: 'invalid_key', probe_kind: 'quick' }
    experience.trackProviderValidation(failed)
    experience.trackProviderValidation({ ...failed, api_key: 'sk-secret' })
    assert.equal(events.length, 1)
    experience.trackProviderValidation({ ...failed, probe_kind: 'trial', trial_context_ok: true })
    assert.equal(events.length, 2)
    tick(experience.CAPTURE_QUIET_MS)
    experience.trackProviderValidation(failed)
    assert.equal(events.length, 3)
    assert.equal(JSON.stringify(events).includes('sk-secret'), false)
    const save = experience.beginExperience('provider_configuration_save', { placement: 'settings_model', provider: 'openai' })
    save('completed')
    const test = experience.beginExperience('provider_connection_test', { placement: 'settings_model', provider: 'openai' })
    test('failed')
    assert.equal(events.filter(item => item.event === 'provider_configuration_save_finished').length, 1)
    assert.equal(events.filter(item => item.event === 'provider_connection_test_finished').length, 1)
  } finally { restoreClock() }
})

test('asr readiness emits on state change only', () => {
  const events = []
  const studio = loadStudio(events)
  const blocked = { provider: 'whisper_local', code: 'whisper_not_installed', has_subtitle: false, blocked: true }
  studio.trackAsrReadiness(blocked)
  studio.trackAsrReadiness({ ...blocked, model: 'sk-secret' })
  assert.equal(events.length, 1)
  studio.trackAsrReadiness({ ...blocked, has_subtitle: true, blocked: false })
  assert.equal(events.length, 2)
  assert.equal(events[1].props.has_subtitle, true)
  assert.equal(events[1].props.blocked, false)
  assert.equal(JSON.stringify(events).includes('sk-'), false)
})

test('desktop webview does not send $pageview and the browser still does', () => {
  const browserEvents = []
  const browser = loadPosthog(browserEvents, { location: { protocol: 'https:', hostname: 'autoclip.example' } })
  browser.initAnalytics()
  browser.setAnalyticsEnabled(true)
  browser.trackPageview('/settings?section=ai')
  assert.equal(browserEvents.length, 1)
  assert.equal(browserEvents[0].event, '$pageview')
  assert.equal(browserEvents[0].props.route, '/settings')

  const desktopEvents = []
  const desktop = loadPosthog(desktopEvents, { __TAURI_INTERNALS__: {}, location: { protocol: 'http:', hostname: 'tauri.localhost' } })
  desktop.initAnalytics()
  desktop.setAnalyticsEnabled(true)
  desktop.trackPageview('/')
  desktop.trackPageview('/project/abc')
  assert.equal(desktopEvents.length, 0)
  assert.equal(desktop.isDesktopWebview(), true)

  const hostEvents = []
  const host = loadPosthog(hostEvents, { location: { protocol: 'https:', hostname: 'tauri.localhost' } })
  host.initAnalytics()
  host.setAnalyticsEnabled(true)
  host.trackPageview('/')
  assert.equal(hostEvents.length, 0)
})
