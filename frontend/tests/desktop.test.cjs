const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
function load(name, mocks, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '../src/desktop', `${name}.ts`), 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText
  const module = { exports: {} }
  const sandbox = { exports: module.exports, module, console,
    __env: { PROD: true, VITE_PUBLIC_SENTRY_DSN: 'https://public@example.invalid/1', VITE_APP_VERSION: '1.3.1' },
    ...globals }
  sandbox.require = id => {
    if (id in mocks) return mocks[id]
    if (id.startsWith('./')) return load(id.slice(2).replace(/\.ts$/, ''), mocks, globals)
    throw Error(id)
  }
  runInSandbox(js, sandbox)
  return module.exports
}
const DESKTOP_WINDOW = { __TAURI_INTERNALS__: {} }
test('I652: frontend Sentry initializes only in the packaged desktop production build', () => {
  const DSN = 'https://public@example.invalid/1'
  const cases = [
    ['packaged desktop production build', { PROD: true, VITE_PUBLIC_SENTRY_DSN: DSN, VITE_APP_VERSION: '1.5.7' }, DESKTOP_WINDOW, 1],
    ['dev server / tauri dev', { PROD: false, DEV: true, VITE_PUBLIC_SENTRY_DSN: DSN, VITE_APP_VERSION: '1.5.7' }, DESKTOP_WINDOW, 0],
    ['unknown release', { PROD: true, VITE_PUBLIC_SENTRY_DSN: DSN, VITE_APP_VERSION: '' }, DESKTOP_WINDOW, 0],
    ['production bundle opened in a browser tab', { PROD: true, VITE_PUBLIC_SENTRY_DSN: DSN, VITE_APP_VERSION: '1.5.7' }, {}, 0],
  ]
  for (const [name, env, window, expected] of cases) {
    let inits = 0
    const sentry = load('sentry', { '@sentry/react': { init: () => { inits++ }, setUser() {} } }, { __env: env, window, localStorage: { getItem: () => null, setItem() {} } })
    sentry.initSentry()
    sentry.setCrashReportsEnabled(true)
    assert.equal(inits, expected, name)
  }
})
test('crash payload removes private text and retains code positions for source maps', () => {
  let config
  const sentry = load('sentry', { '@sentry/react': { init: c => { config = c } } }, { localStorage: { getItem: () => null }, window: DESKTOP_WINDOW })
  sentry.initSentry()
  const event = config.beforeSend({ event_id: 'event', release: 'autoclip-frontend@1.3.1',
    message: 'private', request: { data: 'private' }, extra: { secret: 'private' }, breadcrumbs: ['private'], user: { id: 'private' },
    exception: { values: [{ type: 'TypeError', value: 'private', stacktrace: { frames: [{ filename: 'http://localhost/assets/index.js?token=private', lineno: 1, colno: 20, function: 'render', vars: { text: 'private' } }] } }] },
    debug_meta: { images: [{ debug_id: 'build-id' }] } })
  assert.ok(!JSON.stringify(event).includes('private'))
  assert.equal(event.exception.values[0].stacktrace.frames[0].colno, 20)
  assert.equal(event.debug_meta.images[0].debug_id, 'build-id')
})
test('crash opt-out takes effect even when storage is blocked and rapid toggles do not reinitialize', () => {
  let config; let inits = 0
  const sentry = load('sentry', { '@sentry/react': { init: c => { config = c; inits++ } } }, { localStorage: { getItem() { throw Error() }, setItem() { throw Error() } }, window: DESKTOP_WINDOW })
  sentry.initSentry(); sentry.setCrashReportsEnabled(false)
  assert.equal(sentry.isCrashReportsEnabled(), false)
  assert.equal(config.beforeSend({}), null)
  sentry.setCrashReportsEnabled(true); sentry.setCrashReportsEnabled(false)
  assert.equal(inits, 1)
  assert.equal(config.beforeSend({}), null)
})
test('manual update failure rejects instead of claiming the app is current; automatic checks stay quiet', async () => {
  const writes = []
  const updater = load('updater', { '../utils/desktopMode': { isDesktopMode: async () => true }, '@tauri-apps/plugin-updater': { check: async () => { throw Error('offline') } } }, { localStorage: { getItem: () => null, setItem: (k) => writes.push(k) } })
  await assert.rejects(updater.checkForUpdate(), /offline/)
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.deepEqual(writes, [])
})
test('an available update is checked again next launch; an up-to-date result waits a day', async () => {
  const schedule = load('updateSchedule', {})
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) }
  assert.equal(schedule.shouldCheckAutomatically(storage, 1000), true)
  schedule.rememberSuccessfulCheck(storage, 1000, 'current')
  assert.equal(schedule.shouldCheckAutomatically(storage, 1000 + 60_000), false)
  assert.equal(schedule.shouldCheckAutomatically(storage, 1000 + schedule.UPDATE_CHECK_INTERVAL_MS), true)
  schedule.rememberSuccessfulCheck(storage, 2000, 'available')
  assert.equal(schedule.shouldCheckAutomatically(storage, 2000 + 60_000), true)
  const started = schedule.applyDownloadEvent({ received: 0, total: 0, percent: null }, { event: 'Started', data: { contentLength: 200 } })
  const mid = schedule.applyDownloadEvent(started, { event: 'Progress', data: { chunkLength: 50 } })
  assert.equal(mid.percent, 25)
  assert.equal(schedule.applyDownloadEvent(mid, { event: 'Finished' }).percent, 100)
  assert.equal(schedule.previewNotes('# 标题\n\n- 后台下载新版本\n'), '后台下载新版本')
  const store2 = new Map()
  const storage2 = { getItem: (k) => store2.get(k) ?? null, setItem: (k, v) => store2.set(k, String(v)) }
  let calls = 0
  const updater = load('updater', {
    '../utils/desktopMode': { isDesktopMode: async () => true },
    '@tauri-apps/plugin-updater': { check: async () => { calls += 1; return calls === 1 ? null : { version: '1.4.0', body: '- 提示重启', download() {}, install() {}, close() {} } } },
  }, { localStorage: storage2 })
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.equal(store2.get('autoclip.updater.lastResult'), 'current')
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.equal(calls, 1)
  store2.set('autoclip.updater.lastResult', 'available')
  const found = await updater.maybeCheckForUpdate()
  assert.equal(found.version, '1.4.0')
  assert.equal(store2.get('autoclip.updater.lastResult'), 'available')
})
test('the same new version is offered at most once a day; a newer version can remind the same day', () => {
  const schedule = load('updateSchedule', {})
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) }
  assert.equal(schedule.areRemindersEnabled(storage), true)
  assert.equal(schedule.shouldRemind(storage, '1.5.7', 1_000), true)
  schedule.rememberReminder(storage, '1.5.7', 1_000)
  assert.equal(store.get('autoclip.updater.lastRemindedVersion'), '1.5.7')
  assert.equal(store.get('autoclip.updater.lastRemindedAt'), '1000')
  assert.equal(schedule.shouldRemind(storage, '1.5.7', 1_000 + 60_000), false)
  assert.equal(schedule.shouldRemind(storage, '1.5.7', 1_000 + schedule.UPDATE_CHECK_INTERVAL_MS - 1), false)
  assert.equal(schedule.shouldRemind(storage, '1.5.7', 1_000 + schedule.UPDATE_CHECK_INTERVAL_MS), true)
  assert.equal(schedule.shouldRemind(storage, '1.5.9', 1_000 + 60_000), true)
})
test('turning off reminders skips automatic checks and does not prompt', async () => {
  const schedule = load('updateSchedule', {})
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) }
  schedule.writeRemindersEnabled(storage, false)
  assert.equal(schedule.areRemindersEnabled(storage), false)
  assert.equal(schedule.shouldCheckAutomatically(storage, 1_000), false)
  assert.equal(schedule.shouldRemind(storage, '1.5.7', 1_000), false)
  let calls = 0
  const updater = load('updater', {
    '../utils/desktopMode': { isDesktopMode: async () => true },
    '@tauri-apps/plugin-updater': { check: async () => { calls += 1; return { version: '1.5.7', close() {} } } },
  }, { localStorage: storage })
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.equal(calls, 0)
  assert.equal(store.has('autoclip.updater.lastCheckAt'), false)
})
test('already reminding the same version today does not offer it again even if the check still finds it', async () => {
  const schedule = load('updateSchedule', {})
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) }
  const now = Date.now()
  schedule.rememberSuccessfulCheck(storage, now, 'available')
  schedule.rememberReminder(storage, '1.5.7', now)
  let closed = 0
  const updater = load('updater', {
    '../utils/desktopMode': { isDesktopMode: async () => true },
    '@tauri-apps/plugin-updater': { check: async () => ({ version: '1.5.7', close() { closed += 1 } }) },
  }, { localStorage: storage })
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.equal(closed, 1)
})
test('provider answers are dropped and the daily cap samples after full fidelity', () => {
  const store = new Map()
  const localStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
  }
  let config
  const sentry = load('sentry', { '@sentry/react': { init: (c) => { config = c } } }, { localStorage, window: DESKTOP_WINDOW })
  sentry.initSentry()
  const dropped = config.beforeSend({
    event_id: '00000000-0000-0000-0000-000000000001',
    tags: { http_status: 429, upstream_error_type: 'rate_limited' },
    exception: { values: [{ type: 'Error', value: 'private' }] },
  })
  assert.equal(dropped, null)
  assert.equal(store.size, 0)
  for (let i = 0; i < 15; i++) {
    const kept = config.beforeSend({
      event_id: '00000000-0000-0000-0000-000000000001',
      exception: { values: [{ type: 'Error', value: 'x' }] },
    })
    assert.ok(kept)
  }
  assert.equal(config.beforeSend({
    event_id: '00000000-0000-0000-0000-000000000001',
    exception: { values: [{ type: 'Error', value: 'x' }] },
  }), null)
  assert.ok(config.beforeSend({
    event_id: '00000000-0000-0000-0000-000000000000',
    exception: { values: [{ type: 'Error', value: 'x' }] },
  }))
})
test('offline automatic checks stay silent and do not persist a successful check', async () => {
  const store = new Map()
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) }
  const updater = load('updater', {
    '../utils/desktopMode': { isDesktopMode: async () => true },
    '@tauri-apps/plugin-updater': { check: async () => { throw Object.assign(new Error('429 rate limited'), { status: 429 }) } },
  }, { localStorage: storage })
  assert.equal(await updater.maybeCheckForUpdate(), null)
  assert.equal(store.get('autoclip.updater.lastCheckAt'), undefined)
  assert.equal(store.get('autoclip.updater.lastResult'), undefined)
})
