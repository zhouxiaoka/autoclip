const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
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
  vm.runInNewContext(js, sandbox)
  return module.exports
}
test('crash payload removes private text and retains code positions for source maps', () => {
  let config
  const sentry = load('sentry', { '@sentry/react': { init: c => { config = c } } }, { localStorage: { getItem: () => null } })
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
  const sentry = load('sentry', { '@sentry/react': { init: c => { config = c; inits++ } } }, { localStorage: { getItem() { throw Error() }, setItem() { throw Error() } } })
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
