// R20 #166 #167: render the real CreativeImport (real React + happy-dom, real importReadiness, real errorText,
// real TranscriptionGatePrompt) and assert what the user sees, not the arguments passed to setError.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { Window } = require('happy-dom')

const window = new Window({ url: 'http://localhost/' })
globalThis.window = window
globalThis.document = window.document
globalThis.navigator = window.navigator
globalThis.HTMLElement = window.HTMLElement
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const React = require('react')
const { createRoot } = require('react-dom/client')
const { act } = React

const dir = path.resolve(__dirname, '../src/features/studio')
function load(file, mocks) {
  const abs = path.join(dir, file)
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX }, fileName: abs })
  const exports = {}
  const req = id => {
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.startsWith('./')) return load(id.slice(2) + (fs.existsSync(path.join(dir, id.slice(2) + '.tsx')) ? '.tsx' : '.ts'), mocks)
    throw new Error('unexpected import ' + id)
  }
  vm.runInNewContext(outputText, { exports, require: req, window, console, FormData: window.FormData, Promise, setTimeout, clearTimeout })
  return exports
}

const h = React.createElement
const Btn = ({ children, onClick, disabled, loading }) => h('button', { type: 'button', onClick, disabled: !!(disabled || loading) }, children)
const okCheck = { ok: true, code: 'ok', repair: 'none' }
const READY = { analysis_mode: 'auto', ready: true, checks: { analysis: okCheck, transcription: okCheck, visual: okCheck, ffmpeg: okCheck } }

function mount({ readiness, importImpl }) {
  const calls = []
  const realErrorText = load('errorText.ts', {})
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: (s, v) => v ? s.replace(/\{\{(\w+)\}\}/g, (_, k) => v[k]) : s, getLocale: () => 'zh-CN' },
    antd: { Select: () => null },
    'react-router-dom': { useNavigate: () => () => {} },
    '../../ui': { Btn, Segmented: () => null, Dialog: () => null, StatusDot: ({ label }) => h('span', null, label) },
    './PlatformPicker': { default: () => null },
    './api': { studioApi: { readiness, import: body => { calls.push(body); return importImpl(body) } }, ...realErrorText },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-importflow-aaaaaaaa' },
    '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
    '../../analytics/experience': { trackExperience() {} },
    './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
    './StyleProbeLine': { default: () => null },
    './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: () => null },
    '../../services/api': { speechApi: { installRuntime: async () => ({}), downloadModel: async () => ({}) } },
    './platformLabel': { platformLabel: id => id },
    './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
    './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: () => null, isVideoFile: () => false, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000 },
    './importPreferencesStore': { readImportPreferences: () => null },
    './studio.css': {}, './quick-output.css': {},
  }
  const CreativeImport = load('CreativeImport.tsx', mocks).default
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
    const view = await render({ readiness: async () => READY, importImpl: async () => { throw axios422({ code, message: 'whatever the backend says' }) } })
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
