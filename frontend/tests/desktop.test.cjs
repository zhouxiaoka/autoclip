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
  vm.runInNewContext(js, { exports: module.exports, module, console,
    __env: { PROD: true, VITE_PUBLIC_SENTRY_DSN: 'https://public@example.invalid/1', VITE_APP_VERSION: '1.3.1' },
    require: id => { if (id in mocks) return mocks[id]; throw Error(id) }, ...globals })
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
  const updater = load('updater', { '../utils/desktopMode': { isDesktopMode: async () => true }, '@tauri-apps/plugin-updater': { check: async () => { throw Error('offline') } } }, { localStorage: { getItem: () => null, setItem() {} } })
  await assert.rejects(updater.checkForUpdate(), /offline/)
  assert.equal(await updater.maybeCheckForUpdate(), null)
})
