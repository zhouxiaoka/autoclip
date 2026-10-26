const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const { loadTs } = require('./load-ts.cjs')

// Compile the actual source in memory. No new runner dependency or network calls.
// Pending timers in `queue`, in order; clearTimeout really removes one (the PUT abort timer is cleared on reply).
function fakeTimers(queue) {
  const ids = new Map()
  let next = 0
  return {
    setTimeout: fn => { const id = ++next; ids.set(id, fn); queue.push(fn); return id },
    clearTimeout: id => { const fn = ids.get(id); ids.delete(id); const at = queue.indexOf(fn); if (at >= 0) queue.splice(at, 1) },
  }
}

function load(name, mocks = {}, globals = {}) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  runInSandbox(js, { exports: module.exports, module, Blob, Date, Math, console, URL,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key' },
    require: (id) => {
      if (id in mocks) return mocks[id]
      if (id === './failureCodes') return loadTs(path.join(__dirname, '../src/analytics/failureCodes.ts'))
      if (id === './successRateContract' || id === '../../analytics/successRateContract') return load('successRateContract')
      if (id === './connectionTestCode' || id === '../../analytics/connectionTestCode') return load('connectionTestCode')
      if (id === '@event-catalog') {
        const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../../backend/core/event_catalog.json'), 'utf8'))
        return { default: data, __esModule: true }
      }
      if (id === './errorText') return require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/features/studio/errorText.ts'))
      if (id === './runtime') return load('runtime', {}, globals)
      if (id === '../utils/apiConfig') {
        return { apiConfigManager: { getBaseUrl: () => '/api/v1', addListener: () => () => {} } }
      }
      throw new Error(`Unexpected dependency: ${id}`)
    }, ...globals }, { filename: file })
  return module.exports
}
const core = require('./helpers/real-backend.cjs').withRealBackend(load('workflow'))

test('native Mac architecture overrides the Intel webview UA before launch resolves', () => {
  const lifecycle = load('lifecycle', {
    '@tauri-apps/api/app': { getVersion: () => new Promise(() => {}) },
    './posthog': {},
  }, {
    window: { __AUTOCLIP_RUNTIME__: { os: 'macos', arch: 'aarch64' } },
    navigator: { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X)', language: 'en' },
    document: { documentElement: { lang: 'en' } },
  })
  assert.equal(lifecycle.getRuntimeInfo().arch, 'aarch64')
})

test('first capture has native os/arch without waiting for trackLaunch', () => {
  const registered = {}; const events = []
  const sdk = {
    init(_key, config) { config.loaded(sdk) },
    register(props) { Object.assign(registered, props) },
    capture(name, props) { events.push({ ...registered, ...props }); return {} },
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, {
    localStorage: memory(), window: { __TAURI_INTERNALS__: {}, __AUTOCLIP_RUNTIME__: { os: 'macos', arch: 'arm64' } },
    navigator: { userAgent: 'Macintosh; Intel Mac OS X', language: 'en' },
  })
  ph.initAnalytics()
  assert.equal(registered.os, 'macos')
  assert.equal(registered.arch, 'aarch64')
  ph.captureBusinessEvent('setup_presented')
  assert.equal(events[0].os, 'macos')
  assert.equal(events[0].arch, 'aarch64')
})

test('identity waits for the desktop port, retries failure and cancels retries on opt-out', async () => {
  const id = '018f6b2a-7c3d-7b2a-8c11-111111111111'
  let ready = false, listener, timer, config
  const requests = []; const cancelled = []
  const sdk = {
    init(_key, options) { config = options; options.loaded(sdk) },
    register() {}, get_distinct_id: () => id,
    opt_in_capturing() {}, opt_out_capturing() {},
  }
  const ph = load('posthog', {
    'posthog-js': sdk, './workflow': core,
    '../utils/apiConfig': { apiConfigManager: {
      getBaseUrl: () => ready ? 'http://127.0.0.1:8123/api/v1' : '/api/v1',
      isReady: () => ready, addListener: fn => { listener = fn },
    } },
  }, {
    localStorage: memory(),
    window: { __TAURI_INTERNALS__: {}, __AUTOCLIP_RUNTIME__: { os: 'windows', arch: 'amd64', distinct_id: id } },
    setTimeout: fn => { timer = fn; return 1 }, clearTimeout: id => { cancelled.push(id); timer = undefined },
    fetch: (url, options) => { requests.push({ url, options }); return Promise.resolve({ ok: false }) },
  })
  ph.initAnalytics()
  assert.equal(config.bootstrap.distinctID, id)
  assert.equal(config.bootstrap.isIdentifiedID, false)
  assert.equal(requests.length, 0)
  ready = true; listener()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(requests.length, 1)
  assert.equal(requests[0].url, 'http://127.0.0.1:8123/api/v1/settings/analytics-identity')
  assert.deepEqual(JSON.parse(requests[0].options.body), { distinct_id: id })
  assert.equal(typeof timer, 'function')
  timer()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(requests.length, 2)
  ph.setAnalyticsEnabled(false)
  assert.equal(timer, undefined)
  assert.ok(cancelled.length > 0)
  listener()
  const identityPuts = requests.filter(r => r.url.endsWith('/settings/analytics-identity'))
  assert.equal(identityPuts.length, 2)
})

test('X2: opting out tells the backend so Sentry drops user.id; startup syncs the saved preference', async () => {
  const storage = memory()
  const puts = []
  const sdk = { init() {}, capture() { return {} }, get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, {
    localStorage: storage, window: {},
    fetch: (url, opts) => { puts.push({ url, body: JSON.parse(opts.body) }); return Promise.resolve({ ok: true }) },
  })
  const consent = () => puts.filter(p => p.url === '/api/v1/settings/analytics-consent').map(p => p.body.enabled)
  ph.initAnalytics()
  ph.setAnalyticsEnabled(true)
  await new Promise(resolve => setImmediate(resolve))
  // P2: the backend state is unknown at launch, so the saved "on" is synced once.
  assert.deepEqual(consent(), [true])
  ph.setAnalyticsEnabled(false)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(consent(), [true, false])
  ph.setAnalyticsEnabled(true)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(consent(), [true, false, true])
})

test('R10 P1: off→on written but response lost, then off again still reaches the backend', async () => {
  const puts = []
  let lose = false
  const timers = []
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: memory(), window: {},
    setTimeout: (fn) => { timers.push(fn); return timers.length },
    clearTimeout: () => {},
    fetch: (url, opts) => {
      if (!String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      puts.push(JSON.parse(opts.body).enabled)
      // Backend applied the write, but the response never arrives.
      return lose ? Promise.reject(new Error('response lost')) : Promise.resolve({ ok: true })
    },
  })
  ph.initAnalytics()
  ph.setAnalyticsEnabled(false)
  await new Promise(resolve => setImmediate(resolve))
  const base = puts.length
  assert.equal(puts[base - 1], false)
  lose = true
  ph.setAnalyticsEnabled(true)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts.slice(base), [true])
  lose = false
  ph.setAnalyticsEnabled(false)
  await new Promise(resolve => setImmediate(resolve))
  // The opt-out must be sent even though the last confirmed state was also "off".
  assert.deepEqual(puts.slice(base), [true, false])
  // A pending retry from the lost PUT must not resend "on" over the newer opt-out.
  for (const fn of timers.splice(0)) fn()
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(!puts.slice(base + 2).includes(true))
})

test('R10 P2: re-enable write failed, restart syncs the persisted "on" to the backend', async () => {
  const storage = memory()
  storage.setItem('autoclip.analytics.optOut', 'false')
  const puts = []
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: storage, window: {},
    fetch: (url, opts) => {
      if (String(url).includes('/settings/analytics-consent')) puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok: true })
    },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts, [true])
})


test('X2r: consent is marked sent only after success and failed PUTs retry', async () => {
  const storage = memory()
  const puts = []
  let respondOk = false
  let timer
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: storage, window: {},
    setTimeout: (fn) => { timer = fn; return 1 },
    clearTimeout: () => { timer = undefined },
    fetch: (url, opts) => {
      const body = JSON.parse(opts.body)
      if (String(url).includes('/settings/analytics-consent')) puts.push(body.enabled)
      return Promise.resolve({ ok: respondOk || !String(url).includes('/settings/analytics-consent') })
    },
  })
  const consent = () => puts.slice()
  respondOk = true
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts.splice(0), [true]) // P2 startup sync
  respondOk = false
  ph.setAnalyticsEnabled(false)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(consent(), [false])
  // Failure must not stick: a retry should fire with the same opt-out.
  assert.equal(typeof timer, 'function')
  respondOk = true
  timer()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(consent(), [false, false])
  ph.setAnalyticsEnabled(true)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(consent(), [false, false, true])
})

test('X2r: rapid toggle serializes so the backend ends on the latest UI value', async () => {
  const storage = memory()
  const puts = []
  const pending = []
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: storage, window: {},
    fetch: (url, opts) => {
      const body = JSON.parse(opts.body)
      if (!String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      return new Promise(resolve => {
        puts.push(body.enabled)
        pending.push(resolve)
      })
    },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts.splice(0), [true]) // P2 startup sync
  pending.splice(0)[0]({ ok: true })
  await new Promise(resolve => setImmediate(resolve))
  ph.setAnalyticsEnabled(false) // in-flight: false
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts, [false])
  ph.setAnalyticsEnabled(true)
  ph.setAnalyticsEnabled(false) // UI settles on false while first PUT still open
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(puts.length, 1) // second intent waits for the in-flight PUT
  pending[0]({ ok: true })
  await new Promise(resolve => setImmediate(resolve))
  await new Promise(resolve => setImmediate(resolve))
  // publishedConsent already false and UI is false → no need to send true mid-flight
  assert.equal(puts.filter(v => v === true).length, 0)
  assert.equal(puts[puts.length - 1], false)
  for (let i = 1; i < pending.length; i++) pending[i]({ ok: true })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(puts[puts.length - 1], false)
})

test('X2: an opted-out launch reports the opt-out even without a PostHog key', async () => {
  const storage = memory()
  storage.setItem('autoclip.analytics.optOut', 'true')
  const puts = []
  const ph = load('posthog', { 'posthog-js': { init() { throw Error('must not init') } }, './workflow': core }, {
    localStorage: storage, window: {},
    fetch: (url, opts) => { puts.push({ url, body: JSON.parse(opts.body) }); return Promise.resolve({ ok: true }) },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(puts, [{ url: '/api/v1/settings/analytics-consent', body: { enabled: false } }])
})

test('architecture aliases and untrusted native facts stay within the telemetry enum', () => {
  const runtime = load('runtime')
  for (const arch of ['arm64', 'aarch64', 'ARM64']) assert.equal(runtime.normalizeArch(arch), 'aarch64')
  for (const arch of ['amd64', 'x86_64', 'x64', 'AMD64']) assert.equal(runtime.normalizeArch(arch), 'x86_64')
  const untrusted = load('runtime', {}, {
    window: { __AUTOCLIP_RUNTIME__: { os: 'private title', arch: 'sk-secret' } },
    navigator: { userAgent: 'Macintosh Intel Mac OS X' },
  })
  assert.equal(JSON.stringify(untrusted.runtimeProperties()), '{"os":"macos","arch":"unknown"}')
})

test('reset identity waits for the previous PUT and cannot be overwritten by it', async () => {
  let id = '018f6b2a-7c3d-7b2a-8c11-111111111111'
  const next = '018f6b2a-7c3d-7b2a-8c11-222222222222'
  let finish
  const ids = []
  const ph = load('posthog', { 'posthog-js': {
    init() {}, get_distinct_id: () => id, reset() { id = next },
  }, './workflow': core }, {
    localStorage: memory(), window: {},
    fetch: (url, options) => {
      if (String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      ids.push(JSON.parse(options.body).distinct_id); return new Promise(resolve => { finish = resolve })
    },
  })
  ph.initAnalytics()
  ph.resetUser()
  assert.deepEqual(ids, ['018f6b2a-7c3d-7b2a-8c11-111111111111'])
  finish({ ok: true })
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(ids, ['018f6b2a-7c3d-7b2a-8c11-111111111111', next])
  finish({ ok: true })
  await new Promise(resolve => setImmediate(resolve))
})
function memory() {
  const data = new Map()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }
}
const NOW = Date.parse('2026-09-21T01:00:00Z')
function setup(storage = memory(), clock = () => NOW) {
  const events = []
  let enabled = true
  let accepted = true
  const capture = (event, props) => { if (!accepted) return false; events.push({ event, props }); return true }
  const tracker = new core.WorkflowTracker(storage, () => enabled, capture, clock)
  return { tracker, events, storage, capture, enable: v => enabled = v, accept: v => accepted = v }
}
const task = overrides => ({ id: 'task-1', task_type: 'video_processing', status: 'completed',
  created_at: '2026-09-21T01:00:00', started_at: '2026-09-21T01:00:01Z',
  completed_at: '2026-09-21T01:00:06Z', ...overrides })

test('quick-output properties accept only bounded platform and branding fields', () => {
  const props = core.safeStudioProperties({
    strategy_id: 'tiktok', material_origin: 'user', generation_reason: 'platform_append',
    platform_count: 2, variant_count: 3, completed_variant_count: 2, brand_outro_enabled: true,
    project_id: 'private-project', filename: 'private.mp4', reason: 'raw user text', url: 'https://private.example',
  })
  assert.equal(props.studio_schema_version, 2)
  assert.equal(props.strategy_id, 'tiktok')
  assert.equal(props.material_origin, 'user')
  assert.equal(props.generation_reason, 'platform_append')
  assert.equal(props.platform_count, 2)
  assert.equal(props.variant_count, 3)
  assert.equal(props.completed_variant_count, 2)
  assert.equal(props.brand_outro_enabled, true)
  assert.equal(JSON.stringify(props).includes('private'), false)
  assert.equal(core.safeStudioProperties({ strategy_id: 'untrusted', generation_reason: 'raw text', platform_count: -1 }).strategy_id, undefined)
})


test('duplicate polling and restart preserve deduplication, actual duration and stable IDs', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  const w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task()]); s.tracker.observeTasks(w, [task()])
  assert.equal(s.events.length, 3)
  assert.equal(s.events[2].props.duration_ms, 5000)
  const recovered = new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW)
  recovered.observeTasks(recovered.list()[0], [task()])
  assert.equal(s.events.length, 3)
  assert.equal(new Set(s.events.map(e => e.props.$insert_id)).size, 3)
})
test('historical/non-processing tasks excluded; retries with new task IDs counted', () => {
  const s = setup(); s.tracker.watch('project', 'p'); let w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ created_at: '2026-09-20T01:00:00Z' }), task({ task_type: 'cleanup' })])
  assert.equal(s.events.length, 0)
  s.tracker.observeTasks(w, [task({ status: 'failed' })])
  s.tracker.watch('project', 'p'); w = s.tracker.list()[0]
  s.tracker.observeTasks(w, [task({ id: 'retry-2' })])
  assert.equal(s.events.filter(e => e.event === 'processing_finished').length, 2)
})
test('missing worker timestamps do not invent start or duration; cancellation is distinct', () => {
  const s = setup(); s.tracker.watch('project', 'p')
  s.tracker.observeTasks(s.tracker.list()[0], [task({ status: 'cancelled', started_at: null, completed_at: null })])
  assert.equal(s.events.length, 2)
  assert.equal(s.events[1].props.outcome, 'cancelled')
  assert.equal(core.canonOutcome('cancelled'), 'cancelled')
  assert.equal(core.canonOutcome('failed'), 'error')
  assert.equal(s.events[1].props.duration_ms, undefined)
  assert.equal(s.events[1].props.occurred_at, undefined)
})
test('opt-out clears pending watches, invalidates in-flight generation and never replays', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const old = s.tracker.list()[0]
  const generation = s.tracker.generation()
  s.enable(false); assert.equal(s.tracker.list().length, 0)
  s.enable(true); assert.equal(s.tracker.active(generation), false)
  s.tracker.observeTasks(old, [task()]); assert.equal(s.events.length, 0)
  assert.equal(new core.WorkflowTracker(s.storage, () => true, s.capture, () => NOW).list().length, 0)
})
test('failed enqueue is retried; invalid storage and blocked localStorage do not throw', () => {
  const s = setup(); s.tracker.watch('project', 'p'); const w = s.tracker.list()[0]
  s.accept(false); s.tracker.observeTasks(w, [task()]); assert.equal(w.seen.length, 0)
  s.accept(true); s.tracker.observeTasks(w, [task()]); assert.equal(s.events.length, 3)
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') }, removeItem() { throw Error('blocked') } }
  const b = setup(blocked); b.tracker.watch('project', 'p'); b.tracker.clear()
  const broken = memory(); broken.setItem(core.WORKFLOW_KEY, '{bad'); assert.equal(setup(broken).tracker.list().length, 0)
})
test('watch retention and capacity bounded', () => {
  const s = setup()
  s.tracker.watch('project', 'old', undefined, NOW - 8 * 86400000)
  for (let i = 0; i < 60; i++) s.tracker.watch('project', `p${i}`)
  assert.equal(s.tracker.list().length, 50)
  assert.equal(s.tracker.list().some(w => w.id === 'old'), false)
})
test('errors and routes contain no original secrets, paths or search parameters', () => {
  assert.equal(core.routeName('/project/private-id?token=secret'), '/project/:id')
  assert.equal(core.routeName('/other/secret'), '/other')
  assert.equal(core.errorCode({response:{status:'private'}}), 'unknown')
  assert.equal(core.errorCode({ message: 'sk-secret /Users/person.mp4', response: { status: 401 } }), 'http_401')
  assert.equal(core.errorCode({ message: 'secret' }), 'unknown')
})
test('persisted opt-out skips SDK initialization and can be enabled later without double init', () => {
  const storage = memory(); storage.setItem('autoclip.analytics.optOut', 'true')
  const calls = []; let config
  const sdk = {
    init(_key, cfg) { calls.push('init'); config = cfg },
    capture() { calls.push('capture'); return {} },
    opt_out_capturing() { calls.push('out') }, opt_in_capturing() { calls.push('in') },
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: storage, window: {} })
  ph.initAnalytics(); ph.initAnalytics(); ph.setAnalyticsEnabled(false)
  assert.equal(ph.captureBusinessEvent('disabled'), false)
  assert.deepEqual(calls, [])
  ph.setAnalyticsEnabled(true)
  assert.equal(config.advanced_disable_flags, false)
  assert.equal(ph.captureBusinessEvent('enabled'), true)
  ph.setAnalyticsEnabled(false)
  assert.equal(ph.captureBusinessEvent('disabled-again'), false)
  ph.setAnalyticsEnabled(true); ph.initAnalytics()
  assert.equal(calls.filter(call => call === 'init').length, 1)
  assert.equal(calls.filter(call => call === 'capture').length, 1)
  assert.equal(storage.getItem('autoclip.analytics.optOut'), 'false')
})
test('the anonymous distinct id is stored once for backend events', async () => {
  const storage = memory()
  const puts = []
  const id = '018f6b2a-7c3d-7b2a-8c11-111111111111'
  const sdk = {
    init(_key, cfg) { cfg.loaded?.({ onFeatureFlags() {} }) },
    capture() { return {} },
    get_distinct_id: () => id,
    opt_in_capturing() {},
    opt_out_capturing() {},
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, {
    localStorage: storage,
    window: {},
    fetch: (url, opts) => {
      puts.push({ url, body: opts.body })
      return Promise.resolve({ ok: true })
    },
  })
  const identity = () => puts.filter(p => p.url === '/api/v1/settings/analytics-identity')
  ph.initAnalytics()
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(identity().length, 1)
  assert.equal(JSON.parse(identity()[0].body).distinct_id, id)
  ph.setAnalyticsEnabled(true)
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(identity().length, 1)
})
test('turning analytics off pauses flag reloads and never asks for flags while opted out', () => {
  const storage = memory()
  const calls = []
  const sdk = {
    init(_key, cfg) { calls.push(['init', cfg.advanced_disable_flags]) },
    capture() { return {} },
    opt_out_capturing() { calls.push(['out']) },
    opt_in_capturing() { calls.push(['in']) },
    set_config(cfg) { calls.push(['config', cfg.advanced_disable_flags]) },
    reloadFeatureFlags() { calls.push(['reload']) },
    featureFlags: { setReloadingPaused(paused) { calls.push(['pause', paused]) }, getFlagVariants() { calls.push(['variants']); return { remember_platforms: true } } },
    onFeatureFlags() { calls.push(['listen']) },
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: storage, window: {} })
  assert.equal(ph.readLoadedFlag('remember_platforms'), undefined)
  ph.initAnalytics()
  // W157-N3: values persisted by an earlier session are ignored until this session's flags arrive.
  assert.equal(ph.readLoadedFlag('remember_platforms'), undefined)
  ph.markRemoteFlagsResponse(true)
  assert.equal(ph.readLoadedFlag('remember_platforms'), undefined)
  ph.markRemoteFlagsResponse()
  assert.equal(ph.readLoadedFlag('remember_platforms'), true)
  ph.setAnalyticsEnabled(false)
  assert.equal(ph.readLoadedFlag('remember_platforms'), undefined)
  assert.equal(calls.some(call => call[0] === 'reload'), false)
  assert.deepEqual(calls.filter(call => call[0] === 'config'), [['config', true]])
  assert.deepEqual(calls.filter(call => call[0] === 'pause'), [['pause', true]])
  ph.setAnalyticsEnabled(true)
  assert.equal(calls.filter(call => call[0] === 'reload').length, 1)
  assert.equal(ph.readLoadedFlag('remember_platforms'), true)
})
test('W157-N3: flags restored from posthog persistence are not read before the onFeatureFlags response', () => {
  const storage = memory()
  let listener = null
  const sdk = {
    init(_key, cfg) { cfg.loaded?.(sdk) },
    capture() { return {} }, opt_out_capturing() {}, opt_in_capturing() {}, set_config() {}, reloadFeatureFlags() {},
    register_for_session() {}, setPersonPropertiesForFlags() {},
    featureFlags: { setReloadingPaused() {}, getFlagVariants() { return { pkg_templates_v1: false } } },
    onFeatureFlags(cb) { listener = cb },
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: storage, window: {} })
  ph.initAnalytics()
  assert.equal(ph.readLoadedFlag('pkg_templates_v1'), undefined)
  assert.equal(typeof listener, 'function')
  listener({}, {}, { errorsLoading: false })
  assert.equal(ph.readLoadedFlag('pkg_templates_v1'), false)
})
test('opt-out override prevents SDK initialization even when localStorage is unavailable', () => {
  let initialized = 0
  const sdk = { init() { initialized += 1 } }
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: blocked, window: {} })
  ph.setAnalyticsEnabled(false); ph.initAnalytics()
  assert.equal(initialized, 0)
  assert.equal(ph.captureBusinessEvent('disabled'), false)
})
test('SDK exceptions and unavailable storage cannot break business or override opt-out', () => {
  const captured = []; let config
  const sdk = { init(_key, cfg) { config = cfg }, capture(name, props) { captured.push({ name, props }); return {} },
    opt_out_capturing() {}, opt_in_capturing() {} }
  const blocked = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, { localStorage: blocked, window: {} })
  ph.initAnalytics(); ph.trackPageview('/project/private?key=secret')
  // unreadable preference => nothing initialised or captured until the user opts in.
  assert.equal(config, undefined)
  assert.equal(captured.length, 0)
  ph.setAnalyticsEnabled(true); ph.trackPageview('/project/private?key=secret')
  assert.equal(captured[0].props.route, '/project/:id')
  assert.equal(config.autocapture, false)
  assert.equal(config.disable_session_recording, true)
  ph.setAnalyticsEnabled(false); assert.equal(ph.captureBusinessEvent('test'), false)
  assert.equal(captured.length, 1)
  ph.setAnalyticsEnabled(true); sdk.capture = () => { throw Error('sdk') }
  assert.equal(ph.captureBusinessEvent('test'), false)
})
test('downloads count nonempty bytes, preserve request failure, and stop after consent changes', async () => {
  const s = setup()
  const operations = load('operations', { './posthog': { captureBusinessEvent: s.capture }, './observer': { workflow: s.tracker }, './workflow': core })
  const props = { artifact_type: 'publish_clip' }
  const blob = new Blob(['video'])
  assert.equal(await operations.observeDownload(props, async () => blob), blob)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  await assert.rejects(operations.observeDownload(props, async () => new Blob([])), /Empty/)
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
  const failure = { response: { status: 403 }, message: 'token=secret' }
  await assert.rejects(operations.observeDownload(props, async () => { throw failure }), e => e === failure)
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  let finish; const pending = operations.observeDownload(props, () => new Promise(r => { finish = r }))
  s.tracker.clear(); finish(blob); await pending
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 1)
})

test('actual API entrypoints enroll imports/exports and count every media download path', async () => {
  const s = setup(memory(), () => Date.now())
  const ph = { captureBusinessEvent: s.capture }
  const operations = load('operations', { './posthog': ph, './observer': { workflow: s.tracker }, './workflow': core })
  const blob = new Blob(['video'])
  const transport = {
    defaults: {}, interceptors: { request: { use() {} }, response: { use() {} } },
    async post(url) {
      if (url === '/projects/upload') return { id: 'uploaded' }
      if (url === '/bilibili/download') return { id: 'bilibilitask' }
      if (url === '/youtube/download') return { id: 'youtubetask' }
      if (url.includes('/clips/')) return { ok: true, job_id: 'exportjob' }
      if (url === '/settings/test-api') return { success: false, error: 'secret' }
      return {}
    },
    async get() { return blob },
  }
  const api = load('../services/api', {
    '../i18n': { t: key => key },
    axios: { create: () => transport, get: async () => ({ data: blob, headers: {} }) },
    '../utils/errorHandler': { errorHandler: { handleError() {} } },
    '../utils/apiConfig': { apiConfigManager: { getBaseUrl: () => '/api/v1', addListener() {} } },
    '../analytics/workflow': core, '../analytics/operations': operations, '../analytics/observer': { workflow: s.tracker },
    '../analytics/posthog': ph,
    '../analytics/events': { trackVideoImported() {}, trackClipsExported() {}, trackProcessingFailed() {} },
  }, { FormData, window: { URL: { createObjectURL: () => 'blob:test', revokeObjectURL() {} } },
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } } })
  await api.projectApi.uploadFiles({ video_file: blob, project_name: 'private-name' })
  await api.bilibiliApi.createDownloadTask({ url: 'https://private.invalid/secret' })
  await api.bilibiliApi.createYouTubeDownloadTask({ url: 'https://private.invalid/secret' })
  await api.projectApi.startClipExport('p', 'clip', { preset: 'portrait', subtitles: true })
  await api.projectApi.downloadClip('p', 'clip')
  await api.projectApi.downloadCollection('p', 'collection')
  await api.projectApi.downloadVideo('p', 'clip')
  await api.projectApi.downloadVideo('p', undefined, 'collection')
  await api.projectApi.downloadExport('p', 'exportjob')
  await api.settingsApi.testApiKey('dashscope', 'sk-secret')
  assert.equal(s.events.filter(e => e.event === 'media_download_received').length, 5)
  assert.equal(s.events.find(e => e.event === 'provider_test_finished').props.outcome, 'error')
  assert.equal(JSON.stringify(s.events).includes('secret'), false)
  assert.equal(s.tracker.list().length, 4)
  const accepted = s.events.filter(e => e.event.endsWith('_accepted'))
  assert.equal(accepted.filter(e => e.event === 'import_accepted').length, 3)
  assert.equal(accepted.filter(e => e.event === 'publish_export_accepted').length, 1)
})

test('Studio phases dedupe locally across restart without sending internal IDs or content', () => {
  const s = setup()
  s.tracker.watch('studio-production', 'secret-plan', 'secret-project')
  const w = s.tracker.list()[0]
  s.tracker.observeStudio(w, {plan:{id:'other-plan'},analysis:{status:'completed'}})
  assert.equal(s.events.length,0)
  const snapshot={plan:{id:'secret-plan'},analysis:{status:'failed',error:'sk-secret /Users/private.mp4'}}
  s.tracker.observeStudio(w,snapshot);s.tracker.observeStudio(w,snapshot)
  const recovered=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
  recovered.observeStudio(recovered.list()[0],snapshot)
  assert.equal(s.events.length,0)
  s.tracker.watch('studio-export','secret-job','secret-project')
  s.tracker.observeStudio(s.tracker.list()[1],{jobs:[{job_id:'secret-job',status:'completed'}]})
  assert.equal(s.events[0].event,'studio_export_finished')
  assert.equal(JSON.stringify(s.events).includes('secret'),false)
  s.enable(false);s.tracker.list();s.enable(true)
  s.tracker.observeStudio(w,snapshot)
  assert.equal(s.events.length,1)
})
test('Studio screening distinguishes recommendations, manual fallback and import failure',()=>{
  for (const [snapshot,outcome] of [[{plan:{id:'plan',mode:'ai'},analysis:{status:'awaiting_confirmation'}},'recommended'],[{plan:{id:'plan',mode:'fallback'},analysis:{status:'awaiting_confirmation'}},'fallback'],[{analysis:{status:'failed'}},'error']]) {
    const s=setup();s.tracker.watch('studio-screen','private-project')
    s.tracker.observeStudio(s.tracker.list()[0],snapshot)
    assert.equal(s.events[0].props.outcome,outcome)
    assert.equal(s.events[0].props.studio_schema_version,2)
  }
})
test('actual Studio API enrolls accepted work and sends aggregate-only telemetry',async()=>{
  const s=setup(memory(),()=>Date.now())
  const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const transport={defaults:{},post:async(url)=>url==='/studio/import'?{project_id:'private-project'}:url.endsWith('/export')?{job_id:'private-job'}:{}}
  const file=path.join(__dirname,'../src/features/studio/api.ts')
  const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText
  const module={exports:{}}
  runInSandbox(js,{module,exports:module.exports,require:id=>({'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':transport,'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker}}[id])})
  const api=module.exports.studioApi
  await api.import({filename:'private.mp4',url:'https://private.test/?key=secret'})
  await api.confirmPlan('private-project','private-plan',['highlight'],{language:'source'})
  await api.export('private-project','private-draft',2)
  assert.equal(s.tracker.list().length,3)
  assert.equal(s.events.length,6)
  assert.equal(JSON.stringify(s.events).includes('private'),false)
  assert.equal(JSON.stringify(s.events).includes('secret'),false)
  for(const e of s.events) assert.ok(Object.keys(e.props).every(k=>['operation_id','flow_id','material_origin','auto_frame_retained','has_crop_track','has_manual_adjustment','studio_schema_version','request_duration_ms','source_type','has_subtitle','aspect','portrait_style','platform_count','brand_outro_enabled','goal_content','goal_highlight','goal_promo'].includes(k)))
  s.enable(false)
  await api.import({})
  assert.equal(s.events.length,6)
})
test('Studio aggregate requests retain failures and respect consent changes in flight',async()=>{
  const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const failure={response:{status:401},message:'private-key'}
  await assert.rejects(aggregate.observeStudioOperation('studio_export',async()=>{throw failure},()=>{}),e=>e===failure)
  assert.equal(s.events[1].props.error_code,'http_401')
  assert.equal(JSON.stringify(s.events).includes('private-key'),false)
  let finish;let accepted=false
  const pending=aggregate.observeStudioOperation('studio_import',()=>new Promise(r=>{finish=r}),()=>{accepted=true})
  s.tracker.clear();finish({project_id:'secret'});await pending
  assert.equal(accepted,false)
  assert.equal(s.events.length,3)
})

test('Studio allowlist rejects arbitrary values and preserves per-run partial counts',()=>{
 const props=core.safeStudioProperties({source_type:'secret',analysis_mode:'visual',title:'private',duration_ms:-1,goal:'private',requested_goals:['highlight','promo'],succeeded_goals:['highlight'],failed_goals:['promo'],error_code:'http_secret'})
 assert.equal(props.requested_count,2);assert.equal(props.failed_promo,true)
 assert.equal(JSON.stringify(props).includes('secret'),false);assert.equal(JSON.stringify(props).includes('private'),false)
 const s=setup();s.tracker.watch('studio-production','plan','project')
 s.tracker.observeStudio(s.tracker.list()[0],{plan:{id:'plan',confirmed_analysis:'visual'},analysis:{status:'failed',outcome:'partial',requested_goals:['highlight','promo'],succeeded_goals:['highlight'],failed_goals:['promo'],result_count:2,duration_ms:321}})
 assert.equal(s.events.length,0)
})
test('rescreen ignores an old plan while running and replaces the old local watch',()=>{
 const s=setup();s.tracker.watch('studio-screen','p');const old=s.tracker.list()[0]
 s.tracker.watch('studio-screen','p',undefined,undefined,{},true);const current=s.tracker.list()[0]
 s.tracker.observeStudio(old,{plan:{id:'old',mode:'ai'},analysis:{status:'awaiting_confirmation'}})
 s.tracker.observeStudio(current,{plan:{id:'old',mode:'ai'},analysis:{status:'running'}})
 assert.equal(s.events.length,0)
 s.tracker.observeStudio(current,{plan:{id:'new',mode:'local',local_evidence:{subtitle_status:'available'}},analysis:{status:'awaiting_confirmation'}})
 assert.equal(s.events[0].props.outcome,'recommended');assert.equal(s.events[0].props.recommendation_mode,'local')
 assert.equal(core.routeName('/import/private?token=secret'),'/import/:id')
 assert.equal(core.routeName('/project/private/studio/secret'),'/project/:id/studio/:draftId')
})
test('the UI does not emit studio_qa_checked; the backend owns that event', () => {
  const s = setup()
  s.tracker.watch('studio-variant', 'variant-1', 'project', undefined, {}, false, 'job-1')
  const qa = { mode: 'shadow', checks: [
    { checker: 'avsync', outcome: 'fail', bucket: '80_200', duration_ms: 12 },
    { checker: 'ending', outcome: 'fail', bucket: 'mid_word', duration_ms: 3, text: 'private caption' },
    { checker: 'loudness', outcome: 'pass', bucket: 'in_target', duration_ms: 40 },
  ] }
  const snapshot = { output_variants: [{ id: 'variant-1', draft_id: 'd', render_job_id: 'job-1', strategy_id: 'douyin', status: 'completed', qa }] }
  const watch = s.tracker.list()[0]
  s.tracker.observeStudio(watch, snapshot)
  s.tracker.observeStudio(watch, snapshot)
  assert.equal(s.events.filter(item => item.event === 'studio_qa_checked').length, 0)
  assert.equal(JSON.stringify(s.events).includes('private'), false)
  assert.equal(s.events.some(item => item.event === 'studio_variant_finished'), true)
})

test('immutable export repeated acceptance does not recount its completion',()=>{
 const s=setup();s.tracker.watch('studio-export','j','p');const w=s.tracker.list()[0]
 s.tracker.observeStudio(w,{jobs:[{job_id:'j',status:'completed',duration_ms:20}]})
 const insert=s.events[0].props.$insert_id
 s.tracker.watch('studio-export','j','p');s.tracker.observeStudio(s.tracker.list()[0],{jobs:[{job_id:'j',status:'completed'}]})
 assert.equal(s.events.length,1);assert.ok(insert.startsWith('studio-v1:'))
})
test('native download emits saved or failed, and opt-out in flight suppresses results',async()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 await aggregate.observeStudioDownload(async()=>42)
 assert.equal(s.events[1].event,'studio_download_saved')
 await assert.rejects(aggregate.observeStudioDownload(async()=>{throw Error('private filename')}))
 assert.equal(s.events[3].event,'studio_download_failed');assert.equal(JSON.stringify(s.events).includes('private'),false)
 let finish;const pending=aggregate.observeStudioDownload(()=>new Promise(r=>finish=r));s.tracker.clear();finish();await pending
 assert.equal(s.events.length,5)
})

test('social publishing distinguishes scheduling and inbox acceptance from published content',()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 assert.equal(aggregate.socialPublishOutcome('scheduled',true,[]),'scheduled')
 assert.equal(aggregate.socialPublishOutcome('submitted',false,[{success:true,fallback_to_inbox:true}]),'inbox')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[]),'unknown')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[{success:true},{success:false}]),'partial')
 assert.equal(aggregate.socialPublishOutcome('completed',false,[{success:false}]),'error')
 aggregate.socialPublishObserved(s.tracker.generation(),{source_type:'studio',gateway:'bilibili',outcome:'completed',url:'private'})
 assert.equal(s.events[0].props.source_type,'studio');assert.equal(JSON.stringify(s.events).includes('private'),false)
 const gen=s.tracker.generation();s.tracker.clear();aggregate.socialPublishObserved(gen,{outcome:'completed'});assert.equal(s.events.length,1)
})

test('UI workspace snapshots capture fast screening before confirm and never enroll historical projects',async()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const snapshot={plan:{id:'plan',mode:'local'},analysis:{status:'awaiting_confirmation'}}
 await aggregate.observeStudioWorkspace('p',async()=>snapshot);assert.equal(s.events.length,0)
 s.tracker.watch('studio-screen','p')
 assert.equal(await aggregate.observeStudioWorkspace('p',async()=>snapshot),snapshot)
 assert.equal(s.events.length,1);assert.equal(s.events[0].props.recommendation_mode,'local')
 await aggregate.observeStudioWorkspace('p',async()=>snapshot);assert.equal(s.events.length,1)
 assert.equal(core.safeStudioProperties(null).studio_schema_version,2)
})

test('late workspace response cannot settle a newer rescreen attempt',async()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 s.tracker.watch('studio-screen','p');let finish
 const pending=aggregate.observeStudioWorkspace('p',()=>new Promise(r=>finish=r))
 s.tracker.watch('studio-screen','p',undefined,undefined,{},true)
 finish({plan:{id:'old',mode:'ai'},analysis:{status:'awaiting_confirmation'}});await pending
 assert.equal(s.events.length,0)
})

test('readable but full storage cannot override an immediate opt-out', () => {
  const captured=[]
  const ph=load('posthog',{'posthog-js':{init(){},capture(...args){captured.push(args);return {}},opt_out_capturing(){},opt_in_capturing(){}},'./workflow':core},{localStorage:{getItem(){return null},setItem(){throw Error('quota')}},window:{}})
  ph.initAnalytics();ph.setAnalyticsEnabled(false)
  assert.equal(ph.isAnalyticsEnabled(),false);assert.equal(ph.captureBusinessEvent('blocked'),false)
  assert.equal(captured.length,0)
  ph.setAnalyticsEnabled(true);assert.equal(ph.captureBusinessEvent('allowed',{schema_version:999,runtime:'private'}),true)
  assert.equal(captured[0][1].schema_version,2);assert.equal(captured[0][1].runtime,'web')
})

test('sample classification and opaque flow/artifact survive restart and clear on opt-out', () => {
  const s=setup();s.tracker.rememberProject('private-project',core.projectProperties({settings:{example:true,example_version:2,secret:'sk-secret'}}))
  const first=s.tracker.context('private-project','private-job')
  assert.equal(first.material_origin,'sample');assert.equal(first.example_version,2)
  assert.match(first.flow_id,/^t-/);assert.match(first.artifact_id,/^t-/)
  const restored=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
  assert.equal(restored.context('private-project','private-job').artifact_id,first.artifact_id)
  restored.rememberProject('real-project',{material_origin:'user'})
  assert.equal(restored.context('real-project').material_origin,'user')
  assert.notEqual(restored.context('real-project').flow_id,first.flow_id)
  assert.equal(JSON.stringify(first).includes('private'),false)
  restored.clear();assert.equal(restored.context('private-project').material_origin,'unknown')
})

test('immutable receipts recover the right run after a newer plan replaced current state', () => {
  const s=setup();s.tracker.rememberProject('p',{material_origin:'sample'})
  s.tracker.watch('studio-production','old-plan','p',undefined,{},false,'old-run')
  const w=s.tracker.list()[0]
  s.tracker.observeStudio(w,{material_origin:'sample',plan:{id:'new-plan'},analysis:{run_id:'new-run',phase:'screening',status:'running'},analysis_history:[{run_id:'old-run',plan:{id:'old-plan',confirmed_analysis:'subtitle'},analysis:{phase:'production',status:'completed'}}]})
  s.tracker.observeStudio(w,{plan:{id:'new-plan'},analysis:{status:'failed'}})
  assert.equal(s.events.length,0)
  s.tracker.watch('studio-screen','p',undefined,undefined,{},true,'screen-run')
  s.tracker.observeStudio(s.tracker.list()[1],{analysis:{run_id:'production-run',phase:'production',status:'failed'}})
  assert.equal(s.events.length,0)
})

test('experience contract excludes config secrets and results cannot replay across consent changes', () => {
  const s=setup();const x=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const finish=x.beginExperience('provider_connection_test',{provider:'openai',placement:'home_setup',api_key:'sk-secret',model:'private-model',base_url:'https://private'})
  finish('failed',{error:'sk-secret'});finish('completed')
  assert.equal(s.events.length,2);assert.equal(s.events[1].props.outcome,'error')
  assert.equal(JSON.stringify(s.events).includes('secret'),false);assert.equal(JSON.stringify(s.events).includes('private'),false)
  const late=x.beginExperience('model_discovery',{provider:'openai'});s.tracker.clear();late('completed',{result_count:9})
  assert.equal(s.events.length,3)
})

test('provider validation keeps host and error enum only', () => {
  const s=setup();const x=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  x.trackProviderValidation({
    provider:'openai', result:'failed', error_type:'invalid_key',
    base_url_host:'https://api.openai.com/v1?key=sk-secret', api_key:'sk-secret', model:'gpt-4o',
  })
  const leaked=s.events[0].props
  assert.equal(leaked.base_url_host, 'api.openai.com')
  assert.equal(leaked.result, 'failed')
  assert.equal(leaked.upstream_error_type, 'invalid_key')
  assert.equal(leaked.error_type, undefined)
  assert.equal(JSON.stringify(leaked).includes('sk-secret'), false)
  assert.equal(JSON.stringify(leaked).includes('https://'), false)
  x.trackProviderValidation({provider:'api88', base_url_host:'88api.ai', result:'ok', error_type:'not-a-type', api_key:'sk-secret'})
  const event=s.events.find(e=>e.event==='provider_validation_finished' && e.props.provider==='api88')
  assert.equal(event.props.provider,'api88')
  assert.equal(event.props.base_url_host,'88api.ai')
  assert.equal(event.props.result,'success')
  assert.equal(event.props.upstream_error_type, undefined)
  assert.equal(event.props.error_type, undefined)
  assert.equal(JSON.stringify(event).includes('sk-secret'), false)
})

test('purpose-slot telemetry keeps source enums and drops model ids', () => {
  const s=setup()
  const x=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const finish=x.beginExperience('provider_configuration_save',{
    placement:'settings_model', provider:'dashscope',
    analysis_source:'preset', vision_source:'follow', cover_source:'frame',
    transcription_source:'whisper_local', vision_follow_lacks_vision:true,
    analysis_model:'qwen-plus', model:'secret-model', api_key:'sk-secret',
  })
  finish('completed')
  const props=s.events.find(e=>e.event==='provider_configuration_save_finished').props
  assert.equal(props.analysis_source,'preset')
  assert.equal(props.vision_source,'follow')
  assert.equal(props.cover_source,'frame')
  assert.equal(props.transcription_source,'whisper_local')
  assert.equal(props.vision_follow_lacks_vision,true)
  assert.equal(JSON.stringify(props).includes('qwen'),false)
  assert.equal(JSON.stringify(props).includes('secret'),false)
})

function settingsHook(s, transport, initial) {
  let cursor=0;const slots=[]
  const react={useState(value){const i=cursor++;if(!(i in slots))slots[i]=value;return [slots[i],next=>{slots[i]=typeof next==='function'?next(slots[i]):next}]},useRef(value){const i=cursor++;if(!(i in slots))slots[i]={current:value};return slots[i]},useEffect(){}}
  const providers={PROVIDERS:{openai:{}},}
  const defaults=loadTs('modelDefaults.ts')
  const access=loadTs('providerAccess.ts',{'../../i18n':{t:x=>x},'./providers':providers,'../../analytics/successRateContract':load('successRateContract')})
  const urls=loadTs('providerUrl.ts')
  const logic=load('../features/settings/modelSettingsLogic',{'./endpointProvider':loadTs('endpointProvider.ts'),'./providers':providers,'./modelDefaults':defaults,'./providerAccess':access,'./providerUrl':urls,'./providerPresets':loadTs('providerPresets.ts',{'../../i18n':{t:x=>x}})})
  const slotLogic=loadTs('defaultModelSlots.ts',{'../../i18n':{t:x=>x}})
  const experience=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  const custom=load('../features/settings/customProvider',{'./providerUrl':urls,'./modelSettingsLogic':logic,'./providerAccess':access},{URL,crypto:{randomUUID:()=>'uuid'}})
  const hook=load('../features/settings/useModelSettings',{
    react,antd:{message:{success(){},error(){}}},'../../i18n':{t:x=>x},'../studio/api':{errorText:()=> 'redacted'},'../studio/settingsReturn':{notifySettingsSaved(){}},
    '../../analytics/experience':experience,'./providers':providers,'./providerAccess':access,
    './modelSettingsApi':{modelSettingsApi:{get:async()=>structuredClone(initial),...transport},bindingCapability:()=> 'text'},
    './modelDefaults':defaults,'./modelSettingsLogic':logic,'./defaultModelSlots':slotLogic,
    './providerCatalogView':{assignAnalysis:value=>value,ensureCatalogConnection:value=>({settings:value,changed:false}),selectLocalAsr:value=>value},
    './providerPresets':{getProvider:()=>undefined},
    './customProvider':custom,
    './keyGuide':loadTs('keyGuide.ts'),
    './keyGuideBus':loadTs('keyGuideBus.ts'),
  },{window:{setTimeout(){},clearTimeout(){},addEventListener(){},removeEventListener(){}}})
  return ()=>{cursor=0;return hook.useModelSettings('home_setup')}
}
const modelFixture=()=>({version:1,saved:false,connections:[{id:'private-id',provider:'openai',api_key:'sk-secret',has_key:true,base_url:'https://gw.example/v1',name:'acct'}],analysis:{connection_id:'private-id',model:'private-model',capability:'text'},vision:null,cover:null,cover_enabled:false,allow_send_frame:false,analysis_mode:'subtitle',allow_visual_screening:false,transcription:{provider:'whisper_local',model:'base'},chunk_size:2000,min_score_threshold:.7,max_clips_per_collection:5})
test('R6 save persists transient validation without blocking and still blocks invalid keys', async () => {
 for (const [response, expected] of [
  [{success:false, result:'transient', error_type:'timeout'}, 'transient'],
  [{success:false, error_type:'connection'}, 'transient'],
  [{success:false, error_type:'rate_limited'}, 'transient'],
  [{success:false, error_type:'upstream_unavailable'}, 'transient'],
  [{code:'ECONNABORTED'}, 'transient'],
  [{code:'ERR_NETWORK'}, 'transient'],
  [{response:{status:503}}, 'transient'],
  [{response:{status:429}}, 'transient'],
  [{response:{status:401}}, 'failed'],
  [{success:false, result:'failed', error_type:'invalid_key'}, 'failed'],
 ]) {
  const s = setup()
  let persisted
  const render = settingsHook(s, {
   discover: async () => ({models:[],source:'catalog',preview:true}),
   test: async () => { if (response.code || response.response) throw response; return response },
   save: async value => { persisted = value; return {...value,saved:true} },
  }, modelFixture())
  await render().load(); await Promise.resolve()
  const outcome = await render().save()
  assert.equal(persisted.connections[0].validation_status, expected)
  assert.equal(outcome.ok, true)
  assert.equal(outcome.validationFailed, expected === 'failed')
  const telemetry = JSON.stringify(s.events)
  for (const value of ['sk-secret', 'https://', 'private-model', 'private-id']) assert.equal(telemetry.includes(value), false)
 }
})

test('actual unified settings hook records save once and HTTP-200 negative tests as failures',async()=>{
 const s=setup();const render=settingsHook(s,{discover:async()=>({models:[],source:'catalog',preview:true}),save:async value=>({...value,saved:true}),test:async()=>({success:false,error_type:'invalid_key',base_url_host:'gw.example'})},modelFixture())
 await render().load();await Promise.resolve();let m=render();await m.save();m=render();await m.test()
 assert.equal(s.events.filter(e=>e.event==='provider_configuration_save_finished').length,1)
 assert.equal(s.events.find(e=>e.event==='provider_configuration_save_finished').props.mode,'initial')
 assert.equal(s.events.find(e=>e.event==='provider_connection_test_finished').props.outcome,'error')
 const validation=s.events.filter(e=>e.event==='provider_validation_finished')
 assert.ok(validation.length>=1)
 assert.equal(validation[0].props.result,'failed')
 assert.equal(validation[0].props.upstream_error_type,'invalid_key')
 assert.equal(validation[0].props.base_url_host,'gw.example')
 assert.equal(validation[0].props.provider,'openai')
 assert.equal(s.events.some(e=>e.event==='api_key_configured'),false)
 assert.equal(JSON.stringify(s.events).includes('sk-secret'),false);assert.equal(JSON.stringify(s.events).includes('private'),false)
})
test('fetchModels ignores a late response after the URL changes',async()=>{
  const s=setup();const fetchPending=[]
  const render=settingsHook(s,{
    discover:()=>new Promise(()=>{}),
    fetchList:()=>new Promise(resolve=>fetchPending.push(resolve)),
  },modelFixture())
  await render().load();await Promise.resolve()
  let m=render();const id=m.settings.connections[0].id
  const stale=m.fetchModels({...m.settings.connections[0],base_url:'https://old.example/v1'})
  m=render();m.editConnection(m.settings.connections[0],{base_url:'https://new.example/v1'})
  m=render();const fresh=m.fetchModels({...m.settings.connections[0],base_url:'https://new.example/v1'})
  fetchPending[0]({ok:true,models:['stale-old'],recommended:{analysis:[]}})
  await Promise.resolve();m=render()
  assert.equal(JSON.stringify(m.lists[id]||{}).includes('stale-old'),false)
  fetchPending[1]({ok:true,models:['fresh-new'],recommended:{analysis:[]}})
  await fresh;await stale;m=render()
  assert.deepEqual((m.lists[id]||{models:[]}).models.map(item=>item.id),['fresh-new'])
  assert.equal(JSON.stringify(m.lists).includes('stale-old'),false)
  assert.equal(JSON.stringify(m.lists).includes('old.example'),false)
})

test('actual fetchList ignores stale completions',async()=>{
 const s=setup();const pending=[]
 const render=settingsHook(s,{
  discover:async()=>({models:[],source:'catalog',preview:true}),
  fetchList:()=>new Promise(resolve=>pending.push(resolve)),
 },modelFixture())
 await render().load();const m=render();const c=m.settings.connections[0]
 const first=m.fetchModels(c)
 const second=m.fetchModels(c)
 pending[0]({ok:true,models:['stale-id'],source:'live'})
 await Promise.resolve()
 pending[1]({ok:true,models:['fresh-id'],source:'live'})
 await second
 await first.catch(()=>{})
 const latest=render()
 const ids=latest.lists[c.id].models.map(model=>model.id)
 assert.equal(ids.join(','),'fresh-id')
 assert.equal(JSON.stringify(s.events).includes('stale-id'),false)
})

test('fetchList preserves recommendations and server hints without rediscovery',async()=>{
 let discoveries=0;const pending=[]
 const render=settingsHook(setup(),{
  discover:async()=>{discoveries++;return {models:[],source:'catalog',preview:true}},
  fetchList:()=>new Promise(resolve=>pending.push(resolve)),
 },modelFixture())
 await render().load();await Promise.resolve()
 const c=render().settings.connections[0];const initialDiscoveries=discoveries
 const success=render().fetchModels(c)
 assert.equal(render().busy[c.id],true)
 pending[0]({ok:true,models:['other','recommended'],recommended:{analysis:['recommended']},source:'cache'})
 await success
 assert.deepEqual(Array.from(render().lists[c.id].models,m=>m.id),['recommended','other'])
 assert.equal(render().lists[c.id].source,'cache')
 assert.equal(render().busy[c.id],false)
 assert.equal(discoveries,initialDiscoveries)
 const failed=render().fetchModels(c)
 pending[1]({ok:false,models:[],message_key:'settings.providers.fetch_list_failed'})
 await failed
 assert.equal(render().listErrors[c.id],'settings.providers.fetch_list_failed')
 assert.equal(render().busy[c.id],false)
 assert.deepEqual(Array.from(render().lists[c.id].models,m=>m.id),['recommended','other'])
})

test('actual discovery ignores stale completions and distinguishes preview from live results',async()=>{
 const s=setup();let pending=[]
 const render=settingsHook(s,{discover:()=>new Promise(resolve=>pending.push(resolve))},modelFixture())
 await render().load();const m=render();const c=m.settings.connections[0]
 const second=m.discover(c,true,'manual')
 pending[0]({models:[],source:'catalog',preview:true});await Promise.resolve()
 pending[1]({models:[{id:'private-model',analysis:true}],source:'live',preview:false});await second
 const results=s.events.filter(e=>e.event==='model_discovery_finished')
 assert.equal(results.length,1);assert.equal(results[0].props.source,'live');assert.equal(results[0].props.trigger,'manual')
})

test('sample render and native save share an artifact without exposing backend IDs',async()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 s.tracker.rememberProject('private-sample',{material_origin:'sample',example_version:1})
 const ctx=s.tracker.context('private-sample','private-job')
 s.tracker.watch('studio-export','private-job','private-sample',undefined,ctx)
 s.tracker.observeStudio(s.tracker.list()[0],{material_origin:'sample',jobs:[{job_id:'private-job',status:'completed'}]})
 aggregate.studioDownloadRequested('private-sample','private-job')
 assert.equal(s.events.some(e=>e.event==='studio_download_saved'),false)
 await aggregate.observeStudioDownload(async()=>42,'private-sample','private-job')
 for(const event of s.events){assert.equal(event.props.material_origin,'sample');assert.equal(event.props.artifact_id,ctx.artifact_id);assert.equal(event.props.flow_id,ctx.flow_id)}
 assert.equal(JSON.stringify(s.events).includes('private'),false)
})
test('retrying the same plan retains both execution attempts until independently observed',()=>{
 const s=setup()
 s.tracker.watch('studio-production','plan','p',undefined,{},false,'run-first')
 s.tracker.watch('studio-production','plan','p',undefined,{},false,'run-second')
 const state={plan:{id:'plan'},analysis:{status:'completed',phase:'production',run_id:'run-second'},analysis_history:[{run_id:'run-first',plan:{id:'plan'},analysis:{status:'failed',phase:'production'}}]}
 for(const watch of s.tracker.list())s.tracker.observeStudio(watch,state)
 assert.equal(s.events.length,0)
})

test('actual auto-frame API distinguishes automatic zero detection from retained edits',async()=>{
 const s=setup();const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const api=load('../features/studio/api',{'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':{post:async()=>({scenes:[{crop_x:null,fit_shots:2}]})},'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker},'./noticeRuntime':{noteWorkspaceCompletion(){}},'./subtitleState':load('../features/studio/subtitleState'),'./transcriptionRecovery':load('../features/studio/transcriptionRecovery',{'./recoveryClock':load('../features/studio/recoveryClock')})})
 s.tracker.rememberProject('private-project',{material_origin:'user'})
 await api.studioApi.autoFrame('private-project',{layout:'crop',scenes:[]},'auto')
 const event=s.events.find(e=>e.event==='studio_auto_frame_finished')
 assert.equal(event.props.framing_outcome,'no_detection');assert.equal(event.props.trigger,'auto')
 assert.equal(event.props.fit_count,2);assert.equal(event.props.framed_count,0)
 const draft={layout:'crop',scenes:[{framing_source:'auto',crop_track:[{private:42}]}]}
 assert.equal(api.draftProperties(draft).auto_frame_retained,true)
 draft.scenes[0].framing_adjusted=true
 assert.equal(api.draftProperties(draft).auto_frame_retained,false)
 assert.equal(api.draftProperties(draft).has_manual_adjustment,true)
 assert.equal(JSON.stringify(s.events).includes('private'),false)
})

test('framing installation retries use distinct terminal deduplication keys',()=>{
 const s=setup();const inserts=[]
 for(let i=0;i<2;i++){
  s.tracker.watch('framing-runtime','runtime',undefined,undefined,{},true)
  const watch=s.tracker.list()[0]
  s.tracker.emitOnce(watch,'finished','studio_framing_install_finished',{outcome:i?'completed':'failed'})
  inserts.push(s.events[i].props.$insert_id)
 }
 assert.notEqual(inserts[0],inserts[1])
 assert.equal(s.events[0].props.studio_schema_version,2)
})

test('1.5 API observes cover and retry terminal results across restart without content',async()=>{
 const s=setup()
 const aggregate=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const transport={post:async url=>url.endsWith('/cover/ai')?{job_id:'private-cover',status:'queued'}:{attempt:null,variant:{id:'private-variant',render_job_id:'private-new-render',status:'queued'}} /* #419: the retry command returns {attempt, variant} */,get:async()=>({job_id:'private-cover',status:'completed'}),put:async()=>({title:'private-title',description:'private-description',tags:['private-tag']})}
 const api=load('../features/studio/api',{'../../analytics/workflow':core,'../../analytics/posthog':{captureBusinessEvent:s.capture},'../../services/api':transport,'../../analytics/studio':aggregate,'../../analytics/observer':{workflow:s.tracker},'./noticeRuntime':{noteWorkspaceCompletion(){}},'./subtitleState':load('../features/studio/subtitleState'),'./transcriptionRecovery':load('../features/studio/transcriptionRecovery',{'./recoveryClock':load('../features/studio/recoveryClock')})}).studioApi
 s.tracker.rememberProject('private-project',{material_origin:'user'})
 await api.redesignVariantCover('private-project','private-variant')
 await api.variantCoverJob('private-project','private-variant') // terminal before the global poll
 assert.equal(s.events.filter(e=>e.event==='studio_cover_redesign_finished').length,1)
 await api.retryOutputVariant('private-project','private-variant')
 await api.updateVariantPost('private-project','private-variant',{title:'private-title',description:'private-description',tags:['private-tag']})
 const recovered=new core.WorkflowTracker(s.storage,()=>true,s.capture,()=>NOW)
 const snapshot={output_variants:[{id:'private-variant',draft_id:'private-draft',render_job_id:'private-old-render',strategy_id:'douyin',status:'failed',cover_job:{job_id:'private-cover',status:'completed'}}]}
 for(const w of recovered.list())recovered.observeStudio(w,snapshot)
 assert.equal(s.events.filter(e=>e.event==='studio_cover_redesign_finished').length,1)
 assert.equal(s.events.filter(e=>e.event==='studio_variant_finished').length,0) // not this retry
 snapshot.output_variants[0].render_job_id='private-new-render';snapshot.output_variants[0].status='completed'
 snapshot.jobs=[{job_id:'private-new-render',status:'completed',result:{outro_applied:false,warnings:['private error']}}]
 for(const w of recovered.list()){recovered.observeStudio(w,snapshot);recovered.observeStudio(w,snapshot)}
 const finished=s.events.filter(e=>e.event==='studio_variant_finished')
 assert.equal(finished.length,1);assert.equal(finished[0].props.outcome,'success');assert.equal(finished[0].props.outro_applied,false);assert.equal(finished[0].props.warning_count,1)
 assert.equal(JSON.stringify(s.events).includes('private'),false)
 assert.equal(s.events.filter(e=>e.event==='studio_post_save_accepted').length,1)
})

test('publish kit saving has disk evidence; browser clicks and opt-out never invent success',async()=>{
 const s=setup();const x=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const props={artifact_type:'publish_kit',strategy_id:'douyin'}
 x.studioDownloadRequested('private-project','private-render',props)
 assert.equal(s.events.length,1);assert.equal(s.events[0].props.download_mode,'browser')
 await x.observeStudioDownload(async()=>42,'private-project','private-render',props)
 assert.equal(s.events.at(-1).event,'studio_download_saved');assert.equal(s.events.at(-1).props.artifact_type,'publish_kit')
 await assert.rejects(x.observeStudioDownload(async()=>{throw {code:'ERR_NETWORK',message:'private path'}},'private-project','private-render',props))
 assert.equal(s.events.at(-1).event,'studio_download_failed');assert.equal(s.events.at(-1).props.error_code,'network')
 let finish;const pending=x.observeStudioDownload(()=>new Promise(r=>finish=r),'p','j',props)
 const count=s.events.length;s.tracker.clear();finish(42);await pending
 assert.equal(s.events.length,count);assert.equal(JSON.stringify(s.events).includes('private'),false)
})

test('portrait import and saved outro preference retain explicit enums and confirmed state',()=>{
 const s=setup();const x=load('studio',{'./flags':{flagAssigned:()=>false},'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const body=new FormData();body.set('portrait_style','podcast');body.set('name','private name');body.append('platforms','douyin')
 const props=core.safeStudioProperties(x.studioImportProperties(body))
 assert.equal(props.portrait_style,'podcast');assert.equal(props.brand_outro_enabled,undefined)
 body.set('brand_outro_enabled','false');assert.equal(x.studioImportProperties(body).brand_outro_enabled,false)
 const experience=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
 const done=experience.beginExperience('output_branding_save',{section:'app',brand_outro_enabled:false})
 done('completed',{brand_outro_enabled:false});done('failed')
 assert.equal(s.events.length,2);assert.equal(s.events[1].props.brand_outro_enabled,false)
 const late=experience.beginExperience('output_branding_save',{brand_outro_enabled:true});const n=s.events.length;s.tracker.clear();late('completed')
 assert.equal(s.events.length,n);assert.equal(JSON.stringify(props).includes('private'),false)
})

test('every flag evaluation carries app_version as a semver flag person property', () => {
  const storage = memory()
  const calls = []
  const sdk = {
    init(_key, cfg) { calls.push(['init']); cfg.loaded?.(sdk) },
    capture() { return {} },
    opt_out_capturing() {}, opt_in_capturing() {},
    set_config() {},
    register(props) { calls.push(['register', props.app_version]) },
    setPersonPropertiesForFlags(props, reload) { calls.push(['flagprops', props.app_version, reload]) },
    reloadFeatureFlags() { calls.push(['reload']) },
    featureFlags: { setReloadingPaused() {}, getFlagVariants() { return {} } },
    onFeatureFlags() {},
  }
  const file = path.join(__dirname, '../src/analytics/posthog.ts')
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText
  const module = { exports: {} }
  runInSandbox(js, { exports: module.exports, module, console, localStorage: storage, window: {},
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key', VITE_APP_VERSION: 'v1.5.7' },
    require: (id) => {
      if (id === 'posthog-js') return { __esModule: true, default: sdk }
      if (id === './workflow') return core
      if (id === './runtime') return load('runtime', {}, { window: {} })
      if (id === '../utils/apiConfig') return { apiConfigManager: { getBaseUrl: () => '/api/v1', addListener: () => () => {} } }
      throw new Error(`Unexpected dependency: ${id}`)
    } }, { filename: file })
  const ph = module.exports
  assert.equal(JSON.stringify(ph.flagPersonProperties()), '{"app_version":"1.5.7"}')
  ph.initAnalytics()
  // Set inside loaded, before the SDK's first flag request, without an extra reload.
  assert.equal(JSON.stringify(calls.slice(0, 3)), JSON.stringify([['init'], ['register', '1.5.7'], ['flagprops', '1.5.7', false]]))
  ph.setAnalyticsEnabled(false)
  calls.length = 0
  ph.setAnalyticsEnabled(true)
  const props = calls.findIndex(call => call[0] === 'flagprops')
  const reload = calls.findIndex(call => call[0] === 'reload')
  assert.ok(props >= 0 && reload > props, JSON.stringify(calls))
})

const separateModelFixture = () => {
 const value = modelFixture()
 value.saved = true
 for (const role of ['vision', 'cover', 'transcription']) {
  value.connections.push({...value.connections[0], id:role, validation_status:'unchecked'})
  value[role] = {connection_id:role, model:`private-${role}`, capability:'auto', ...(role === 'transcription' ? {provider:'cloud'} : {})}
 }
 value.cover_enabled = true
 return value
}
test('save validates every separate connection and persists their results without leaking identifiers', async () => {
 const s=setup(); const calls=[]; let persisted
 const render=settingsHook(s,{
  discover:async()=>({models:[],source:'catalog',preview:true}),
  test:async(connection,model,vision,purpose)=>{calls.push([connection.id,model,vision,purpose]);return {success:connection.id!=='cover',error_type:connection.id==='cover'?'invalid_key':undefined}},
  save:async value=>{persisted=value;return {...value,saved:true}},
 },separateModelFixture())
 await render().load(); await Promise.resolve()
 const result=await render().save()
 assert.deepEqual(calls.map(call=>call[0]).sort(),['cover','private-id','transcription','vision'])
 assert.deepEqual(calls.find(call=>call[0]==='vision').slice(2),[true,'vision'])
 assert.equal(persisted.connections.find(c=>c.id==='vision').validation_status,'ok')
 assert.equal(persisted.connections.find(c=>c.id==='transcription').validation_status,'ok')
 assert.equal(persisted.connections.find(c=>c.id==='cover').validation_status,'failed')
 assert.equal(result.validationFailed,true)
 assert.equal(JSON.stringify(s.events).includes('private'),false)
 assert.equal(JSON.stringify(s.events).includes('sk-secret'),false)
})
test('each purpose has a manual test entry point that recovers a failed separate connection', async () => {
 for (const role of ['vision','cover','transcription']) {
  const s=setup(); const calls=[]; const initial=separateModelFixture()
  initial.connections.find(c=>c.id===role).validation_status='failed'
  const render=settingsHook(s,{
   discover:async()=>({models:[],source:'catalog',preview:true}),
   test:async(connection,model,vision,purpose)=>{calls.push([connection.id,model,vision,purpose]);return {success:true}},
  },initial)
  await render().load(); await Promise.resolve(); await render().test(role)
  assert.deepEqual(calls,[[role,`private-${role}`,role==='vision',role]])
  assert.equal(render().settings.connections.find(c=>c.id===role).validation_status,'ok')
  assert.equal(render().dirty,true)
 }
})

test('save skips disabled/local connections and deduplicates shared access checks', async () => {
 const initial=separateModelFixture()
 initial.vision={...initial.analysis}
 initial.cover_enabled=false
 initial.transcription={provider:'whisper_local',model:'base'}
 initial.connections.slice(1).forEach(c=>{c.validation_status='failed'})
 const calls=[];const s=setup()
 const render=settingsHook(s,{
  discover:async()=>({models:[],source:'catalog',preview:true}),
  test:async connection=>{calls.push(connection.id);return {success:true}},
  save:async value=>({...value,saved:true}),
 },initial)
 await render().load();await Promise.resolve()
 const result=await render().save()
 assert.deepEqual(calls,['private-id'])
 assert.equal(result.validationFailed,false)
})

test('save rechecks only the changed optional binding on a validated connection', async () => {
 const initial=separateModelFixture()
 initial.connections.forEach(c=>{c.validation_status='ok'})
 const calls=[];const render=settingsHook(setup(),{
  discover:async()=>({models:[],source:'catalog',preview:true}),
  test:async(connection,model)=>{calls.push([connection.id,model]);return {success:true,models:[model]}},
  save:async value=>({...value,saved:true}),
 },initial)
 await render().load();await Promise.resolve()
 render().update({cover:{...initial.cover,model:'private-new-image'}})
 await render().save()
 assert.deepEqual(calls,[['cover','private-new-image']])
 assert.equal(render().lists.cover.preview,true,'non-chat ids must not be backfilled as live chat models')
})

test('catalog endpoint validation unlocks only the current credentials and keeps telemetry sanitized', async () => {
  for (const stale of [false, true]) {
    const s = setup()
    let finishProbe
    const initial = { ...modelFixture(), saved: true, analysis: null,
      connections: [{ id: 'endpoint', name: 'Endpoint', provider: 'compatible', catalog_provider_id: 'azure-openai',
        base_url: 'https://endpoint.example.test/v1', api_key: 'test-only', validation_status: 'unchecked' }] }
    const render = settingsHook(s, { discover: async () => ({ models: [], source: 'live' }),
      test: () => new Promise(resolve => { finishProbe = resolve }) }, initial)
    await render().load()
    const pending = render().validateCatalogConnection(render().settings.connections[0], 'test-model')
    if (stale) render().editConnection(render().settings.connections[0], { base_url: 'https://changed.example.test/v1' })
    finishProbe({ ok: true, success: true, result: 'success', base_url_host: 'endpoint.example.test', model_ids: ['test-model'] })
    await pending
    assert.equal(render().settings.connections[0].validation_status, stale ? 'unchecked' : 'ok')
    assert.equal(render().settings.analysis, null)
    const telemetry = JSON.stringify(s.events)
    for (const privateValue of ['https://', 'test-only', 'test-model', 'azure-openai']) assert.equal(telemetry.includes(privateValue), false)
  }
})

test('R11: unreadable localStorage at startup sends only "off", never "on"', async () => {
  const puts = []
  const broken = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') }, removeItem() {} }
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: broken, window: {},
    fetch: (url, opts) => {
      if (String(url).includes('/settings/analytics-consent')) puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok: true })
    },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(!puts.includes(true), JSON.stringify(puts))
  assert.deepEqual(puts, [false])
})

test('R11: an opt-out keeps retrying after the backoff is exhausted until the API recovers', async () => {
  const puts = []
  let up = false
  const timers = []
  const storage = memory()
  storage.setItem('autoclip.analytics.optOut', 'true')
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: storage, window: {},
    // Real browsers have AbortController: the 5 s abort timer is armed and cleared around every PUT.
    AbortController, ...fakeTimers(timers),
    fetch: (url, opts) => {
      if (!String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok: up })
    },
  })
  ph.initAnalytics()
  for (let i = 0; i < 12; i++) {
    await new Promise(resolve => setImmediate(resolve))
    const fn = timers.shift()
    assert.equal(typeof fn, 'function', `retry ${i} was not scheduled (gave up)`)
    if (i === 11) up = true // API recovers well after the 5 exponential retries
    fn()
  }
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(puts.length >= 13)
  assert.ok(puts.every(v => v === false))
  const settled = puts.length
  await new Promise(resolve => setImmediate(resolve))
  for (const fn of timers.splice(0)) fn()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(puts.length, settled) // once accepted, no more retries
})

test('R12 #16: unreadable preference keeps SDK init, capture, flags and identity OFF', async () => {
  const calls = { init: 0, capture: 0, identity: 0, flags: 0 }
  const broken = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') }, removeItem() {} }
  const ph = load('posthog', { 'posthog-js': {
    init() { calls.init++ }, capture() { calls.capture++; return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {}, reloadFeatureFlags() { calls.flags++ },
  }, './workflow': core }, {
    localStorage: broken, window: {},
    fetch: (url) => { if (String(url).includes('/settings/analytics-identity')) calls.identity++; return Promise.resolve({ ok: true }) },
  })
  ph.initAnalytics()
  assert.equal(ph.isAnalyticsEnabled(), false)
  assert.equal(ph.captureBusinessEvent('studio_import_started', {}), false)
  ph.trackPageview('/')
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(calls, { init: 0, capture: 0, identity: 0, flags: 0 })
  assert.equal(ph.readLoadedFlag('pkg_templates_v1'), undefined)
})

test('R12 #19: two windows interleave — storage OFF from another window drops a queued ON retry', async () => {
  const shared = memory()
  const puts = []
  let ok = false
  const timers = []
  const make = () => load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: shared, window: {},
    setTimeout: (fn) => { timers.push(fn); return timers.length }, clearTimeout: () => {},
    fetch: (url, opts) => {
      if (!String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok })
    },
  })
  const a = make()
  a.initAnalytics()
  a.setAnalyticsEnabled(true) // A wants ON; the PUT fails and a retry is queued
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(timers.length > 0)
  const b = make()
  b.setAnalyticsEnabled(false) // B (another window) turns analytics OFF in shared storage
  ok = true
  await new Promise(resolve => setImmediate(resolve))
  const before = puts.length
  for (const fn of timers.splice(0)) fn() // A's queued retry fires
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(!puts.slice(before).includes(true), JSON.stringify(puts))
  assert.equal(puts[puts.length - 1], false)
})

test('R13 #26: storage readable but write fails — session OFF is sent on close and every retry', async () => {
  const store = { ['autoclip.analytics.optOut']: 'false' }
  const readable = { getItem: (k) => (k in store ? store[k] : null), setItem() { throw new Error('quota') }, removeItem() {} }
  const puts = []
  const timers = []
  let ok = true
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {}, reloadFeatureFlags() {} }, './workflow': core }, {
    localStorage: readable, window: {},
    setTimeout: (fn) => { timers.push(fn); return timers.length }, clearTimeout: () => {},
    fetch: (url, opts) => {
      if (!String(url).includes('/settings/analytics-consent')) return Promise.resolve({ ok: true })
      puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok })
    },
  })
  const tick = () => new Promise(resolve => setImmediate(resolve))
  ph.initAnalytics(); await tick()
  assert.deepEqual(puts, [true])
  ok = false
  ph.setAnalyticsEnabled(false) // close: storage write throws, storage still reads "on"
  await tick()
  assert.equal(puts.at(-1), false, 'close must send off')
  assert.equal(ph.isAnalyticsEnabled(), false)
  for (let i = 0; i < 7 && timers.length; i++) { timers.shift()(); await tick() }
  assert.ok(puts.length >= 4)
  assert.ok(puts.slice(1).every(v => v === false), `retries must stay off: ${puts}`)
  ok = true; if (timers.length) { timers.shift()(); await tick() }
  assert.equal(puts.at(-1), false)
})

test('R13 #26: shared storage OFF still vetoes a stale session ON', async () => {
  const shared = memory()
  const puts = []
  const timers = []
  const ph = load('posthog', { 'posthog-js': { init() {}, capture() { return {} },
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111', opt_in_capturing() {}, opt_out_capturing() {} }, './workflow': core }, {
    localStorage: shared, window: {}, AbortController, ...fakeTimers(timers),
    fetch: (url, opts) => { if (String(url).includes('analytics-consent')) puts.push(JSON.parse(opts.body).enabled); return Promise.resolve({ ok: false }) },
  })
  ph.setAnalyticsEnabled(true); await new Promise(r => setImmediate(r))
  shared.setItem('autoclip.analytics.optOut', 'true') // another window turned it off
  assert.ok(timers.length)
  timers.shift()(); await new Promise(r => setImmediate(r)) // queued retry of the stale session ON
  assert.equal(puts.at(-1), false)
})

test('1.5.7 connection-test failure keeps closed error_code, integer status and config_source only', () => {
  const s=setup();const x=load('experience',{'./posthog':{captureBusinessEvent:s.capture},'./observer':{workflow:s.tracker},'./workflow':core})
  x.trackExperience('provider_connection_test_finished', { outcome:'failed', error_code:'dns', http_status:503, config_source:'customized', base_url:'https://gw.example/v1', api_key:'sk-secret', detail:'upstream private' })
  x.trackExperience('provider_connection_test_finished', { outcome:'failed', error_code:'https://leak', http_status:'503', config_source:'https://gw.example' })
  const [ok, bad] = s.events.map(e => e.props)
  assert.equal(ok.error_code, 'dns'); assert.equal(ok.http_status, 503); assert.equal(ok.config_source, 'customized')
  assert.equal(JSON.stringify(ok).includes('sk-secret') || JSON.stringify(ok).includes('https://') || JSON.stringify(ok).includes('private'), false)
  assert.equal(bad.error_code, undefined); assert.equal(bad.http_status, undefined); assert.equal(bad.config_source, undefined)
})

test('1.5.7 connection-test codes: 422 local validation, gemini-style results, transport', () => {
  const c = load('connectionTestCode')
  const r422 = (detail) => ({ response: { status: 422, data: { detail } } })
  assert.equal(c.codeFromRequestError(r422('请填写 API Key')), 'empty_key')
  assert.equal(c.codeFromRequestError(r422('x'), { emptyKey: true }), 'empty_key')
  assert.equal(c.codeFromRequestError(r422('请填写接口地址，不要填控制台网址')), 'bad_base_url')
  assert.equal(c.codeFromRequestError(r422('field required')), 'invalid_request')
  assert.equal(c.codeFromRequestError({ code: 'ECONNABORTED' }), 'timeout')
  assert.equal(c.codeFromRequestError({ code: 'ERR_NETWORK' }, { desktop: false }), 'cors')
  assert.equal(c.codeFromRequestError({ code: 'ERR_NETWORK' }), 'network')
  assert.equal(c.codeFromRequestError({ response: { status: 502 } }), 'http_5xx')
  // Gemini 1.5.6 results had error_type but no error_code: still classified, never 'uncoded'.
  assert.equal(c.codeFromResult({ error_type: 'invalid_key', http_status: 400 }), 'invalid_key')
  assert.equal(c.codeFromResult({ error_type: 'upstream_unavailable' }), 'http_5xx')
  assert.equal(c.codeFromResult({ http_status: 429 }), 'rate_limited')
  assert.equal(c.codeFromResult({ error_code: 'dns' }), 'dns')
  assert.equal(c.codeFromResult({}), 'unknown')
  for (const type of ['constructor', '__proto__', 'toString', 'hasOwnProperty']) assert.equal(c.codeFromResult({ error_type: type }), 'unknown', type)
  assert.equal(c.codeFromResult({ error_code: 'constructor' }), 'unknown')
  assert.equal(c.safeHttpStatus(503), 503); assert.equal(c.safeHttpStatus('503'), undefined)
})

test('implicit on adopts a backend analytics opt-out and does not PUT enabled true', async () => {
  const storage = memory()
  const puts = []
  const sdk = {
    init(_key, config) { config.loaded(sdk) },
    capture() { return {} }, register() {},
    get_distinct_id: () => '018f6b2a-7c3d-7b2a-8c11-111111111111',
    opt_in_capturing() {}, opt_out_capturing() {}, set_config() {},
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, {
    localStorage: storage, window: {},
    fetch: (url, opts) => {
      if (String(url).includes('/settings/privacy')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ analytics: false, crash_reports: true, distinct_id: '018f6b2a-7c3d-7b2a-8c11-222222222222' }),
        })
      }
      if (String(url).includes('/settings/analytics-consent')) puts.push(JSON.parse(opts.body).enabled)
      return Promise.resolve({ ok: true, json: async () => ({}) })
    },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(!puts.includes(true), JSON.stringify(puts))
  assert.deepEqual(puts, [false])
  assert.equal(storage.getItem('autoclip.analytics.optOut'), 'true')
  assert.equal(ph.isAnalyticsEnabled(), false)
  assert.equal(ph.captureBusinessEvent('studio_import_started', {}), false)
})

test('a launch-frozen distinct id does not overwrite a newer backend id', async () => {
  const launch = '018f6b2a-7c3d-7b2a-8c11-111111111111'
  const newer = '018f6b2a-7c3d-7b2a-8c11-222222222222'
  const identity = []
  const sdk = {
    init(_key, config) { config.loaded(sdk) },
    register() {}, get_distinct_id: () => launch,
    opt_in_capturing() {}, opt_out_capturing() {},
  }
  const ph = load('posthog', { 'posthog-js': sdk, './workflow': core }, {
    localStorage: memory(),
    window: { __AUTOCLIP_RUNTIME__: { os: 'macos', arch: 'arm64', distinct_id: launch } },
    fetch: (url, opts) => {
      if (String(url).includes('/settings/privacy')) {
        return Promise.resolve({ ok: true, json: async () => ({ analytics: true, distinct_id: newer, crash_reports: true }) })
      }
      if (String(url).includes('/settings/analytics-identity')) identity.push(JSON.parse(opts.body).distinct_id)
      return Promise.resolve({ ok: true, json: async () => ({}) })
    },
  })
  ph.initAnalytics()
  await new Promise(resolve => setImmediate(resolve))
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(identity, [])
  assert.equal(ph.isAnalyticsEnabled(), true)
})
