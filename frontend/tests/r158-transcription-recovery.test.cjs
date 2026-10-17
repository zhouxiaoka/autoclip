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

// ---- #418 R27b I426: rounds, one poll in flight, dispose on unmount, round signal ----
function deferredApi() {
  const st = { live: 0, max: 0, calls: 0, pending: [], reply: () => check('whisper_installing') }
  const api = {
    readiness: signal => {
      if (signal) signal.addEventListener('abort', () => { st.aborted = (st.aborted || 0) + 1 })
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


// ---- I428: Dong's surviving mutations (ported to the derived view fields) ----
// ---- I428: Dong's 5 surviving mutations ----
test('I428 a 500 between outages resets the streak (20s down, one 500, 20s down -> still waiting)', async () => {
  const { clock, api } = clockedApi()
  const c = await startWait(api, clock)
  clock.down = true; await pollUntil(c, clock, 20000)
  clock.down = false; clock.error500 = true; await pollUntil(c, clock, 22000)
  assert.equal(c.state.unreachable, undefined, 'a 500 is an answer: out of unreachable')
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
  assert.equal(c.state.unreachable, true)
  await c.retry()
  assert.equal(c.state.phase, 'installing'); assert.equal(c.state.unreachable, undefined, 'retry leaves unreachable')
  const phases = await pollUntil(c, clock, 35000)
  assert.ok(!phases.includes('failed'), `the old streak is not inherited: ${phases}`)
})

// ---- #418 R27c I486: one fake clock (monotonic `now` + a timer scheduler) and one fake request layer ----
// The scheduler fires due timers in time order, setting clock.t to each due time; `wake(ms)` is a machine sleep: the
// clock jumps and every overdue timer fires late, at the wake time. Hook tests run each timer inside act().
function fakeClock(start = 0) {
  const timers = []; let ids = 0
  const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve() }
  const fire = async fn => { if (clock.act) { await act(async () => { fn() }); await act(async () => {}) } else { fn(); await flush() } }
  const clock = {
    t: start, act: false,
    setTimeout: (fn, ms) => { const h = ++ids; timers.push({ h, fn, at: clock.t + (ms || 0) }); return h },
    clearTimeout: h => { const i = timers.findIndex(x => x.h === h); if (i >= 0) timers.splice(i, 1) },
    pending: () => timers.length,
    async advance(ms) {
      const end = clock.t + ms
      for (;;) {
        if (clock.act) await act(async () => { await flush() }); else await flush()
        timers.sort((a, b) => a.at - b.at || a.h - b.h)
        const next = timers[0]
        if (!next || next.at > end) break
        timers.shift(); clock.t = Math.max(clock.t, next.at); await fire(next.fn)
      }
      clock.t = end
      if (clock.act) await act(async () => { await flush() }); else await flush()
    },
    async wake(ms) { clock.t += ms; await clock.advance(0) },
  }
  return clock
}
const netErr = () => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK', response: undefined })
const err500 = () => Object.assign(new Error('Request failed with status code 500'), { response: { status: 500 } })
/** The request layer as studioApi.readinessProbe behaves: one request, axios' own 5s timeout (ECONNABORTED, no
 * response), cancelled by the round's signal. Records calls, requests in flight and cancellations. */
function fakeTransport(clock, extra = {}) {
  const st = { calls: 0, live: 0, max: 0, aborted: 0, timeouts: 0, mode: 'ok', delay: 0, stage: 'installing', progress: 10, log: [] }
  const api = {
    readiness: signal => {
      st.calls++; st.live++; st.max = Math.max(st.max, st.live)
      return new Promise((resolve, reject) => {
        let done = false, answerTimer
        const end = (fn, v) => { if (done) return; done = true; st.live--; clock.clearTimeout(deadline); clock.clearTimeout(answerTimer); fn(v) }
        if (signal) signal.addEventListener('abort', () => { if (!done) st.aborted++; end(reject, Object.assign(new Error('canceled'), { code: 'ERR_CANCELED' })) })
        const deadline = clock.setTimeout(() => { st.timeouts++; end(reject, Object.assign(new Error('timeout of 5000ms exceeded'), { code: 'ECONNABORTED' })) }, 5000)
        const mode = st.mode
        const answer = () => mode === 'down' ? end(reject, netErr()) : mode === '500' ? end(reject, err500())
          : end(resolve, st.stage === 'ready' ? check('ok') : st.stage === 'downloading' ? check('whisper_model_downloading', { model: 'base' }) : check('whisper_installing'))
        if (mode === 'hang') return
        if (st.delay) answerTimer = clock.setTimeout(answer, st.delay); else queueMicrotask(answer)
      })
    },
    getRuntimeStatus: async () => ({ status: 'installing', progress: st.progress }),
    getModels: async () => [{ name: 'base', status: 'downloading', downloadProgress: st.progress }],
    installRuntime: async () => { st.log.push('runtime') }, downloadModel: async m => { st.log.push('model:' + m) },
    ...extra,
  }
  return { st, api }
}
/** The page's cadence without React: poll, let the clock run until it settles, wait `step`, repeat until `until`. */
async function drive(c, clock, until, step = 2000) {
  const seen = []
  while (clock.t < until) {
    await clock.advance(step)
    let settled = false
    const p = c.poll().then(() => { settled = true })
    for (let i = 0; i < 200 && !settled; i++) await clock.advance(100)
    await p
    seen.push([clock.t, c.state.phase])
  }
  return seen
}
async function waitingOn(clock, t, extra = {}) {
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t, ...extra })
  c.open('whisper_not_installed'); await c.install()
  assert.equal(c.state.phase, 'installing')
  return c
}

test('R27c wiring (source): one probe call site, no timer race in the controller; both pages pass the round signal through probeConfig', () => {
  // The 5s timeout itself is asserted by behaviour ('R28 readiness timeout 5s (behaviour, fake timers)').
  const src = fs.readFileSync(path.join(dir, 'transcriptionRecovery.ts'), 'utf8')
  assert.equal((src.match(/api\.readiness\(/g) || []).length, 1, 'one probe call site')
  assert.doesNotMatch(src, /setTimer|clearTimer|setTimeout|Promise\.race/, 'no timer race in the controller: axios times the probe out and aborts it')
  for (const page of ['CreativeImport.tsx', 'PlanSummary.tsx']) {
    const src = fs.readFileSync(path.join(dir, page), 'utf8')
    assert.match(src, /readiness: ?signal ?=> ?studioApi\.readinessProbe\(signal\)/, page)
    assert.match(src, /getRuntimeStatus: ?signal ?=> ?speechApi\.getRuntimeStatus\(probeConfig\(signal\)\)/, `I513 ${page}`)
    assert.match(src, /getModels: ?signal ?=> ?speechApi\.getModels\(probeConfig\(signal\)\)/, `I513 ${page}`)
  }
  assert.match(fs.readFileSync(path.join(dir, 'useTranscriptionRecovery.ts'), 'utf8'), /options\.pollMs \?\? POLL_MS/, 'I517')
})

test('R27c state is phase + offlineSince + ownsInstall: no link enum, no round counter, no flags', () => {
  const src = fs.readFileSync(path.join(dir, 'transcriptionRecovery.ts'), 'utf8')
  for (const gone of ['RecoveryLink', 'modelRequested', 'unreachableSince', 'inflight', 'let round', 'let disposed', 'let installing', 'readinessTimeoutError', 'r !== round'])
    assert.ok(!src.includes(gone), `removed: ${gone}`)
  const c = recovery.createRecoveryController(fakeTransport(fakeClock()).api)
  assert.equal(c.link, undefined)
})

test('R27c I480 S2: 6 polls on a hung backend keep one request in flight; close / retry / dispose cancel it', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = 'hang'
  const polls = []; for (let i = 0; i < 6; i++) { polls.push(c.poll()); await clock.advance(500) }
  assert.equal(t.st.live, 1, 'one readiness in flight'); assert.equal(t.st.max, 1)
  const r1 = c.retry(); await clock.advance(0)  // aborts the hung poll; the retry's own probe hangs too
  assert.equal(t.st.aborted, 1, 'retry cancels the request in flight')
  const r2 = c.retry(); await clock.advance(0)
  assert.equal(t.st.aborted, 2, 'a second retry cancels the first one\'s probe')
  c.close(); await Promise.all([r1, r2])
  assert.equal(t.st.aborted, 3, 'close cancels it'); assert.equal(t.st.live, 0)
  t.st.mode = 'ok'
  const d = await waitingOn(clock, t)
  t.st.mode = 'hang'
  const p = d.poll(); await clock.advance(100)
  d.dispose(); await p
  assert.equal(t.st.aborted, 4, 'dispose cancels it'); assert.equal(t.st.live, 0)
  await Promise.all(polls)
})

test('R27c I481: a slow 500 (4.9s) for 40s is an answer every time: never unreachable, never failed', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = '500'; t.st.delay = 4900
  const seen = await drive(c, clock, 40000)
  assert.ok(seen.length >= 5)
  assert.ok(seen.every(([, p]) => p === 'installing'), JSON.stringify(seen))
  assert.equal(c.state.unreachable, undefined); assert.equal(t.st.timeouts, 0)
})

test('R27c real-machine 7s pause (hung, timeouts): not failed, unreachable shown, continues by itself', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  let readyCalls = 0
  const c = await waitingOn(clock, t, { onReady: () => { readyCalls++ } })
  t.st.mode = 'hang'
  const seen = await drive(c, clock, 7000)
  assert.ok(!seen.some(([, p]) => p === 'failed'), JSON.stringify(seen))
  assert.equal(c.state.unreachable, true)
  t.st.mode = 'ok'; t.st.stage = 'ready'
  await drive(c, clock, clock.t + 2000)
  assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
})

test('R27c real-machine 40s pause: failed (offline) at 35s, the 35s assertion threshold; resumes by itself after', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  let readyCalls = 0
  const c = await waitingOn(clock, t, { onReady: () => { readyCalls++ } })
  t.st.mode = 'hang'
  const t0 = clock.t
  const seen = (await drive(c, clock, t0 + 40000)).map(([at, p]) => [at - t0, p])
  const firstFail = seen.find(([, p]) => p === 'failed')
  // probes go out at 2, 9, 16, 23, 30 (each times out after 5s): the streak counts from the first send (2s), so the
  // probe sent at 30 fails at 35 - a 35s pause is failed before it resumes.
  assert.ok(firstFail && firstFail[0] === 35000, JSON.stringify(seen))
  assert.equal(c.state.offline, true)
  t.st.mode = 'ok'
  await drive(c, clock, clock.t + 10000, 10000)
  assert.equal(c.state.phase, 'installing', 'back: the wait resumes without a click'); assert.equal(c.state.offline, undefined)
  t.st.stage = 'ready'
  await drive(c, clock, clock.t + 2000)
  assert.equal(c.state.phase, 'ready'); assert.equal(readyCalls, 1)
})

test('R27c I482 S1: the machine sleeps 60s with a probe in flight and wakes to a healthy backend: not failed', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  await drive(c, clock, 6000)
  t.st.mode = 'hang'
  const before = t.st.calls
  const p = c.poll(); await clock.advance(1000)
  t.st.mode = 'ok'
  await clock.wake(60000) // the 5s timeout fires late, on wake
  await p
  assert.notEqual(c.state.phase, 'failed', 'a timeout around a sleep is not 60s of unreachability')
  assert.equal(c.state.offline, undefined)
  assert.equal(t.st.timeouts, 1)
  assert.equal(t.st.calls - before, 1, 'R28: no re-probe; the late timeout counts at most 2 x 5s')
  await drive(c, clock, clock.t + 2000)
  assert.equal(c.state.unreachable, undefined, 'the next poll is answered')
})

test('R29 (was R27c I482): a 5-minute sleep between polls with the backend down counts the 14s cap, never resets the count', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = 'down'
  await drive(c, clock, 10000) // 5 polls, 10s counted
  await clock.wake(5 * 60 * 1000)
  const seen = (await gaps(c, clock, [2000, 2000, 2000, 2000])).map(([, p]) => p)
  // 10 + 14 (the 302s gap, capped at 2 x 2s + 2 x 5s) = 24, then 26, 28, 30 -> failed on the 4th poll after waking
  assert.deepEqual(seen, ['installing', 'installing', 'installing', 'failed'])
  assert.equal(c.state.offline, true)
})

test('R27c I483: a 15-minute sleep while downloading is not a stall timeout; 10 awake minutes still are', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  t.st.stage = 'downloading'; t.st.progress = 5
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t })
  c.open('whisper_model_downloading', 'base')
  await drive(c, clock, 60000)
  assert.equal(c.state.phase, 'downloading')
  await clock.wake(15 * 60 * 1000)
  await drive(c, clock, clock.t + 60000)
  assert.equal(c.state.phase, 'downloading', 'the sleep is not counted as no progress')
  await drive(c, clock, clock.t + 9 * 60 * 1000)
  assert.equal(c.state.phase, 'timeout', '10 awake minutes without progress are a timeout')
})

function deferred() { let resolve, reject; const p = new Promise((a, b) => { resolve = a; reject = b }); return { p, resolve, reject } }

test('R27c I484/A1: a poll\'s download request answered after close + reinstall writes nothing; the new round sends its own', async () => {
  const clock = fakeClock()
  let stage = 'model'; const downloads = []
  const t = fakeTransport(clock, {
    readiness: async () => stage === 'model' ? check('whisper_model_missing', { model: 'base' }) : check('whisper_not_installed'),
    downloadModel: m => { const d = deferred(); downloads.push(d); return d.p },
  })
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t })
  c.open('whisper_not_installed'); stage = 'runtime'; await c.install(); stage = 'model'
  const stale = c.poll(); await clock.advance(0)
  assert.equal(downloads.length, 1, 'the poll asked for the model')
  c.close(); c.open('whisper_not_installed'); stage = 'runtime'; await c.install()
  assert.equal(c.state.phase, 'installing')
  downloads[0].resolve({}); await stale; await clock.advance(0)
  stage = 'model'
  const p = c.poll(); await clock.advance(0)
  assert.equal(downloads.length, 2, 'the new round sends its own download request (a stale answer must not mark it requested)')
  downloads[1].resolve({}); await p
  assert.equal(c.state.phase, 'downloading')
})

test('R27c A5/A8: close while install waits on its probe or its download request: nothing is written or sent', async () => {
  const clock = fakeClock()
  const probe = deferred(); const dl = deferred(); const log = []
  const t = fakeTransport(clock, { readiness: () => probe.p, downloadModel: m => { log.push('model:' + m); return dl.p }, installRuntime: async () => { log.push('runtime') } })
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t })
  c.open('whisper_model_missing', 'base')
  const a = c.install(); c.close()
  probe.resolve(check('whisper_not_installed')); await a; await clock.advance(0)
  assert.deepEqual(log, [], 'A8: after the read the round is over: no install request')
  assert.equal(c.state.phase, 'idle')
  const probe2 = deferred()
  t.api.readiness = () => probe2.p
  c.open('whisper_model_missing', 'base')
  const b = c.install(); probe2.resolve(check('whisper_model_missing', { model: 'base' })); await clock.advance(0)
  assert.deepEqual(log, ['model:base'])
  c.close(); dl.resolve({}); await b; await clock.advance(0)
  assert.equal(c.state.phase, 'idle', 'A5: a download accepted after close does not reopen the wait')
})

test('R27c I485: a poll during a retry shares the retry round: no second readiness, no ready consumed before the request', async () => {
  const clock = fakeClock()
  let calls = 0, readyCalls = 0; const probe = deferred(); const log = []
  const t = fakeTransport(clock, {
    readiness: () => { calls++; return calls === 1 ? Promise.resolve(check('whisper_not_installed')) : calls === 2 ? probe.p : Promise.resolve(check('ok')) },
    installRuntime: async () => { log.push('runtime') },
  })
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t, onReady: () => { readyCalls++ } })
  c.open('whisper_not_installed'); await c.install()
  assert.equal(c.state.phase, 'installing')
  const r = c.retry()          // e.g. retry pressed while still waiting: its probe is in flight
  const p = c.poll()           // the page's poll timer fires meanwhile
  await clock.advance(0)
  assert.equal(calls, 2, 'the poll shares the retry round instead of sending its own readiness')
  probe.resolve(check('whisper_not_installed')); await r; await p
  assert.deepEqual(log, ['runtime', 'runtime'])
  assert.equal(c.state.phase, 'installing'); assert.equal(readyCalls, 0, 'no ready consumed while the install request was out')
})

test('R27c A2: after retry or close + open, poll never shares the old round\'s promise', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = 'hang'
  const stale = c.poll()
  const r = c.retry()
  assert.notEqual(c.poll(), stale)
  t.st.mode = 'ok'; await clock.advance(6000); await Promise.all([stale, r])
  t.st.mode = 'hang'
  const stale2 = c.poll(); await clock.advance(0)
  c.close(); c.open('whisper_installing')
  const calls = t.st.calls
  const fresh = c.poll(); await clock.advance(0)
  assert.notEqual(fresh, stale2, 'the reopened wait polls on its own')
  assert.equal(t.st.calls, calls + 1, 'and sends its own readiness')
  t.st.mode = 'ok'; await clock.advance(6000); await Promise.all([stale2, fresh])
})

test('R27c D5: open / retry start the unreachable timer over (no inherited offlineSince)', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = 'down'
  await drive(c, clock, clock.t + 20000)
  assert.equal(c.state.unreachable, true)
  c.open('whisper_installing') // a coded refusal reopens the wait from a fresh round
  assert.equal(c.state.unreachable, undefined, 'the reopened wait is not shown as unreachable')
  const seen = await drive(c, clock, clock.t + 20000)
  assert.ok(!seen.some(([, p]) => p === 'failed'), `20s + 20s in two rounds is never 30s in a row: ${JSON.stringify(seen)}`)
})

test('R27c A6: dispose then activate (StrictMode remount) keeps polling', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  c.dispose()
  const calls = t.st.calls
  await c.poll(); assert.equal(t.st.calls, calls, 'disposed: no request')
  c.activate()
  t.st.stage = 'ready'
  await c.poll()
  assert.equal(t.st.calls, calls + 1); assert.equal(c.state.phase, 'ready')
})

// ---- hook tests on the same fake clock ----
function loadHook(clock) {
  const ts = require('typescript'); const vm = require('node:vm')
  const { outputText } = ts.transpileModule(fs.readFileSync(path.join(dir, 'useTranscriptionRecovery.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } })
  const hook = {}
  vm.runInNewContext(outputText, { exports: hook, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout, require: id => id === './transcriptionRecovery' ? recovery : require(id) })
  clock.act = true
  return hook
}
async function mountHook(clock, api, opts = {}, strict = false) {
  const hook = loadHook(clock)
  const box = { controller: null, last: null, renders: 0 }
  function Probe() { const [s, c] = hook.useTranscriptionRecovery(api, { now: () => clock.t, ...opts }); box.controller = c; box.last = s; return null }
  const root = createRoot(document.createElement('div'))
  await act(async () => { root.render(strict ? React.createElement(React.StrictMode, null, React.createElement(Probe)) : React.createElement(Probe)) })
  box.unmount = () => act(async () => root.unmount())
  return box
}

test('#403 hook: an offline failure keeps polling at the low frequency and continues by itself', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const h = await mountHook(clock, t.api)
  try {
    await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
    t.st.mode = 'down'
    await clock.advance(36000)
    assert.equal(h.last.phase, 'failed'); assert.equal(h.last.offline, true)
    const calls = t.st.calls
    await clock.advance(30000)
    assert.equal(t.st.calls - calls, 3, 'slow polls every 10s go on after an offline failure')
    t.st.mode = 'ok'; t.st.stage = 'ready'
    await clock.advance(12000)
    assert.equal(h.last.phase, 'ready')
  } finally { await h.unmount() }
})

test('R27c A7 hook: the first slow poll after an offline failure goes out after OFFLINE_RETRY_MS, not at once', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const sent = []; const inner = t.api.readiness
  t.api.readiness = signal => { sent.push(clock.t); return inner(signal) }
  const h = await mountHook(clock, t.api)
  try {
    let failedAt = null
    h.controller.subscribe(s => { if (failedAt === null && s.phase === 'failed') failedAt = clock.t })
    await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
    t.st.mode = 'down'
    await clock.advance(36000)
    assert.ok(failedAt !== null, 'failed (offline)')
    await clock.advance(recovery.OFFLINE_RETRY_MS + 100)
    const after = sent.filter(at => at >= failedAt)
    // the probe that failed (a network error answers at once, so it was sent at failedAt), then the first slow one
    assert.deepEqual(after, [failedAt, failedAt + recovery.OFFLINE_RETRY_MS], `first slow probe exactly OFFLINE_RETRY_MS after the failure: ${after}`)
  } finally { await h.unmount() }
})

test('R27c A6 hook under StrictMode: polling continues after the double mount, one loop only', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const h = await mountHook(clock, t.api, {}, true)
  try {
    await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
    await clock.advance(1000)
    const calls = t.st.calls
    await clock.advance(20000)
    const n = t.st.calls - calls
    assert.ok(n >= 9 && n <= 11, `one 2s loop: ${n} probes in 20s`)
    assert.equal(t.st.max, 1)
  } finally { await h.unmount() }
})

test('I428 hook unmount clears its poll timer and cancels the probe in flight', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const h = await mountHook(clock, t.api, { pollMs: 50 })
  await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
  await clock.advance(20)
  assert.ok(clock.pending() >= 1, 'a poll timer is scheduled while waiting')
  t.st.mode = 'hang'
  await clock.advance(40)
  assert.equal(t.st.live, 1)
  await h.unmount()
  assert.equal(t.st.aborted, 1, 'unmount cancels the probe in flight')
  assert.equal(clock.pending(), 0, 'unmount clears the timers (poll and the probe timeout)')
})

test('I428/I426 hook unmount with a poll in flight: nothing rescheduled, no auto-continue afterwards', async () => {
  const clock = fakeClock()
  const probe = deferred(); let calls = 0
  const t = fakeTransport(clock, { readiness: () => { calls++; return calls === 1 ? Promise.resolve(check('whisper_not_installed')) : probe.p } })
  let readyCalls = 0
  const h = await mountHook(clock, t.api, { pollMs: 5, onReady: () => { readyCalls++ } })
  await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
  await clock.advance(5)
  assert.equal(calls, 2, 'the first poll is in flight')
  await h.unmount()
  probe.resolve(check('ok')); await clock.advance(50)
  assert.equal(readyCalls, 0, 'no auto-continue after unmount')
  assert.equal(clock.pending(), 0, 'no timer rescheduled after unmount')
})

test('I426 hook: leaving offline and coming back continues once, with one readiness in flight at a time', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  let readyCalls = 0
  const h = await mountHook(clock, t.api, { onReady: () => { readyCalls++ } })
  try {
    await act(async () => { h.controller.open('whisper_not_installed'); await h.controller.install() })
    t.st.mode = 'hang'
    await clock.advance(40000)
    assert.equal(h.last.phase, 'failed'); assert.equal(h.last.offline, true)
    t.st.mode = 'ok'; t.st.stage = 'ready'
    await clock.advance(12000)
    assert.equal(h.last.phase, 'ready'); assert.equal(readyCalls, 1, 'continued exactly once'); assert.equal(t.st.max, 1)
  } finally { await h.unmount() }
})

// ---- #418 R28 (Dong's R27c review I490-I499 -> I510-I519) ----
/** Runs `fn` after `hops` microtasks once `p` settled (the timing of Dong's n2probe / i491 scripts). */
const afterHops = (p, hops, fn) => { let q = p.then(() => {}, () => {}); for (let i = 0; i < hops; i++) q = q.then(() => {}); q.then(fn) }

test('R28 I510 (N2): close() in the microtasks between a settled request and the commit writes nothing, no onReport / onReady', async () => {
  for (const kind of ['poll-ready', 'install-download']) {
    for (let hops = 0; hops <= 6; hops++) {
      const events = []; let c, closed = false
      const note = name => () => { if (closed) events.push(name) }
      const answer = kind === 'poll-ready' ? check('ok') : check('whisper_model_missing', { model: 'base' })
      const api = { ...fakeApi({ report: () => answer }),
        readiness: () => { const p = Promise.resolve(answer); if (kind === 'poll-ready') afterHops(p, hops, () => { closed = true; c.close() }); return p },
        downloadModel: () => { const p = Promise.resolve({}); afterHops(p, hops, () => { closed = true; c.close() }); return p } }
      c = recovery.createRecoveryController(api, { now: () => 0, onReady: note('onReady'), onReport: note('onReport') })
      c.open(kind === 'poll-ready' ? 'whisper_installing' : 'whisper_model_missing', 'base')
      c.subscribe(s => { if (closed && s.phase !== 'idle') events.push('state:' + s.phase) })
      if (kind === 'poll-ready') await c.poll(); else await c.install()
      for (let i = 0; i < 20; i++) await Promise.resolve()
      assert.ok(closed, `${kind} hops ${hops}: closed`)
      assert.equal(c.state.phase, 'idle', `${kind} hops ${hops}`)
      assert.deepEqual(events, [], `${kind} hops ${hops}: nothing after close`)
    }
  }
})

test('R28 I511: close() right after the probe answered never sends the install / download request', async () => {
  for (const code of ['whisper_not_installed', 'whisper_model_missing']) {
    for (let hops = 0; hops <= 5; hops++) {
      const order = []; let c
      const api = { ...fakeApi({ report: () => check(code, { model: 'base' }) }),
        readiness: () => { const p = Promise.resolve(check(code, { model: 'base' })); afterHops(p, hops, () => { order.push('close'); c.close() }); return p },
        installRuntime: async () => { order.push('request') }, downloadModel: async () => { order.push('request') } }
      c = recovery.createRecoveryController(api, { now: () => 0 })
      c.open(code, 'base'); await c.install()
      for (let i = 0; i < 20; i++) await Promise.resolve()
      assert.ok(!order.includes('close') || order.indexOf('request') === -1 || order.indexOf('request') < order.indexOf('close'), `${code} hops ${hops}: ${order}`)
      assert.equal(c.state.phase, 'idle')
    }
  }
})

test('R28 I512: a 15-minute sleep inside getModels / getRuntimeStatus is not a stall', async () => {
  for (const stage of ['downloading', 'installing']) {
    let t = 0; let sleepNext = false
    const sleepy = () => { if (sleepNext) { t += 15 * 60 * 1000; sleepNext = false } }
    const api = { ...fakeApi({ report: () => stage === 'downloading' ? check('whisper_model_downloading', { model: 'base' }) : check('whisper_installing') }),
      getModels: async () => { sleepy(); return [{ name: 'base', status: 'downloading', downloadProgress: 40 }] },
      getRuntimeStatus: async () => { sleepy(); return { status: 'installing', progress: 40 } } }
    const c = recovery.createRecoveryController(api, { now: () => t })
    c.open(stage === 'downloading' ? 'whisper_model_downloading' : 'whisper_installing', 'base')
    t += 2000; await c.poll(); t += 2000; await c.poll()
    sleepNext = true; t += 2000; await c.poll()
    assert.equal(c.state.phase, stage, `${stage}: the sleep inside the follow-up read is not counted`)
  }
})

test('R28 I513: follow-up reads take the round signal; a hung read ends after the 5s timeout and close cancels it', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const reads = { live: 0, aborted: 0, signals: [] }
  const hung = signal => new Promise((resolve, reject) => {
    reads.live++; reads.signals.push(signal)
    let done = false
    const end = err => { if (done) return; done = true; reads.live--; reject(err) }
    const timer = clock.setTimeout(() => end(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' })), recovery.READINESS_TIMEOUT_MS)
    signal.addEventListener('abort', () => { if (done) return; clock.clearTimeout(timer); reads.aborted++; end(new Error('canceled')) })
  })
  t.api.getModels = hung; t.api.getRuntimeStatus = hung
  t.st.stage = 'downloading'; t.st.progress = 5
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t })
  c.open('whisper_model_downloading', 'base')
  t.api.getModels = async () => [{ name: 'base', status: 'downloading', downloadProgress: 5 }]
  await c.poll(); assert.equal(c.state.percent, 5)
  t.api.getModels = hung
  const p = c.poll(); await clock.advance(5000); await p
  assert.equal(c.state.phase, 'downloading', 'the hung read timed out; the wait goes on'); assert.equal(reads.live, 0)
  assert.equal(c.state.percent, 5, 'a failed read keeps the last progress (no reset that restarts the stall time)')
  assert.ok(reads.signals.every(s => s instanceof AbortSignal))
  const q = c.poll(); await clock.advance(1000)
  assert.equal(reads.live, 1)
  c.close(); await q
  assert.equal(reads.aborted, 1, 'close cancels the follow-up read'); assert.equal(reads.live, 0)
  t.st.stage = 'installing'
  const d = recovery.createRecoveryController(t.api, { now: () => clock.t })
  d.open('whisper_installing')
  const r = d.poll(); await clock.advance(1000)
  assert.equal(reads.live, 1, 'getRuntimeStatus in flight')
  d.close(); await r
  assert.equal(reads.aborted, 2, 'close cancels the runtime read too'); assert.equal(reads.live, 0)
})

test('R28 A8: a probe that ignores its signal still ends the round at once on close', async () => {
  const api = { ...fakeApi({}), readiness: () => new Promise(() => {}) }
  const c = recovery.createRecoveryController(api, { now: () => 0 })
  c.open('whisper_installing')
  let done = false; const p = c.poll().then(() => { done = true })
  await Promise.resolve(); c.close()
  for (let i = 0; i < 5; i++) await Promise.resolve()
  assert.ok(done, 'the round does not wait for a request that never settles'); await p
})

test('R28 I515: slow rounds (4s probe + 4s read) are observed time: timeout within one round of 10 minutes', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  t.st.delay = 4000
  const slowModels = () => new Promise(resolve => clock.setTimeout(() => resolve([{ name: 'base', status: 'downloading', downloadProgress: 5 }]), 4000))
  t.api.getModels = slowModels
  const c = downloadingOn(clock, t)
  await gaps(c, clock, [2000])
  const seen = await gaps(c, clock, Array(70).fill(2000))
  const first = seen.find(([, p]) => p === 'timeout')
  assert.ok(first && first[0] <= recovery.STALL_MS + 10000, JSON.stringify(first))
})

test('R28 I515: polls that alternate unanswered / answered without progress still time out at 10 minutes', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = downloadingOn(clock, t)
  await gaps(c, clock, [2000])
  const seen = []
  for (let i = 0; i < 320; i++) { t.st.mode = i % 2 ? 'ok' : 'down'; seen.push(...(await gaps(c, clock, [2000])).map(([, p]) => p)) }
  assert.ok(!seen.includes('failed'), 'never 30s unreachable in a row')
  const at = seen.indexOf('timeout')
  assert.ok(at >= 0 && at <= 300, `timeout after ${at + 1} polls`)
})

/** services/api.ts with the real axios and the real apiConfigManager, as the desktop app runs it (Tauri window). */
function loadRealApi({ tauri = false } = {}) {
  const vm = require('node:vm'); const ts = require('typescript'); const axios = require('axios')
  const cfgDir = path.resolve(__dirname, '../src/utils')
  const { apiConfigManager } = loadTs(path.join(cfgDir, 'apiConfig.ts'), {}, cfgDir)
  const exports = {}
  const mocks = {
    axios: { default: axios }, '../analytics/workflow': {}, '../i18n': { t: x => x },
    '../utils/errorHandler': { errorHandler: { handleError() {} } }, '../utils/apiConfig': { apiConfigManager },
    '../analytics/operations': {}, '../analytics/observer': {}, '../analytics/posthog': {}, '../analytics/events': {},
  }
  const source = fs.readFileSync(path.resolve(__dirname, '../src/services/api.ts'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, {
    exports, require: id => { assert.ok(id in mocks, id); return mocks[id] }, console, setTimeout, clearTimeout,
    window: tauri ? { __TAURI__: {} } : undefined,
  })
  return { api: exports.default, speechApi: exports.speechApi, apiConfigManager, axios }
}

test('R28 I514 (behaviour): a request aborted while waiting for the desktop backend is never sent, even once it is ready', async () => {
  const { api, apiConfigManager, axios } = loadRealApi({ tauri: true })
  apiConfigManager.config = { ...apiConfigManager.config, isReady: false }
  const sent = []
  api.defaults.adapter = async config => { sent.push(config.url); return { status: 200, data: {}, headers: {}, config } }
  const ctrl = new AbortController()
  let outcome = null
  const p = api.get('/whisper/runtime-status', recovery.probeConfig(ctrl.signal)).then(() => { outcome = 'sent' }, e => { outcome = axios.isCancel(e) ? 'cancelled' : 'error' })
  for (let i = 0; i < 5; i++) await Promise.resolve()
  assert.equal(outcome, null, 'waiting for the backend config'); assert.equal(sent.length, 0)
  ctrl.abort()
  for (let i = 0; i < 20; i++) await Promise.resolve()
  assert.equal(outcome, 'cancelled', 'abort ends the wait at once (not after waitForReady\'s 30s)')
  apiConfigManager.updateConfig({ baseUrl: 'http://127.0.0.1:1/api/v1', port: 1, isReady: true }) // the backend comes up later
  await p; for (let i = 0; i < 20; i++) await Promise.resolve()
  assert.deepEqual(sent, [], 'no request after the abort')
  // control: without an abort the same request goes out once the backend is ready
  apiConfigManager.config = { ...apiConfigManager.config, isReady: false }
  const q = api.get('/whisper/runtime-status', recovery.probeConfig(new AbortController().signal))
  for (let i = 0; i < 5; i++) await Promise.resolve()
  apiConfigManager.updateConfig({ isReady: true }); await q
  assert.deepEqual(sent, ['/whisper/runtime-status'])
})

test('R28 readiness timeout 5s (behaviour, fake timers): the probe and the follow-up read are aborted at 5s, not before', async t => {
  const { api, speechApi, apiConfigManager } = loadRealApi()
  apiConfigManager.updateConfig({ baseUrl: 'http://127.0.0.1:1/api/v1', port: 1, isReady: true })
  const studioApi = loadTs(path.join(dir, 'api.ts'), {
    '../../analytics/posthog': { captureBusinessEvent() {} }, '../../analytics/workflow': { safeStudioProperties: x => x },
    '../../analytics/studio': {}, '../../analytics/observer': { workflow: {} }, '../../services/api': { default: api },
    './noticeRuntime': { noteWorkspaceCompletion() {} }, './subtitleState': { effectiveSubtitles: () => false }, './types': {},
  }, dir).studioApi
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const live = new Map()
  // axios' fetch adapter with a backend that never answers: the request ends only when its signal aborts.
  const fetch = (url, init) => new Promise((resolve, reject) => {
    const signal = url instanceof Request ? url.signal : init.signal
    const key = String(url.url ?? url); live.set(key, 'open')
    signal.addEventListener('abort', () => { live.set(key, 'aborted'); reject(signal.reason ?? new Error('aborted')) })
  })
  api.defaults.adapter = 'fetch'; api.defaults.env = { ...api.defaults.env, fetch, Request, Response }
  const round = new AbortController()
  const outcomes = {}
  const watch = (name, p) => p.then(() => { outcomes[name] = 'answered' }, e => { outcomes[name] = recovery.isNetworkError(e) && /^(ECONNABORTED|ETIMEDOUT)$/.test(e.code) ? 'timeout' : e.code })
  const all = Promise.all([watch('probe', studioApi.readinessProbe(round.signal)), watch('read', speechApi.getRuntimeStatus(recovery.probeConfig(round.signal)))])
  for (let i = 0; i < 50; i++) await new Promise(r => setImmediate(r))
  assert.deepEqual([...live.values()], ['open', 'open'], 'both requests are in flight ' + JSON.stringify(outcomes))
  t.mock.timers.tick(4999)
  for (let i = 0; i < 20; i++) await new Promise(r => setImmediate(r))
  assert.deepEqual([...live.values()], ['open', 'open'], 'still open at 4.999s')
  t.mock.timers.tick(1)
  for (let i = 0; i < 50 && Object.keys(outcomes).length < 2; i++) await new Promise(r => setImmediate(r))
  const at5s = [...live.values()]
  round.abort(); await all // a mutant that never times out must not hang the file
  assert.deepEqual(at5s, ['aborted', 'aborted'], 'aborted at 5s')
  // axios' timeout code: ECONNABORTED from the xhr adapter (the app), ETIMEDOUT from fetch (here); no response either way
  assert.deepEqual(outcomes, { probe: 'timeout', read: 'timeout' }, 'a timeout (no response): the controller counts it as unreachable')
})

/** Drives polls with explicit gaps (ms before each poll), returns [[time since start, phase]]. */
async function gaps(c, clock, list) {
  const t0 = clock.t; const seen = []
  for (const g of list) {
    await clock.advance(g)
    let done = false; const p = c.poll().then(() => { done = true })
    await clock.advance(0)
    for (let i = 0; i < 200 && !done; i++) await clock.advance(100)
    await p; seen.push([clock.t - t0, c.state.phase])
  }
  return seen
}
const downloadingOn = (clock, t) => {
  t.st.stage = 'downloading'; t.st.progress = 5
  const c = recovery.createRecoveryController(t.api, { now: () => clock.t })
  c.open('whisper_model_downloading', 'base')
  return c
}

test('R28 I515: awake 10 minutes of on-time 2s polls without progress (answered or 500) time out at 10 minutes', async () => {
  for (const mode of ['ok', '500']) {
    const clock = fakeClock(); const t = fakeTransport(clock)
    const c = downloadingOn(clock, t)
    await gaps(c, clock, [2000]) // percent null -> 5: the last progress
    t.st.mode = mode
    const seen = await gaps(c, clock, Array(310).fill(2000))
    const first = seen.find(([, p]) => p === 'timeout')
    assert.ok(first, `${mode}: the stall is reported (not suppressed)`)
    assert.equal(first[0], recovery.STALL_MS, `${mode}: exactly at 10 minutes of polls`)
    assert.ok(seen.filter(([at]) => at < recovery.STALL_MS).every(([, p]) => p === 'downloading'), `${mode}: not earlier`)
  }
})

test('R28 I515: jittered polls (2s +- 1.5s) are all observed time: timeout within one poll of 10 minutes', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = downloadingOn(clock, t)
  await gaps(c, clock, [2000])
  const list = []; for (let i = 0; i < 400; i++) list.push([3500, 500, 3000, 1000][i % 4])
  const seen = await gaps(c, clock, list)
  const first = seen.find(([, p]) => p === 'timeout')
  assert.ok(first && first[0] >= recovery.STALL_MS && first[0] <= recovery.STALL_MS + 3500, JSON.stringify(first))
})

test('R28 I515: the clock jumping 10 minutes at once is not a timeout; the stall keeps counting after it', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = downloadingOn(clock, t)
  await gaps(c, clock, [2000, 2000])
  const seen = await gaps(c, clock, [10 * 60 * 1000, 2000])
  assert.ok(seen.every(([, p]) => p === 'downloading'), JSON.stringify(seen))
  const after = await gaps(c, clock, Array(300).fill(2000))
  assert.ok(after.some(([, p]) => p === 'timeout'), 'observed minutes after the jump still count')
})

test('R29 I576 (Dong): a 15-minute sleep counts 14s: 9:50 without progress -> timeout on waking; 1:00 -> not, then 8:46 more', async () => {
  for (const [polls, wakeAs, more] of [[295, 'timeout', 0], [30, 'downloading', 263]]) {
    const clock = fakeClock(); const t = fakeTransport(clock)
    const c = downloadingOn(clock, t)
    await gaps(c, clock, [2000]) // percent null -> 5: the last progress
    const before = await gaps(c, clock, Array(polls).fill(2000))
    assert.ok(before.every(([, p]) => p === 'downloading'), `${polls * 2}s counted before the sleep`)
    const wake = await gaps(c, clock, [15 * 60 * 1000])
    assert.equal(wake[0][1], wakeAs, `${polls * 2}s + 14s`)
    if (!more) continue
    const after = (await gaps(c, clock, Array(more).fill(2000))).map(([, p]) => p)
    // 74s counted at waking: 526s (263 polls, 8:46) more to 600s, not one poll earlier
    assert.deepEqual([after.indexOf('timeout'), after.slice(0, more - 1).every(p => p === 'downloading')], [more - 1, true])
  }
})

test('R29 (was R28 I515): offline 26s, then a 60s sleep: back -> continues; still down -> 26 + 14 = 40s, failed on waking', async () => {
  for (const [polls, back, wakeAs, next] of [[13, true, 'installing', null], [13, false, 'failed', null], [7, false, 'installing', 'failed']]) {
    const clock = fakeClock(); const t = fakeTransport(clock)
    const c = await waitingOn(clock, t)
    t.st.mode = 'down'
    const down = await gaps(c, clock, Array(polls).fill(2000))
    assert.ok(down.every(([, p]) => p === 'installing'))
    assert.equal(c.state.unreachable, true)
    if (back) t.st.mode = 'ok'
    const wake = await gaps(c, clock, [60000])
    assert.equal(wake[0][1], wakeAs, `${polls * 2}s down, back=${back}`)
    if (back) assert.equal(c.state.unreachable, undefined)
    // control: 14s down + 14s for the sleep = 28s, still waiting; the next 2s poll makes 30s
    if (next) assert.equal((await gaps(c, clock, [2000]))[0][1], next)
  }
})

/** The hook's cadence (useTranscriptionRecovery): the next poll POLL_MS after a waiting round ends, OFFLINE_RETRY_MS
 * after an offline failure; awake the whole time. Returns [[time since start, phase, offline]]. */
async function hookCadence(c, clock, ms) {
  const t0 = clock.t; const seen = []
  while (clock.t - t0 < ms) {
    const s = c.state
    await clock.advance(s.phase === 'failed' && s.offline ? recovery.OFFLINE_RETRY_MS : recovery.POLL_MS)
    let done = false; const p = c.poll().then(() => { done = true })
    await clock.advance(0)
    for (let i = 0; i < 200 && !done; i++) await clock.advance(100)
    await p; seen.push([clock.t - t0, c.state.phase, !!c.state.offline])
  }
  return seen
}
const timesOut = clock => () => new Promise((resolve, reject) => clock.setTimeout(() => reject(Object.assign(new Error('timeout of 5000ms exceeded'), { code: 'ECONNABORTED' })), recovery.READINESS_TIMEOUT_MS))

test('R28 I515 (Dong 11:2x): every probe hits the full 5s timeout, awake 10 minutes: failed (offline) at 35s and never cleared', async () => {
  const clock = fakeClock(); const t = fakeTransport(clock)
  const c = await waitingOn(clock, t)
  t.st.mode = 'hang' // each probe ends with axios' 5s timeout: 2s wait + 5s round = 7s between round ends
  const seen = await hookCadence(c, clock, 10 * 60 * 1000)
  const first = seen.findIndex(([, p]) => p === 'failed')
  assert.ok(first >= 0 && seen[first][0] <= 35000, `failed by 35s, not reset by the 7s spacing: ${JSON.stringify(seen.slice(0, 8))}`)
  assert.ok(seen.slice(first).every(([, p, off]) => p === 'failed' && off), 'stays failed (offline) for the rest of the 10 minutes')
  assert.ok(t.st.timeouts >= 40, `slow polls go on (10s wait + 5s timeout) (${t.st.timeouts} timeouts)`)
})

test('R28 I515 (Dong 11:2x): answered probe but the follow-up read times out every round, awake 10 minutes: timeout', async () => {
  for (const delay of [0, 4900]) {
    const clock = fakeClock(); const t = fakeTransport(clock)
    t.st.delay = delay
    const c = downloadingOn(clock, t)
    await gaps(c, clock, [2000]) // percent null -> 5: the last progress
    t.api.getModels = timesOut(clock) // every round: probe (+ delay) + 5s read timeout; the wait between is 2s
    const seen = await hookCadence(c, clock, recovery.STALL_MS + 20000)
    const first = seen.find(([, p]) => p === 'timeout')
    assert.ok(first && first[0] <= recovery.STALL_MS + 2000 + delay + 5000, `delay ${delay}: timeout within one round of 10 minutes: ${JSON.stringify(first)}`)
    assert.ok(seen.filter(([at]) => at < recovery.STALL_MS - 12000).every(([, p]) => p === 'downloading'), `delay ${delay}: not earlier`)
  }
})

test('R28 I516: a closed own install reopened from whisper_installing does not inherit ownsInstall (#372/#281)', async () => {
  let report = check('whisper_not_installed')
  const api = fakeApi({ report: () => report })
  const c = recovery.createRecoveryController(api, { now: () => 0 })
  c.open('whisper_not_installed'); await c.install()
  assert.deepEqual(api.log, ['runtime'])
  c.close()
  c.open('whisper_installing')
  report = check('whisper_model_missing', { model: 'base' })
  await c.poll()
  assert.deepEqual(api.log, ['runtime'], 'no automatic model download for an install this round did not start')
  assert.equal(c.state.phase, 'install_required')
})
