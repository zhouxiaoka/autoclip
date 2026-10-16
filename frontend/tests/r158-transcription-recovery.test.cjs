// #418 rewrite: the one install-recovery controller (transcriptionRecovery.ts) and its one view
// (TranscriptionGatePrompt). Install, download, done, failed and timeout are distinct phases; every phase has an exit.
const { test, before, after } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { Window } = require('happy-dom')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')

const { act } = require('react')
// DOM is created per file in before(), never at module load (a top-level new Window() leaks into other files).
let window, createRoot
function setupDom() {
  if (window) return
  window = new Window({ url: 'http://localhost/' })
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  ;({ createRoot } = require('react-dom/client'))
}
function teardownDom() {
  if (!window) return
  window.happyDOM.abort?.(); window.close()
  for (const key of ['window', 'document', 'navigator', 'HTMLElement', 'IS_REACT_ACT_ENVIRONMENT']) delete globalThis[key]
  window = undefined
}
before(setupDom)
after(teardownDom)

const dir = path.resolve(__dirname, '../src/features/studio')
const recovery = loadTs(path.join(dir, 'transcriptionRecovery.ts'), {}, dir)
const Btn = ({ children, onClick, disabled }) => React.createElement('button', { type: 'button', onClick, disabled }, children)
const Prompt = loadTs(path.join(dir, 'TranscriptionGatePrompt.tsx'), { '../../i18n': { t: (s, v) => v ? s.replace(/\{\{(\w+)\}\}/g, (_, k) => v[k]) : s }, '../../ui': { Btn } }, dir).default

const check = (code, extra = {}) => ({ checks: { transcription: { ok: code === 'ok', code, repair: 'none', ...extra } } })

function fakeApi(script) {
  const log = []
  return {
    log,
    readiness: async () => script.report(),
    getRuntimeStatus: async () => script.runtime ? script.runtime() : { status: 'installing', progress: 0 },
    getModels: async () => script.models ? script.models() : [],
    installRuntime: async () => { log.push('runtime'); if (script.installFails) throw new Error('x') },
    downloadModel: async m => { log.push('model:' + m) },
  }
}

test('one-click install on a clean machine: runtime -> model download -> ready (#281, #280)', async () => {
  let stage = 'missing'
  const api = fakeApi({
    report: () => stage === 'missing' ? check('whisper_not_installed') : stage === 'installing' ? check('whisper_installing')
      : stage === 'model' ? check('whisper_model_missing', { model: 'base' }) : stage === 'downloading' ? check('whisper_model_downloading', { model: 'base' }) : check('ok'),
    runtime: () => ({ status: 'installing', progress: 40 }),
    models: () => [{ name: 'base', status: 'downloading', downloadProgress: 60 }],
  })
  const c = recovery.createRecoveryController(api)
  c.open('whisper_not_installed')
  assert.equal(c.state.phase, 'install_required')
  await c.install(); stage = 'installing'
  assert.deepEqual(api.log, ['runtime'])
  assert.equal((await c.poll()).phase, 'installing'); assert.equal(c.state.percent, 40)
  stage = 'model'
  assert.equal((await c.poll()).phase, 'downloading', 'the install goes on to the model by itself')
  assert.deepEqual(api.log, ['runtime', 'model:base'])
  stage = 'downloading'
  assert.equal((await c.poll()).percent, 60)
  stage = 'ok'
  assert.equal((await c.poll()).phase, 'ready')
})

test('a model that is merely missing (not after our install) asks first, then downloads on click', async () => {
  const api = fakeApi({ report: () => check('whisper_model_missing', { model: 'small' }) })
  const c = recovery.createRecoveryController(api)
  c.open('whisper_model_missing', 'small')
  assert.equal(c.state.phase, 'install_required')
  await c.install()
  assert.deepEqual(api.log, ['model:small']); assert.equal(c.state.phase, 'downloading')
})

test('failed install and failed download are their own phase; retry restarts the right step', async () => {
  const api = fakeApi({ report: () => check('whisper_installing'), runtime: () => ({ status: 'error' }) })
  const c = recovery.createRecoveryController(api)
  c.open('whisper_installing')
  assert.equal((await c.poll()).phase, 'failed')
  await c.retry(); assert.deepEqual(api.log, ['runtime'])
  const d = fakeApi({ report: () => check('whisper_model_downloading', { model: 'base' }), models: () => [{ name: 'base', status: 'error' }] })
  const e = recovery.createRecoveryController(d)
  e.open('whisper_model_downloading', 'base')
  assert.equal((await e.poll()).phase, 'failed')
  await e.retry(); assert.deepEqual(d.log, ['model:base'])
  const f = recovery.createRecoveryController(fakeApi({ report: () => check('whisper_not_installed'), installFails: true }))
  f.open('whisper_not_installed'); await f.install()
  assert.equal(f.state.phase, 'failed', 'a refused install request is a failure, not an endless wait')
})

test('no progress for stallMs is a timeout, distinct from failed', async () => {
  let now = 0
  const api = fakeApi({ report: () => check('whisper_model_downloading', { model: 'base' }), models: () => [{ name: 'base', status: 'downloading', downloadProgress: 5 }] })
  const c = recovery.createRecoveryController(api, { stallMs: 1000, now: () => now })
  c.open('whisper_model_downloading', 'base')
  await c.poll(); now = 500; await c.poll()
  assert.equal(c.state.phase, 'downloading')
  now = 1600; await c.poll()
  assert.equal(c.state.phase, 'timeout')
})

test('waiting codes never open as "not installed"; source codes never open recovery', () => {
  assert.equal(recovery.phaseOfCode('whisper_installing'), 'installing')
  assert.equal(recovery.phaseOfCode('whisper_model_downloading'), 'downloading')
  assert.equal(recovery.phaseOfCode('whisper_install_failed'), 'failed')
  for (const code of ['source_unreadable', 'source_too_short', 'source_no_audio', 'cloud_not_configured', undefined]) assert.equal(recovery.isRecoveryCode(code), false)
})

test('#232: a wait that reaches ready continues by itself exactly once; failed / timeout / open(ready) never do', async () => {
  let report = check('whisper_model_downloading', { model: 'base' })
  let readyCalls = 0
  const api = fakeApi({ report: () => report, models: () => [{ name: 'base', status: 'downloading', downloadProgress: 10 }] })
  const c = recovery.createRecoveryController(api, { onReady: () => readyCalls++ })
  c.open('whisper_model_downloading', 'base')
  await c.poll(); assert.equal(readyCalls, 0)
  report = check('ok')
  await c.poll(); assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
  await c.poll(); assert.equal(readyCalls, 1, 'once')
  const failing = recovery.createRecoveryController(fakeApi({ report: () => check('whisper_installing'), runtime: () => ({ status: 'error' }) }), { onReady: () => readyCalls++ })
  failing.open('whisper_installing'); await failing.poll()
  assert.equal(failing.state.phase, 'failed'); assert.equal(readyCalls, 1)
})

test('#350: the install request goes out before the wait; a poll that still sees not_installed keeps waiting', async () => {
  const order = []
  let report = check('whisper_not_installed')
  const api = fakeApi({ report: () => report, runtime: () => ({ status: 'installing', progress: 5 }) })
  const sendInstall = api.installRuntime
  api.installRuntime = async () => { order.push('request'); await sendInstall() }
  const c = recovery.createRecoveryController(api)
  c.subscribe(s => order.push(s.phase))
  c.open('whisper_not_installed')
  await c.install()
  assert.deepEqual(order, ['install_required', 'request', 'installing'], 'request first, then the waiting phase')
  assert.equal((await c.poll()).phase, 'installing', 'stale not_installed right after the request is still installing')
  report = check('whisper_installing')
  assert.equal((await c.poll()).phase, 'installing')
  report = check('ok')
  assert.equal((await c.poll()).phase, 'ready')
})

test('#349: onReady hands over the fresh report; every report read reaches onReport', async () => {
  let report = check('whisper_model_downloading', { model: 'base' })
  const seen = []; let handed
  const c = recovery.createRecoveryController(fakeApi({ report: () => report, models: () => [] }), { onReport: r => seen.push(r.checks.transcription.code), onReady: r => { handed = r } })
  c.open('whisper_model_downloading', 'base')
  await c.poll(); report = check('ok'); await c.poll()
  assert.deepEqual(seen, ['whisper_model_downloading', 'ok'])
  assert.equal(handed.checks.transcription.code, 'ok')
})

function render(props) {
  const host = document.createElement('div'); document.body.appendChild(host)
  const root = createRoot(host)
  act(() => root.render(React.createElement(Prompt, props)))
  const button = label => [...host.querySelectorAll('button')].find(b => b.textContent === label)
  return { host, button, unmount: () => act(() => root.unmount()) }
}

test('the view: each phase has its exit (install / cloud, progress + settings, continue, retry + settings)', () => {
  const log = []
  const base = { busy: false, onInstall: () => log.push('install'), onRetry: () => log.push('retry'), onContinue: () => log.push('continue'), navigate: to => log.push(to) }
  let v = render({ ...base, state: { phase: 'install_required', percent: null } })
  act(() => v.button('一键安装').click()); act(() => v.button('改用云端转写').click()); v.unmount()
  v = render({ ...base, state: { phase: 'downloading', percent: 42 } })
  assert.equal(v.host.querySelector('[role=progressbar]').getAttribute('aria-valuenow'), '42')
  assert.match(v.host.textContent, /正在下载转写模型/)
  act(() => v.button('打开转写设置').click()); v.unmount()
  v = render({ ...base, state: { phase: 'ready', percent: 100 } })
  act(() => v.button('继续导入').click()); v.unmount()
  for (const phase of ['failed', 'timeout']) { v = render({ ...base, state: { phase, percent: null } }); act(() => v.button('重试').click()); v.unmount() }
  v = render({ ...base, state: { phase: 'idle', percent: null } }); assert.equal(v.host.innerHTML, ''); v.unmount()
  assert.deepEqual(log, ['install', '/settings?section=speech&provider=cloud', '/settings?section=speech', 'continue', 'retry', 'retry'])
})

test('install prompt copy exists in all 8 languages', () => {
  const keys = ['需要先安装本地转写', '视频没有字幕，所选的本地 Whisper 还没装好。安装完成后再开始，或改用云端转写。', '一键安装', '改用云端转写',
    '等待安装完成', '本地 Whisper 正在安装，装好后再开始。', '正在下载转写模型，下载完成后即可继续。', '本地转写已就绪，可以继续导入。', '继续导入',
    '安装或模型下载失败，可以重试，或到转写设置里查看。', '安装长时间没有进展，可以重试，或到转写设置里查看。', '打开转写设置', '已完成 {{percent}}%']
  for (const lang of ['en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru', 'zh']) {
    const data = JSON.parse(fs.readFileSync(path.resolve(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    for (const key of keys) assert.ok(typeof data[key] === 'string' && data[key].length > 0, `${lang}: ${key}`)
  }
})

test('#372: runtime in, model download request 500 -> failed (not downloading); polls never resend; retry sends once', async () => {
  let stage = 'installing'
  const log = []
  let fail = true
  const api = { readiness: async () => stage === 'installing' ? check('whisper_installing') : check('whisper_model_missing', { model: 'base' }),
    getRuntimeStatus: async () => ({ status: 'installing', progress: 50 }), getModels: async () => [],
    installRuntime: async () => { log.push('runtime') }, downloadModel: async m => { log.push('model:' + m); if (fail) throw new Error('500') } }
  const c = recovery.createRecoveryController(api)
  c.open('whisper_not_installed'); await c.install()
  assert.equal(c.state.phase, 'installing')
  stage = 'model'
  await c.poll()
  assert.equal(c.state.phase, 'failed', 'a refused download request is failed, never downloading')
  await c.poll(); await c.poll()
  assert.deepEqual(log, ['runtime', 'model:base'], 'no resend by polling')
  fail = false
  await c.retry()
  assert.equal(c.state.phase, 'downloading')
  await c.poll(); await c.poll()
  assert.deepEqual(log, ['runtime', 'model:base', 'model:base'], 'accepted download is not resent while readiness lags')
})

test('#372 offline: install request network error -> failed -> retry works', async () => {
  let online = false
  const log = []
  const api = { readiness: async () => { if (!online) throw new TypeError('Failed to fetch'); return check('whisper_installing') },
    getRuntimeStatus: async () => ({ status: 'installing', progress: 5 }), getModels: async () => [],
    installRuntime: async () => { log.push('runtime'); if (!online) throw new TypeError('Network Error') }, downloadModel: async () => { throw new TypeError('Network Error') } }
  const c = recovery.createRecoveryController(api)
  c.open('whisper_not_installed'); await c.install()
  assert.equal(c.state.phase, 'failed')
  online = true
  await c.retry()
  assert.equal(c.state.phase, 'installing')
})

test('#372 offline: backend unreachable while waiting -> failed after OFFLINE_POLLS, then retryable', async () => {
  let online = true
  const api = { readiness: async () => { if (!online) throw new TypeError('Failed to fetch'); return check('whisper_installing') },
    getRuntimeStatus: async () => ({ status: 'installing', progress: 5 }), getModels: async () => [],
    installRuntime: async () => {}, downloadModel: async () => {} }
  const c = recovery.createRecoveryController(api)
  c.open('whisper_not_installed'); await c.install()
  online = false
  for (let i = 0; i < recovery.OFFLINE_POLLS - 1; i++) { await c.poll(); assert.equal(c.state.phase, 'installing') }
  await c.poll()
  assert.equal(c.state.phase, 'failed')
  online = true
  await c.retry(); await c.poll()
  assert.equal(c.state.phase, 'installing')
})
