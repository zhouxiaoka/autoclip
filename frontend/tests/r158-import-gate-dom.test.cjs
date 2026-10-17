// R20 #166 #167: render the real CreativeImport (real React + happy-dom, real importReadiness, real errorText,
// real TranscriptionGatePrompt) and assert what the user sees, not the arguments passed to setError.
const { test, before, after } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')  // #328: the one sandbox helper (same file as #422)
const ts = require('typescript')
const { Window } = require('happy-dom')

const React = require('react')
const { act } = React
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
function load(file, mocks, clock) {
  const abs = path.join(dir, file)
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX }, fileName: abs })
  const exports = {}
  const req = id => {
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.startsWith('./')) return load(id.slice(2) + (fs.existsSync(path.join(dir, id.slice(2) + '.tsx')) ? '.tsx' : '.ts'), mocks, clock)
    throw new Error('unexpected import ' + id)
  }
  runInSandbox(outputText, { exports, require: req, window, console, FormData: window.FormData, HTMLElement: window.HTMLElement, URL, Promise, AbortController, setTimeout: clock ? clock.setTimeout : setTimeout, clearTimeout: clock ? clock.clearTimeout : clearTimeout, ...(clock ? { Date: clock.Date } : {}) })
  return exports
}

const h = React.createElement
const Btn = ({ children, onClick, disabled, loading }) => h('button', { type: 'button', onClick, disabled: !!(disabled || loading) }, children)
const okCheck = { ok: true, code: 'ok', repair: 'none' }
const READY = { analysis_mode: 'auto', ready: true, checks: { analysis: okCheck, transcription: okCheck, visual: okCheck, ffmpeg: okCheck } }

function mount({ readiness, importImpl, dropZone = false, autostart = false, speech = {}, clock, navigate = () => {}, pasteStart = {} }) {
  const calls = []
  const realErrorText = load('errorText.ts', {})
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: (s, v) => v ? s.replace(/\{\{(\w+)\}\}/g, (_, k) => v[k]) : s, getLocale: () => 'zh-CN' },
    antd: { Select: () => null },
    'react-router-dom': { useNavigate: () => navigate },
    '../../ui': { Btn, Segmented: () => null, Dialog: () => null, StatusDot: ({ label }) => h('span', null, label) },
    './PlatformPicker': { default: () => null },
    './api': { studioApi: { readiness, readinessProbe: signal => readiness(signal), import: body => { calls.push(body); return importImpl(body) } }, ...realErrorText },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-importflow-aaaaaaaa' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: name => dropZone && name === 'import_drop_zone', flagValue: name => autostart && name === 'one_click_paste_start' ? 'autostart' : 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
    '../../analytics/experience': { trackExperience() {} },
    './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
    './StyleProbeLine': { default: () => null },
    './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: () => null },
    '../../services/api': { speechApi: { installRuntime: async () => ({}), downloadModel: async () => ({}), getRuntimeStatus: async () => ({ status: 'installing', progress: 0 }), getModels: async () => [], ...speech } },
    './platformLabel': { platformLabel: id => id },
    './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
    './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: text => /^https:/.test(text || '') ? 'youtube' : null, isVideoFile: () => true, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000, ...pasteStart },
    './importPreferencesStore': { readImportPreferences: () => null },
    './studio.css': {}, './quick-output.css': {},
  }
  // R22 #209: with autostart the real pasteStart decides, so a global paste really reaches arm() and its lock.
  if (autostart) delete mocks['./pasteStart']
  const CreativeImport = load('CreativeImport.tsx', mocks, clock).default
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  return { host, root, calls, CreativeImport }
}

async function render(opts) {
  const view = mount(opts)
  await act(async () => { view.root.render(h(view.CreativeImport, { onImported: async () => {} })) })
  await act(async () => {})
  return view
}

async function typeUrl(host, value) {
  const area = host.querySelector('textarea')
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
  await act(async () => { setter.call(area, value); area.dispatchEvent(new window.Event('input', { bubbles: true })) })
}
const startButton = host => [...host.querySelectorAll('button')].find(b => /生成成片|正在生成/.test(b.textContent))
const axios422 = detail => Object.assign(new Error('Request failed with status code 422'), { response: { status: 422, data: { detail } } })

test('R20 #166: while submit re-probes readiness the form is locked and nothing is sent yet', async () => {
  let probes = 0
  const pending = []
  const readiness = () => { probes++; if (probes === 1) return Promise.reject(new Error('down')); return new Promise((_, reject) => pending.push(reject)) }
  const view = await render({ readiness, importImpl: async () => ({ project_id: 'p' }) })
  await typeUrl(view.host, 'https://youtube.com/watch?v=one')
  await act(async () => { startButton(view.host).click() })
  // probe 2 is still waiting
  assert.equal(pending.length, 1)
  assert.equal(view.calls.length, 0)
  assert.equal(view.host.querySelector('textarea').disabled, true, 'link input must be locked during the re-probe')
  assert.equal(startButton(view.host).disabled, true)
  // the user cannot swap the link now; the eventual request carries what they clicked on
  for (let attempt = 0; attempt < 3; attempt++) {
    assert.equal(view.host.querySelector('textarea').disabled, true)
    await act(async () => { pending.shift()(new Error('down')) })
  }
  await act(async () => {})
  assert.equal(probes, 4)  // initial load + 3 re-checks
  assert.equal(view.calls.length, 1)
  assert.equal(view.calls[0].get('url'), 'https://youtube.com/watch?v=one')
  act(() => view.root.unmount())
})

for (const [code, label] of [['whisper_not_installed', '需要先安装本地转写'], ['whisper_installing', '等待安装完成']]) {
  test(`R20 #167: a coded 422 (${code}) renders the ${label} dialog in the page`, async () => {
    // The backend still reports the refused state on the next poll (a ready poll would continue by itself, #232).
    const view = await render({ readiness: thenReport(() => check(code)), importImpl: async () => { throw axios422({ code, message: 'whatever the backend says' }) } })
    await typeUrl(view.host, 'https://youtube.com/watch?v=one')
    assert.equal(view.host.querySelector('[role=alertdialog]'), null)
    await act(async () => { startButton(view.host).click() })
    await act(async () => {})
    assert.equal(view.calls.length, 1)
    const dialog = view.host.querySelector('[role=alertdialog]')
    assert.ok(dialog, 'the gate dialog must be rendered')
    assert.equal(dialog.getAttribute('aria-label'), label)
    assert.equal(view.host.querySelector('[role=alert]'), null, 'no plain error line next to the dialog')
    act(() => view.root.unmount())
  })
}

test('R20 #167: an ordinary 422 shows the error line, not the gate dialog', async () => {
  const view = await render({ readiness: async () => READY, importImpl: async () => { throw axios422('视频文件为空，请重新选择') } })
  await typeUrl(view.host, 'https://youtube.com/watch?v=one')
  await act(async () => { startButton(view.host).click() })
  await act(async () => {})
  assert.equal(view.host.querySelector('[role=alertdialog]'), null)
  assert.equal(view.host.querySelector('[role=alert]').textContent, '视频文件为空，请重新选择')
  act(() => view.root.unmount())
})

function dropFile(host, name) {
  const zone = host.querySelector('.ac-dropzone')
  const file = new window.File(['x'], name, { type: 'video/mp4' })
  const event = new window.Event('drop', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'dataTransfer', { value: { files: [file], getData: () => '' } })
  return act(async () => { zone.dispatchEvent(event) })
}
function pasteText(text) {
  const event = new window.Event('paste', { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'clipboardData', { value: { getData: () => text } })
  return act(async () => { window.dispatchEvent(event) })
}
function hangingProbe() {
  let probes = 0
  const pending = []
  const readiness = () => { probes++; if (probes === 1) return Promise.reject(new Error('down')); return new Promise((_, reject) => pending.push(reject)) }
  return { readiness, pending, count: () => probes }
}
const removeButton = host => [...host.querySelectorAll('button')].find(b => b.textContent === '移除')

test('R21 #166: drop and global paste during the re-probe cannot swap the source; the shown file is the uploaded one', async () => {
  const probe = hangingProbe()
  const view = await render({ readiness: probe.readiness, importImpl: async () => ({ project_id: 'p' }), dropZone: true })
  await dropFile(view.host, 'first.mp4')
  assert.match(view.host.textContent, /first\.mp4/)
  await act(async () => { startButton(view.host).click() })
  assert.equal(probe.pending.length, 1)
  await dropFile(view.host, 'second.mp4')
  await pasteText('https://youtube.com/watch?v=other')
  assert.match(view.host.textContent, /first\.mp4/)
  assert.doesNotMatch(view.host.textContent, /second\.mp4/)
  assert.equal(view.host.querySelector('textarea').value, '')
  for (let i = 0; i < 3; i++) await act(async () => { probe.pending.shift()(new Error('down')) })
  await act(async () => {})
  assert.equal(view.calls.length, 1)
  assert.equal(view.calls[0].get('video').name, 'first.mp4')
  assert.equal(view.calls[0].get('url'), null)
  act(() => view.root.unmount())
})

test('R21 #177: 移除 is locked while waiting, and a failed import releases the lock', async () => {
  const probe = hangingProbe()
  const view = await render({ readiness: probe.readiness, importImpl: async () => { throw axios422('视频文件为空，请重新选择') }, dropZone: true })
  await dropFile(view.host, 'first.mp4')
  assert.equal(removeButton(view.host).disabled, false)
  await act(async () => { startButton(view.host).click() })
  assert.equal(removeButton(view.host).disabled, true)
  assert.equal(view.host.querySelector('textarea').disabled, true)
  for (let i = 0; i < 3; i++) await act(async () => { probe.pending.shift()(new Error('down')) })
  await act(async () => {})
  assert.equal(view.calls.length, 1)
  assert.equal(view.host.querySelector('[role=alert]').textContent, '视频文件为空，请重新选择')
  assert.equal(removeButton(view.host).disabled, false, 'lock released after the failure')
  assert.equal(view.host.querySelector('textarea').disabled, false)
  assert.equal(startButton(view.host).disabled, false)
  // and a new source is accepted again
  await dropFile(view.host, 'second.mp4')
  assert.match(view.host.textContent, /second\.mp4/)
  act(() => view.root.unmount())
})

test('R22 #209: real paste-to-start: an idle paste swaps the source, a paste during submit is refused by the lock', async () => {
  const probe = hangingProbe()
  const view = await render({ readiness: probe.readiness, importImpl: async () => { throw axios422('视频文件为空，请重新选择') }, dropZone: true, autostart: true })
  await dropFile(view.host, 'first.mp4')
  await act(async () => { [...view.host.querySelectorAll('button')].find(b => b.textContent === '撤销')?.click() })
  await act(async () => { startButton(view.host).click() })
  assert.equal(probe.pending.length, 1, 'submit is waiting on its readiness re-check')
  await pasteText('https://youtube.com/watch?v=busy')
  assert.match(view.host.textContent, /first\.mp4/, 'busy paste must not swap the source')
  assert.equal(view.host.querySelector('textarea').value, '')
  for (let i = 0; i < 3; i++) await act(async () => { probe.pending.shift()(new Error('down')) })
  await act(async () => {})
  assert.equal(view.calls.length, 1)
  assert.equal(view.calls[0].get('video').name, 'first.mp4')
  // lock released by the failure: the same real paste path now takes the link
  await pasteText('https://youtube.com/watch?v=idle')
  assert.equal(view.host.querySelector('textarea').value, 'https://youtube.com/watch?v=idle')
  assert.ok([...view.host.querySelectorAll('button')].some(b => b.textContent === '撤销'), 'idle paste arms auto start')
  act(() => view.root.unmount())
})

// ---- R24 #232: waiting for a Whisper install / model download never traps the user (real render)
function fakeClock() {
  let now = 1_000_000
  const timers = []
  class FakeDate extends Date { constructor(...a) { super(...(a.length ? a : [now])) } static now() { return now } }
  return {
    Date: FakeDate,
    setTimeout: (fn, ms) => { const id = timers.length + 1; timers.push({ id, fn, at: now + (ms || 0) }); return id },
    clearTimeout: id => { const t = timers.find(x => x.id === id); if (t) t.fn = null },
    async advance(ms) {
      now += ms
      for (const t of timers.filter(x => x.fn && x.at <= now)) { const fn = t.fn; t.fn = null; await act(async () => { fn() }); await act(async () => {}) }
    },
  }
}
const check = (code, extra = {}) => ({ analysis_mode: 'auto', ready: false, checks: { analysis: okCheck, transcription: { ok: false, code, repair: 'none', ...extra }, visual: okCheck, ffmpeg: okCheck } })
// The import page loads with everything ready; the 422 opens the dialog; later polls see the real state.
const thenReport = get => { let calls = 0; return async () => (++calls === 1 ? READY : get()) }
const button = (host, text) => [...host.querySelectorAll('button')].find(b => b.textContent === text)

async function openWaiting(view) {
  await typeUrl(view.host, 'https://youtube.com/watch?v=one')
  await act(async () => { startButton(view.host).click() })
  await act(async () => {}); await act(async () => {})
  const dialog = view.host.querySelector('[role=alertdialog]')
  assert.ok(dialog, 'waiting dialog rendered')
  assert.equal(dialog.getAttribute('aria-label'), '等待安装完成')
  return dialog
}

test('#232: the model download dialog shows live progress, then continues the same import by itself when done', async () => {
  const clock = fakeClock()
  let report = check('whisper_model_downloading', { model: 'small' })
  let percent = 35
  const imports = []
  const view = await render({ clock, readiness: thenReport(() => report),
    speech: { getModels: async () => [{ name: 'small', status: 'downloading', downloadProgress: percent }] },
    importImpl: async body => { imports.push(body); if (imports.length === 1) throw axios422({ code: 'whisper_model_downloading', message: 'x' }); return { project_id: 'p' } } })
  await openWaiting(view)
  assert.equal(view.host.querySelector('[role=progressbar]').getAttribute('aria-valuenow'), '35')
  assert.match(view.host.textContent, /已完成 35%/)
  assert.match(view.host.textContent, /正在下载转写模型/, 'a download is not shown as an install')
  assert.doesNotMatch(view.host.textContent, /正在安装/)
  percent = 80
  await clock.advance(2000)
  assert.equal(view.host.querySelector('[role=progressbar]').getAttribute('aria-valuenow'), '80')
  assert.equal(button(view.host, '继续导入'), undefined, 'no continue while still downloading')
  report = READY
  await clock.advance(2000); await act(async () => {}); await act(async () => {})
  assert.equal(imports.length, 2, 'download done -> the same import is re-sent by itself, no click (#232)')
  assert.equal(imports[1].get('url'), 'https://youtube.com/watch?v=one')
  assert.equal(view.host.querySelector('[role=alertdialog]'), null)
  act(() => view.root.unmount())
})

test('R24 #232: a failed install offers retry (restarts it and waits again) and transcription settings', async () => {
  const clock = fakeClock()
  const installs = []
  const went = []
  let runtime = { status: 'installing', progress: 20 }
  const view = await render({ clock, navigate: to => went.push(to), readiness: thenReport(() => check('whisper_installing')),
    speech: { getRuntimeStatus: async () => runtime, installRuntime: async () => { installs.push(1); runtime = { status: 'installing', progress: 1 }; return {} } },
    importImpl: async () => { throw axios422({ code: 'whisper_installing', message: 'x' }) } })
  await openWaiting(view)
  assert.match(view.host.textContent, /已完成 20%/)
  runtime = { status: 'error', progress: 20 }
  await clock.advance(2000)
  assert.match(view.host.textContent, /安装或模型下载失败/)
  await act(async () => { button(view.host, '打开转写设置').click() })
  assert.deepEqual(went, ['/settings?section=speech'])
  await act(async () => { button(view.host, '重试').click() }); await act(async () => {}); await act(async () => {})
  assert.equal(installs.length, 1, 'retry restarts the install')
  assert.equal(button(view.host, '重试'), undefined, 'back to waiting after retry')
  assert.match(view.host.textContent, /已完成 1%/)
  act(() => view.root.unmount())
})

test('R24 #232: a stalled download times out into retry (model download again) or settings', async () => {
  const clock = fakeClock()
  const downloads = []
  const view = await render({ clock, readiness: thenReport(() => check('whisper_model_downloading', { model: 'small' })),
    speech: { getModels: async () => [{ name: 'small', status: 'downloading', downloadProgress: 5 }], downloadModel: async model => { downloads.push(model); return {} } },
    importImpl: async () => { throw axios422({ code: 'whisper_model_downloading', message: 'x' }) } })
  await openWaiting(view)
  for (let i = 0; i < 5; i++) await clock.advance(2000)
  assert.equal(button(view.host, '重试'), undefined, 'not a timeout yet')
  // R28 I515: the clock jumps 10 minutes at once (no polls in between: unobserved) -> NO timeout, polling goes on
  await clock.advance(10 * 60 * 1000)
  await clock.advance(2000)
  assert.doesNotMatch(view.host.textContent, /长时间没有进展/, 'a 10-minute jump is not 10 observed minutes')
  assert.equal(button(view.host, '重试'), undefined)
  // ...and the stall time keeps counting afterwards: 10 awake minutes of 2s polls without progress are a timeout
  for (let i = 0; i < 301; i++) await clock.advance(2000)
  assert.match(view.host.textContent, /长时间没有进展/)
  assert.ok(button(view.host, '打开转写设置'))
  await act(async () => { button(view.host, '重试').click() }); await act(async () => {}); await act(async () => {})
  assert.deepEqual(downloads, ['small'])
  act(() => view.root.unmount())
})

test('#349: from model_missing (no READY first): 一键安装 -> download -> done -> the import really goes out once, no second install prompt', async () => {
  const clock = fakeClock()
  let report = check('whisper_model_missing', { model: 'small' })
  const downloads = []
  const imports = []
  const view = await render({ clock, dropZone: true, readiness: async () => report,
    speech: { getModels: async () => [{ name: 'small', status: 'downloading', downloadProgress: 50 }], downloadModel: async model => { downloads.push(model); report = check('whisper_model_downloading', { model }); return {} } },
    importImpl: async body => { imports.push(body); return { project_id: 'p' } } })
  await dropFile(view.host, 'talk.mp4')
  await act(async () => { startButton(view.host).click() }); await act(async () => {})
  assert.equal(view.host.querySelector('[role=alertdialog]').getAttribute('aria-label'), '需要先安装本地转写')
  assert.equal(imports.length, 0)
  await act(async () => { button(view.host, '一键安装').click() }); await act(async () => {}); await act(async () => {})
  assert.deepEqual(downloads, ['small'])
  await clock.advance(2000)
  assert.match(view.host.textContent, /正在下载转写模型/)
  report = READY
  await clock.advance(2000); await act(async () => {}); await act(async () => {}); await act(async () => {})
  assert.equal(imports.length, 1, 'the import request is sent after the download (was 0: stale readiness reopened the prompt)')
  assert.equal(imports[0].get('video').name, 'talk.mp4')
  assert.equal(view.host.querySelector('[role=alertdialog]'), null, 'no install prompt again')
  act(() => view.root.unmount())
})

test('#353: the readiness list install button runs through the one recovery controller (no parallel install flow)', async () => {
  const clock = fakeClock()
  const installs = []
  let report = check('whisper_not_installed', { repair: 'install_whisper' })
  const view = await render({ clock, readiness: async () => report,
    speech: { installRuntime: async () => { installs.push('runtime'); report = check('whisper_installing'); return {} }, getRuntimeStatus: async () => ({ status: 'installing', progress: 30 }) },
    importImpl: async () => ({ project_id: 'p' }) })
  const listButton = [...view.host.querySelectorAll('button')].find(b => b.textContent === '安装 Whisper')
  assert.ok(listButton, 'readiness list offers install')
  await act(async () => { listButton.click() }); await act(async () => {}); await act(async () => {})
  assert.deepEqual(installs, ['runtime'])
  await clock.advance(2000)
  assert.equal(view.host.querySelector('[role=alertdialog]').getAttribute('aria-label'), '等待安装完成', 'the controller dialog waits with progress')
  assert.match(view.host.textContent, /已完成 30%/)
  act(() => view.root.unmount())
})

test('#370: 下载转写模型 from the list without 生成成片 does not send an import when the download finishes', async () => {
  const clock = fakeClock()
  let report = check('whisper_model_missing', { model: 'small', repair: 'install_whisper' })
  const imports = []
  const view = await render({ clock, dropZone: true, readiness: async () => report,
    speech: { getModels: async () => [{ name: 'small', status: 'downloading', downloadProgress: 50 }], downloadModel: async model => { report = check('whisper_model_downloading', { model }); return {} } },
    importImpl: async body => { imports.push(body); return { project_id: 'p' } } })
  await dropFile(view.host, 'talk.mp4')
  const listButton = [...view.host.querySelectorAll('button')].find(b => b.textContent === '下载转写模型')
  assert.ok(listButton)
  await act(async () => { listButton.click() }); await act(async () => {}); await act(async () => {})
  await clock.advance(2000)
  report = READY
  await clock.advance(2000); await act(async () => {}); await act(async () => {}); await act(async () => {})
  assert.equal(imports.length, 0, 'no submit was blocked, so nothing is imported by itself')
  assert.equal(view.host.querySelector('[role=alertdialog]'), null)
  await act(async () => { startButton(view.host).click() }); await act(async () => {}); await act(async () => {})
  assert.equal(imports.length, 1, 'the user can still start it')
  act(() => view.root.unmount())
})

test('#371: link_import_without_whisper background install runs through the controller and does not stay on 正在安装本地转写', async () => {
  const clock = fakeClock()
  let report = check('whisper_not_installed', { repair: 'install_whisper' })
  const installs = []
  const view = await render({ clock, readiness: async () => report,
    pasteStart: { shouldBackgroundInstallWhisper: (allow, code) => code === 'whisper_not_installed', claimBackgroundWhisperInstall: () => installs.length === 0 },
    speech: { installRuntime: async () => { installs.push('runtime'); report = check('whisper_installing'); return {} }, getRuntimeStatus: async () => ({ status: 'installing', progress: 10 }) },
    importImpl: async () => ({ project_id: 'p' }) })
  await act(async () => {}); await act(async () => {})
  assert.deepEqual(installs, ['runtime'])
  await clock.advance(2000); await act(async () => {})
  assert.match(view.host.textContent, /正在安装本地转写/)
  assert.equal(view.host.querySelector('[role=alertdialog]'), null, 'background install stays inline')
  report = READY
  await clock.advance(2000); await act(async () => {}); await act(async () => {})
  assert.doesNotMatch(view.host.textContent, /正在安装本地转写/, 'readiness was refreshed by the controller (was stuck)')
  assert.deepEqual(installs, ['runtime'])
  act(() => view.root.unmount())
})

test('#404: a background install that fails is shown (no longer hidden) with a retry that installs again', async () => {
  const clock = fakeClock()
  let report = check('whisper_not_installed', { repair: 'install_whisper' })
  const installs = []
  let runtime = { status: 'installing', progress: 10 }
  const view = await render({ clock, readiness: async () => report,
    pasteStart: { shouldBackgroundInstallWhisper: (allow, code) => code === 'whisper_not_installed', claimBackgroundWhisperInstall: () => installs.length === 0 },
    speech: { installRuntime: async () => { installs.push('runtime'); runtime = installs.length > 1 ? { status: 'installing', progress: 0 } : runtime; report = check('whisper_installing'); return {} }, getRuntimeStatus: async () => runtime },
    importImpl: async () => ({ project_id: 'p' }) })
  await act(async () => {}); await act(async () => {})
  assert.equal(view.host.querySelector('[role=alertdialog]'), null, 'running: inline')
  runtime = { status: 'error' }
  await clock.advance(2000); await act(async () => {}); await act(async () => {})
  const dialog = view.host.querySelector('[role=alertdialog]')
  assert.ok(dialog, 'failed background install is shown')
  assert.match(dialog.textContent, /安装或模型下载失败/)
  const retry = [...dialog.querySelectorAll('button')].find(b => b.textContent === '重试')
  assert.ok(retry, 'retry entry')
  await act(async () => { retry.click() }); await act(async () => {}); await act(async () => {})
  assert.deepEqual(installs, ['runtime', 'runtime'], 'retry installs again')
  act(() => view.root.unmount())
})

test('#372: model download 500 on the page shows failed with retry; polling does not resend', async () => {
  const clock = fakeClock()
  let report = check('whisper_model_missing', { model: 'small' })
  const downloads = []
  let fail = true
  const view = await render({ clock, dropZone: true, readiness: async () => report,
    speech: { downloadModel: async model => { downloads.push(model); if (fail) throw Object.assign(new Error('Request failed with status code 500'), { response: { status: 500 } }); report = check('whisper_model_downloading', { model }); return {} } },
    importImpl: async () => ({ project_id: 'p' }) })
  await dropFile(view.host, 'talk.mp4')
  await act(async () => { startButton(view.host).click() }); await act(async () => {})
  await act(async () => { button(view.host, '一键安装').click() }); await act(async () => {}); await act(async () => {})
  await clock.advance(2000); await clock.advance(2000)
  assert.deepEqual(downloads, ['small'], 'not resent by polling')
  assert.doesNotMatch(view.host.textContent, /正在下载转写模型/)
  assert.ok(button(view.host, '重试'), 'failed offers retry')
  fail = false
  await act(async () => { button(view.host, '重试').click() }); await act(async () => {}); await act(async () => {})
  assert.deepEqual(downloads, ['small', 'small'])
  await clock.advance(2000)
  assert.match(view.host.textContent, /正在下载转写模型/)
  act(() => view.root.unmount())
})
