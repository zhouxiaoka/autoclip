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

// #403: only network errors count as unreachable, judged by time (OFFLINE_MS of continuous unreachability), polling
// goes on meanwhile, and an offline failure keeps polling slowly and continues by itself when the backend is back.
function clockedApi() {
  const clock = { t: 0, down: false, error500: false, stage: 'installing', reads: 0 }
  const netErr = () => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK', response: undefined })
  const api = {
    readiness: async () => {
      clock.reads++
      if (clock.down) throw netErr()
      if (clock.error500) throw Object.assign(new Error('Request failed with status code 500'), { response: { status: 500 } })
      return clock.stage === 'ready' ? check('ok') : check('whisper_installing')
    },
    getRuntimeStatus: async () => ({ status: 'installing', progress: Math.floor(clock.t / 1000) }), getModels: async () => [],
    installRuntime: async () => {}, downloadModel: async () => {},
  }
  return { clock, api }
}
async function startWait(api, clock, extra = {}) {
  const c = recovery.createRecoveryController(api, { now: () => clock.t, ...extra })
  c.open('whisper_not_installed'); await c.install()
  assert.equal(c.state.phase, 'installing')
  return c
}
// poll every 2s (the page's cadence) from clock.t to `until`, recording the phases seen
async function pollUntil(c, clock, until, step = 2000) {
  const phases = []
  while (clock.t < until) { clock.t += step; await c.poll(); phases.push(c.state.phase) }
  return phases
}

test('#403 a 7s backend outage is not a failure: polling goes on and the wait continues by itself', async () => {
  const { clock, api } = clockedApi()
  let readyCalls = 0
  const c = await startWait(api, clock, { onReady: () => { readyCalls++ } })
  clock.down = true
  const during = await pollUntil(c, clock, 7000)
  assert.ok(!during.includes('failed'), `no failed during a 7s outage: ${during}`)
  assert.equal(c.state.unreachable, true, 'the page says it is retrying')
  assert.ok(clock.reads >= 4, 'polling did not stop while unreachable')
  clock.down = false; clock.stage = 'ready'
  await pollUntil(c, clock, 9000)
  assert.equal(c.state.phase, 'ready')
  assert.equal(readyCalls, 1, 'continued by itself, once')
})

test('#403 a blip resets the unreachable streak (20s down, one answer, 20s down -> still waiting)', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.down = true
  await pollUntil(c, clock, 20000)
  clock.down = false
  await pollUntil(c, clock, 22000)
  assert.equal(c.state.unreachable, undefined, 'a reachable answer clears the unreachable flag')
  clock.down = true
  const phases = await pollUntil(c, clock, 42000)
  assert.ok(!phases.includes('failed'), `40s down in total but never 30s in a row: ${phases}`)
  assert.equal(c.state.phase, 'installing')
})

test('#403 threshold: 28s unreachable is still waiting, 30s unreachable is failed (a smaller threshold fails this)', async () => {
  assert.equal(recovery.OFFLINE_MS, 30000)
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.down = true
  clock.t += 1000; await c.poll()  // streak starts at t=1s
  const early = await pollUntil(c, clock, 29000) // up to 28s of streak
  assert.ok(!early.includes('failed'), `not failed before 30s: ${early}`)
  clock.t = 31000; await c.poll()  // 30s of streak
  assert.equal(c.state.phase, 'failed')
  assert.equal(c.state.offline, true)
})

test('#403 a readiness 500 is a reachable backend, never counted as unreachable', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.error500 = true
  const phases = await pollUntil(c, clock, 60000)
  assert.ok(!phases.includes('failed'), `500s for 60s do not fail as offline: ${phases}`)
  assert.equal(c.state.unreachable, undefined)
  assert.equal(recovery.isNetworkError({ response: { status: 500 } }), false)
  assert.equal(recovery.isNetworkError(new TypeError('Failed to fetch')), true)
  assert.equal(recovery.isNetworkError({ code: 'ECONNABORTED', response: undefined }), true)
})

test('#403 after an offline failure the slow polls continue the wait by themselves when the backend is back', async () => {
  const { clock, api } = clockedApi()
  let readyCalls = 0
  const c = await startWait(api, clock, { onReady: () => { readyCalls++ } })
  clock.down = true
  await pollUntil(c, clock, 35000)
  assert.equal(c.state.phase, 'failed'); assert.equal(c.state.offline, true)
  await pollUntil(c, clock, 45000, 10000)
  assert.equal(c.state.phase, 'failed', 'still offline -> still failed')
  clock.down = false
  await pollUntil(c, clock, 55000, 10000)
  assert.equal(c.state.phase, 'installing', 'back: the interrupted wait resumes')
  assert.equal(c.state.offline, undefined)
  clock.stage = 'ready'
  await pollUntil(c, clock, 57000)
  assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
  // a plain (non-offline) failure is not polled
  const before = clock.reads
  const d = recovery.createRecoveryController({ ...api, installRuntime: async () => { throw new Error('x') } }, { now: () => clock.t })
  d.open('whisper_not_installed'); await d.install()
  const reads = clock.reads
  await d.poll()
  assert.equal(d.state.phase, 'failed'); assert.equal(clock.reads, reads, 'install failure stays failed until retry')
  assert.ok(reads > before)
})

test('#403 hook: an offline failure keeps polling at the low frequency and continues by itself', async () => {
  // the hook's poll loop needs real timers, which loadTs's sandbox does not expose: transpile it here with them
  const ts = require('typescript'); const vm = require('node:vm')
  const { outputText } = ts.transpileModule(fs.readFileSync(path.join(dir, 'useTranscriptionRecovery.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } })
  const hook = {}
  vm.runInNewContext(outputText, { exports: hook, setTimeout, clearTimeout, require: id => id === './transcriptionRecovery' ? recovery : require(id) })
  const { clock, api } = clockedApi()
  clock.down = true
  let controller, last
  function Probe() { const [state, c] = hook.useTranscriptionRecovery(api, { now: () => clock.t, pollMs: 5, offlinePollMs: 20 }); controller = c; last = state; return null }
  const host = document.createElement('div'); const root = createRoot(host)
  await act(async () => { root.render(React.createElement(Probe)) })
  try {
  await act(async () => { controller.open('whisper_not_installed'); await controller.install() })
  const wait = ms => act(async () => { await new Promise(r => setTimeout(r, ms)) })
  await wait(20); clock.t = 31000; await wait(30)
  assert.equal(last.phase, 'failed'); assert.equal(last.offline, true)
  const reads = clock.reads
  await wait(80)
  assert.ok(clock.reads > reads, 'slow polls go on after an offline failure')
  clock.down = false; clock.stage = 'ready'
  await wait(80)
  assert.equal(last.phase, 'ready')
  } finally { await act(async () => root.unmount()) }  // a failing assertion must not leave the poll timers alive
})
test('#404 prompt: background installing stays hidden, background failed / timeout / offline are shown with retry', async () => {
  const host = document.createElement('div'); const root = createRoot(host)
  const show = async state => { await act(async () => { root.render(React.createElement(Prompt, { state, busy: false, onInstall() {}, onRetry() {}, onContinue() {}, navigate() {} })) }); return host }
  assert.equal((await show({ phase: 'installing', percent: 10, background: true })).querySelector('[role=alertdialog]'), null)
  for (const state of [{ phase: 'failed', percent: null, background: true }, { phase: 'timeout', percent: null, background: true }, { phase: 'failed', percent: null, background: true, offline: true }]) {
    const view = await show(state)
    assert.ok(view.querySelector('[role=alertdialog]'), JSON.stringify(state))
    assert.ok([...view.querySelectorAll('button')].some(b => b.textContent === '重试'), JSON.stringify(state))
  }
  assert.match((await show({ phase: 'failed', percent: null, offline: true })).textContent, /后端恢复后会自动继续/)
  assert.match((await show({ phase: 'installing', percent: 10, unreachable: true })).textContent, /暂时连不上本地后端，正在重试/)
  await act(async () => root.unmount())
})

// #418 R27b (Dong): only the readiness request gets a 5s deadline; a timeout counts toward the 30s window like a
// network error; a 500 still does not. A paused backend (accepts, never answers) is simulated by a readiness that
// never settles; the injected timer advances the clock by the waited time, as a real 5s wait would.
function hungApi() {
  const { clock, api } = clockedApi()
  clock.hung = false
  const inner = api.readiness
  api.readiness = () => clock.hung ? new Promise(() => {}) : inner()
  const timers = { set: 0 }
  const setTimer = (fn, ms) => { timers.set++; if (clock.hung) { clock.t += ms; queueMicrotask(fn) } return timers.set }
  return { clock, api, timers, opts: { setTimer, clearTimer: () => {} } }
}
function withDeadline(p, ms = 1000) {
  return Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('poll hung: readiness had no deadline')), ms))])
}

test('#418 R27b readiness deadline is 5s and a timeout is unreachable (no response)', () => {
  assert.equal(recovery.READINESS_TIMEOUT_MS, 5000)
  assert.equal(recovery.isNetworkError(recovery.readinessTimeoutError()), true)
})

test('#418 R27b a 7s pause (hung readiness) is not a failure and continues by itself', async () => {
  const { clock, api, opts } = hungApi()
  let readyCalls = 0
  const c = await startWait(api, clock, { ...opts, onReady: () => { readyCalls++ } })
  clock.hung = true
  const t0 = clock.t
  while (clock.t - t0 < 7000) { clock.t += 2000; await withDeadline(c.poll()); assert.notEqual(c.state.phase, 'failed') }
  assert.equal(c.state.unreachable, true, 'the page says it is retrying')
  clock.hung = false; clock.stage = 'ready'
  clock.t += 2000; await withDeadline(c.poll())
  assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
})

test('#418 R27b timeouts adding up to 30s fail the wait, then it continues by itself after recovery', async () => {
  const { clock, api, opts } = hungApi()
  let readyCalls = 0
  const c = await startWait(api, clock, { ...opts, onReady: () => { readyCalls++ } })
  clock.hung = true
  const t0 = clock.t
  const phases = []
  while (clock.t - t0 < 40000) { clock.t += 2000; await withDeadline(c.poll()); phases.push([clock.t - t0, c.state.phase]) }
  const firstFail = phases.find(([, p]) => p === 'failed')
  assert.ok(firstFail, `35s+ of timeouts must fail: ${JSON.stringify(phases)}`)
  assert.ok(firstFail[0] >= 30000, `not failed before 30s of timeouts: ${JSON.stringify(phases)}`)
  // pause starts at 0, polls go out at 2, 9, 16, 23, 30 (5s each): the streak counts from the first send (2s), so the
  // poll sent at 30 fails at 35 - a 35s pause is failed before it resumes (counting from the deadline would be 42).
  assert.equal(firstFail[0], 35000, `failed by the end of a 35s pause: ${JSON.stringify(phases)}`)
  assert.equal(c.state.offline, true)
  clock.hung = false
  clock.t += 10000; await withDeadline(c.poll())
  assert.equal(c.state.phase, 'installing', 'back: the interrupted wait resumes without a click')
  clock.stage = 'ready'
  clock.t += 2000; await withDeadline(c.poll())
  assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
})

test('#418 R27b a 500 is still reachable with the deadline in place; the deadline is cleared on an answer', async () => {
  const { clock, api, opts } = hungApi()
  let cleared = 0
  const c = await startWait(api, clock, { ...opts, clearTimer: () => { cleared++ } })
  const before = cleared
  await pollUntil(c, clock, 6000)
  assert.equal(cleared - before, 3, 'each answered (200) readiness clears its deadline')
  clock.error500 = true
  const phases = await pollUntil(c, clock, 60000)
  assert.ok(!phases.includes('failed'), `500s for 60s are not offline: ${phases}`)
  assert.equal(c.state.unreachable, undefined)
  assert.ok(cleared >= phases.length, 'an answered readiness clears its deadline')
})

test('#418 R27b only readiness gets the deadline (install/model/runtime requests are not raced)', () => {
  const src = fs.readFileSync(path.join(dir, 'transcriptionRecovery.ts'), 'utf8')
  assert.equal((src.match(/READINESS_TIMEOUT_MS\)/g) || []).length, 1)
  assert.equal((src.match(/api\.readiness\(\)/g) || []).length, 1, 'readiness is called only inside the deadline')
})

// ---- #418 R27b I426: rounds, one poll in flight, dispose on unmount, explicit link enum ----
function deferredApi() {
  const st = { live: 0, max: 0, calls: 0, pending: [], reply: () => check('whisper_installing') }
  const api = {
    readiness: () => {
      st.calls++; st.live++; st.max = Math.max(st.max, st.live)
      return new Promise(res => st.pending.push(v => { st.live--; res(v) }))
    },
    getRuntimeStatus: async () => ({ status: 'installing', progress: 10 }), getModels: async () => [],
    installRuntime: async () => {}, downloadModel: async () => {},
  }
  const answer = async (v, i = 0) => { const fn = st.pending.splice(i, 1)[0]; fn(v); for (let k = 0; k < 20; k++) await Promise.resolve() }
  return { st, api, answer }
}
async function waitingController(extra = {}) {
  const d = deferredApi()
  const c = recovery.createRecoveryController(d.api, { now: () => 0, ...extra })
  c.open('whisper_not_installed')
  const p = c.install(); await d.answer(check('whisper_not_installed')); await p
  assert.equal(c.state.phase, 'installing')
  return { c, ...d }
}

test('I426 two polls at once share one readiness request (max concurrency 1)', async () => {
  const { c, st, answer } = await waitingController()
  const a = c.poll(); const b = c.poll()
  assert.equal(st.live, 1); assert.equal(a, b)
  await answer(check('whisper_installing')); await a
  assert.equal(st.max, 1)
})

test('I426 retry while a poll is in flight: the stale ready is dropped, installing is not overwritten, no onReady', async () => {
  let readyCalls = 0
  const { c, st, answer } = await waitingController({ onReady: () => { readyCalls++ } })
  const stale = c.poll()
  const retry = c.retry()
  assert.equal(st.live, 2, 'the retry read and the stale poll')
  await answer(check('whisper_not_installed'), 1)  // the retry's own read answers first -> installing
  await retry
  assert.equal(c.state.phase, 'installing')
  await answer(check('ok'), 0)  // then the stale poll's ready arrives
  await Promise.all([retry, stale])
  assert.notEqual(c.state.phase, 'ready', 'a stale ready must not overwrite the new round')
  assert.equal(readyCalls, 0)
  assert.equal(st.live, 0)
})

test('I426 close and reopen while a poll is in flight: the old answer writes nothing', async () => {
  let readyCalls = 0
  const { c, answer } = await waitingController({ onReady: () => { readyCalls++ } })
  const stale = c.poll()
  c.close(); c.open('whisper_model_missing', 'base')
  await answer(check('ok')); await stale
  assert.equal(c.state.phase, 'install_required'); assert.equal(readyCalls, 0)
})

test('I426 dispose while a poll is in flight: no state change and no onReady afterwards; later polls do nothing', async () => {
  let readyCalls = 0, reports = 0; const seen = []
  const { c, st, answer } = await waitingController({ onReady: () => { readyCalls++ }, onReport: () => { reports++ } })
  const reportsBefore = reports
  c.subscribe(s => seen.push(s.phase))
  const stale = c.poll()
  c.dispose()
  await answer(check('ok')); await stale
  assert.equal(readyCalls, 0); assert.deepEqual(seen, []); assert.equal(c.state.phase, 'installing')
  assert.equal(reports, reportsBefore, 'a dropped answer does not reach onReport either')
  const calls = st.calls
  await c.poll(); assert.equal(st.calls, calls, 'a disposed controller sends no readiness')
})

test('I426 link enum: installing -> unreachable(startedAt) -> failed_recoverable -> installing -> ready; the timer exists only in unreachable', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  const L = x => JSON.parse(JSON.stringify(x.link))
  assert.equal(c.link.kind, 'installing')
  clock.down = true
  clock.t = 2000; await c.poll()
  assert.deepEqual(L(c), { kind: 'unreachable', startedAt: 2000 })
  clock.t = 4000; await c.poll()
  assert.deepEqual(L(c), { kind: 'unreachable', startedAt: 2000 }, 'the streak keeps its start')
  clock.t = 32000; await c.poll()
  assert.deepEqual(L(c), { kind: 'failed_recoverable', resume: 'installing' })
  assert.equal(c.state.offline, true); assert.equal(c.state.phase, 'failed')
  clock.down = false; clock.t = 42000; await c.poll()
  assert.deepEqual(L(c), { kind: 'installing' }); assert.equal(c.state.offline, undefined); assert.equal(c.state.unreachable, undefined)
  clock.stage = 'ready'; clock.t = 44000; await c.poll()
  assert.deepEqual(L(c), { kind: 'ready' })
  assert.ok(!Object.keys(c.link).includes('startedAt'))
})

// ---- I428: Dong's 5 surviving mutations ----
test('I428 a 500 between outages resets the streak (20s down, one 500, 20s down -> still waiting)', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.down = true; await pollUntil(c, clock, 20000)
  clock.down = false; clock.error500 = true; await pollUntil(c, clock, 22000)
  assert.equal(c.link.kind, 'installing', 'a 500 is an answer: out of unreachable')
  clock.error500 = false; clock.down = true
  const phases = await pollUntil(c, clock, 42000)
  assert.ok(!phases.includes('failed'), `never 30s unanswered in a row: ${phases}`)
})

test('I428 non-object errors (string, undefined) count as unreachable', async () => {
  for (const thrown of ['boom', undefined, 42]) {
    const { clock, api } = clockedApi()
    const c = await startWait(api, clock)
    api.readiness = async () => { throw thrown }
    await pollUntil(c, clock, 32000)
    assert.equal(c.state.phase, 'failed', String(thrown)); assert.equal(c.state.offline, true, String(thrown))
  }
})

test('I428 retry restarts the unreachable timer (25s down, retry, 10s down -> still waiting)', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.down = true; await pollUntil(c, clock, 25000)
  assert.equal(c.link.kind, 'unreachable')
  await c.retry()
  assert.equal(c.state.phase, 'installing'); assert.equal(c.link.kind, 'installing', 'retry leaves unreachable')
  const phases = await pollUntil(c, clock, 35000)
  assert.ok(!phases.includes('failed'), `the old streak is not inherited: ${phases}`)
})

function loadHook(timers) {
  const ts = require('typescript'); const vm = require('node:vm')
  const { outputText } = ts.transpileModule(fs.readFileSync(path.join(dir, 'useTranscriptionRecovery.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } })
  const hook = {}
  const st = (fn, ms) => { const h = setTimeout(() => { timers.delete(h); fn() }, ms); timers.add(h); return h }
  const ct = h => { timers.delete(h); clearTimeout(h) }
  vm.runInNewContext(outputText, { exports: hook, setTimeout: st, clearTimeout: ct, require: id => id === './transcriptionRecovery' ? recovery : require(id) })
  return hook
}

test('I428 hook unmount clears its poll timer (no timer left alive)', async () => {
  const timers = new Set(); const hook = loadHook(timers)
  const { clock, api } = clockedApi()
  let controller
  function Probe() { const [, c] = hook.useTranscriptionRecovery(api, { now: () => clock.t, pollMs: 50 }); controller = c; return null }
  const root = createRoot(document.createElement('div'))
  await act(async () => { root.render(React.createElement(Probe)) })
  await act(async () => { controller.open('whisper_not_installed'); await controller.install() })
  await act(async () => { await new Promise(r => setTimeout(r, 20)) })
  assert.ok(timers.size >= 1, 'a poll timer is scheduled while waiting')
  await act(async () => root.unmount())
  assert.equal(timers.size, 0, 'unmount clears the timer')
})

test('I428/I426 hook unmount with a poll in flight: nothing rescheduled, no auto-continue afterwards', async () => {
  const timers = new Set(); const hook = loadHook(timers)
  const d = deferredApi()
  let readyCalls = 0, controller
  function Probe() { const [, c] = hook.useTranscriptionRecovery(d.api, { now: () => 0, pollMs: 5, onReady: () => { readyCalls++ } }); controller = c; return null }
  const root = createRoot(document.createElement('div'))
  await act(async () => { root.render(React.createElement(Probe)) })
  await act(async () => { controller.open('whisper_not_installed'); const p = controller.install(); await d.answer(check('whisper_not_installed')); await p })
  await act(async () => { await new Promise(r => setTimeout(r, 5)) })
  assert.equal(d.st.live, 1, 'the first poll is in flight')
  await act(async () => root.unmount())
  await act(async () => { await d.answer(check('ok')); await new Promise(r => setTimeout(r, 20)) })
  assert.equal(readyCalls, 0, 'no auto-continue after unmount')
  assert.equal(timers.size, 0, 'no timer rescheduled after unmount')
  assert.equal(d.st.max, 1)
})

test('I426 hook: leaving offline and coming back continues once, with one readiness in flight at a time', async () => {
  const timers = new Set(); const hook = loadHook(timers)
  const { clock, api } = clockedApi()
  let live = 0, max = 0
  const inner = api.readiness
  api.readiness = async () => { live++; max = Math.max(max, live); try { await new Promise(r => setTimeout(r, 3)); return await inner() } finally { live-- } }
  let readyCalls = 0, controller, last
  clock.down = true
  function Probe() { const [s, c] = hook.useTranscriptionRecovery(api, { now: () => clock.t, pollMs: 5, offlinePollMs: 10, onReady: () => { readyCalls++ } }); controller = c; last = s; return null }
  const root = createRoot(document.createElement('div'))
  await act(async () => { root.render(React.createElement(Probe)) })
  try {
    await act(async () => { controller.open('whisper_not_installed'); await controller.install() })
    const wait = ms => act(async () => { await new Promise(r => setTimeout(r, ms)) })
    await wait(20); clock.t = 40000; await wait(40)
    assert.equal(last.phase, 'failed'); assert.equal(last.offline, true)
    clock.down = false; clock.stage = 'ready'
    await wait(120)
    assert.equal(last.phase, 'ready'); assert.equal(readyCalls, 1, 'continued exactly once'); assert.equal(max, 1)
  } finally { await act(async () => root.unmount()) }
})
