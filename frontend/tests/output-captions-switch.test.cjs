// Main-page 「字幕」 and settings 「自动成片压字幕」 read and write one output-captions setting.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const React = require('react')
const { runInSandbox } = require('./vm-sandbox.cjs')

const HINT = '关闭后成片不带字幕。标题只在封面上，不会烧进视频。'
const MAIN = '字幕'
const SETTINGS = '自动成片压字幕'
const SAVE_ERROR = '保存失败，请稍后重试'
const LANGS = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']
const h = React.createElement
const { act } = React
const studioDir = path.resolve(__dirname, '../src/features/studio')
const settingsFile = path.resolve(__dirname, '../src/features/settings/OutputCaptionsSetting.tsx')

const state = { enabled: true, failWrites: false, writes: [] }

const settingsApi = {
  getOutputCaptions: async () => ({ enabled: state.enabled }),
  setOutputCaptions: async (value) => {
    state.writes.push(value)
    if (state.failWrites) throw new Error('save failed')
    state.enabled = value
    return { enabled: state.enabled }
  },
}

function Switch({ checked, disabled, onChange, 'aria-label': label }) {
  return h('button', {
    type: 'button', role: 'switch', 'aria-label': label, 'aria-checked': checked ? 'true' : 'false',
    disabled: !!disabled, onClick: () => { if (!disabled) onChange(!checked) },
  })
}

function Row({ label, hint, children }) {
  return h('div', { className: 'ac-row' },
    h('div', { className: 'ac-row-label' }, h('b', null, label), hint ? h('small', null, hint) : null),
    h('div', { className: 'ac-row-control' }, children))
}

const message = {
  error(text) {
    const node = document.createElement('p')
    node.setAttribute('role', 'alert')
    node.dataset.saveError = '1'
    node.textContent = text
    document.body.appendChild(node)
  },
}

const settingsMocks = {
  '../../services/api': { settingsApi },
  '../../i18n': { t: value => value },
  '../../ui': { Row, Btn: ({ children, onClick }) => h('button', { type: 'button', onClick }, children) },
  antd: { Switch, message },
}

function loadModule(abs, mocks) {
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const req = (id) => {
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.endsWith('.css')) return {}
    if (id.startsWith('.')) {
      const base = path.resolve(path.dirname(abs), id)
      const hit = ['', '.ts', '.tsx'].map(ext => base + ext).find(candidate => fs.existsSync(candidate))
      if (!hit) throw new Error('missing ' + id + ' from ' + abs)
      return loadModule(hit, mocks)
    }
    throw new Error('unexpected import ' + id + ' from ' + path.basename(abs))
  }
  runInSandbox(outputText, { exports, require: req, console })
  return exports
}

const captionsModule = loadModule(settingsFile, settingsMocks)

function loadStudio(file, mocks) {
  const abs = path.join(studioDir, file)
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const req = (id) => {
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.startsWith('./')) {
      const stem = id.slice(2)
      const ext = fs.existsSync(path.join(studioDir, stem + '.tsx')) ? '.tsx' : '.ts'
      return loadStudio(stem + ext, mocks)
    }
    throw new Error('unexpected import ' + id)
  }
  runInSandbox(outputText, { exports, require: req, console, window, Promise, setTimeout, clearTimeout, AbortController, HTMLElement: window.HTMLElement, FormData: window.FormData })
  return exports
}

const okCheck = { ok: true, code: 'ok', repair: 'none' }
const READY = { analysis_mode: 'auto', ready: true, checks: { analysis: okCheck, transcription: okCheck, visual: okCheck, ffmpeg: okCheck } }

function studioMocks(templates) {
  return {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: (value, vars) => vars ? value.replace(/\{\{(\w+)\}\}/g, (_, key) => vars[key]) : value, getLocale: () => 'zh-CN' },
    antd: { Select: () => null, Switch, message },
    'react-router-dom': { useNavigate: () => () => {} },
    '../../ui': {
      Btn: ({ children, onClick, disabled, loading }) => h('button', { type: 'button', onClick, disabled: !!(disabled || loading) }, children),
      Segmented: () => null, Dialog: () => null, StatusDot: ({ label }) => h('span', null, label), Row,
    },
    './PlatformPicker': { default: () => null },
    './api': { studioApi: { readiness: async () => READY, readinessProbe: async () => READY, import: async () => ({ project_id: 'p' }) }, errorText: value => String(value), errorCode: () => undefined },
    '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
    '../../analytics/workflow': { telemetryId: () => 't-captions' },
    '../../analytics/flags': {
      useFlag: name => templates && name === 'pkg_templates_v1',
      flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({}),
    },
    '../../analytics/experience': { trackExperience() {} },
    './TemplatePicker': { default: () => h('h2', null, '剪辑风格'), templateImportFields: () => ({}) },
    './StyleProbeLine': { default: () => null },
    './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './ImportPreferences': { default: () => null },
    '../../services/api': {
      settingsApi,
      speechApi: { installRuntime: async () => ({}), downloadModel: async () => ({}), getRuntimeStatus: async () => ({ status: 'installed', progress: 100 }), getModels: async () => [] },
    },
    './platformLabel': { platformLabel: id => id },
    './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
    './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: () => null, isVideoFile: () => true, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000 },
    './importPreferencesStore': { readImportPreferences: () => null },
    './studio.css': {}, './quick-output.css': {},
    '../settings/OutputCaptionsSetting': captionsModule,
  }
}

let window
function installGlobals(values) {
  const saved = Object.keys(values).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
  for (const [key, value] of Object.entries(values)) {
    Object.defineProperty(globalThis, key, { value, writable: true, configurable: true, enumerable: true })
  }
  return () => {
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
}

async function openDom() {
  const Window = (await import('happy-dom')).Window
  window = new Window({ url: 'http://localhost/' })
  return installGlobals({ window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true })
}

function closeDom(restore) {
  try { window.happyDOM.abort?.(); window.close() } finally { restore(); window = undefined }
}

function reset() {
  state.enabled = true
  state.failWrites = false
  state.writes = []
  document.querySelectorAll('[data-save-error]').forEach(node => node.remove())
}

async function flush() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
}

function switchByLabel(host, label) {
  return [...host.querySelectorAll('button[role="switch"]')].find(node => node.getAttribute('aria-label') === label)
}

async function ready(host, label) {
  for (let i = 0; i < 20; i++) {
    await flush()
    const node = switchByLabel(host, label)
    if (node && !node.disabled) return node
  }
  throw new Error('switch did not finish loading: ' + label)
}

async function mount(Component, props) {
  const { createRoot } = require('react-dom/client')
  const host = document.createElement('div')
  document.body.appendChild(host)
  const root = createRoot(host)
  await act(async () => { root.render(h(Component, props)) })
  return {
    host,
    unmount: async () => {
      await act(async () => { root.unmount() })
      host.remove()
    },
  }
}

async function mountMain(templates = true) {
  const CreativeImport = loadStudio('CreativeImport.tsx', studioMocks(templates)).default
  const view = await mount(CreativeImport, { onImported: async () => {} })
  const node = await ready(view.host, MAIN)
  return { ...view, node }
}

async function mountSettings() {
  const view = await mount(captionsModule.default, {})
  const node = await ready(view.host, SETTINGS)
  return { ...view, node }
}

let gate = Promise.resolve()
function serial(name, fn) {
  test(name, async () => {
    const previous = gate
    let release
    gate = new Promise(resolve => { release = resolve })
    await previous
    const restore = await openDom()
    try {
      reset()
      await fn()
    } finally {
      closeDom(restore)
      release()
    }
  })
}

serial('toggling captions on the main page updates the shared setting and settings shows it, and the reverse', async () => {
  const main = await mountMain()
  assert.equal(main.node.getAttribute('aria-checked'), 'true')
  assert.equal(main.host.querySelector('.ac-row small').textContent, HINT)
  await act(async () => { main.node.click() })
  await flush()
  assert.deepEqual(state.writes, [false])
  assert.equal(state.enabled, false)
  assert.equal(switchByLabel(main.host, MAIN).getAttribute('aria-checked'), 'false')
  await main.unmount()

  const settings = await mountSettings()
  assert.equal(settings.node.getAttribute('aria-checked'), 'false')
  await act(async () => { settings.node.click() })
  await flush()
  assert.deepEqual(state.writes, [false, true])
  assert.equal(state.enabled, true)
  assert.equal(switchByLabel(settings.host, SETTINGS).getAttribute('aria-checked'), 'true')
  await settings.unmount()

  const again = await mountMain()
  assert.equal(again.node.getAttribute('aria-checked'), 'true')
  await again.unmount()
})

serial('a failed save keeps the shared value and shows the save error', async () => {
  state.failWrites = true
  const main = await mountMain(false)
  await act(async () => { main.node.click() })
  await flush()
  assert.deepEqual(state.writes, [false])
  assert.equal(state.enabled, true)
  assert.equal(switchByLabel(main.host, MAIN).getAttribute('aria-checked'), 'true')
  const alert = document.querySelector('[data-save-error]')
  assert.equal(alert?.textContent, SAVE_ERROR)
  await main.unmount()

  const settings = await mountSettings()
  assert.equal(settings.node.getAttribute('aria-checked'), 'true')
  await settings.unmount()
})

serial('the captions row sits below the editing style and above special requests', async () => {
  const main = await mountMain(true)
  const style = [...main.host.querySelectorAll('h2')].find(node => node.textContent === '剪辑风格')
  const row = [...main.host.querySelectorAll('.ac-row')].find(node => node.querySelector('b')?.textContent === MAIN)
  const details = main.host.querySelector('details')
  assert.ok(style && row && details)
  const after = window.Node.DOCUMENT_POSITION_FOLLOWING
  assert.equal(style.compareDocumentPosition(row) & after, after)
  assert.equal(row.compareDocumentPosition(details) & after, after)
  assert.equal(details.querySelector('summary').textContent, '有特别要求？（选填）')
  await main.unmount()

  const plain = await mountMain(false)
  assert.equal(plain.host.textContent.includes('剪辑风格'), false)
  const plainRow = [...plain.host.querySelectorAll('.ac-row')].find(node => node.querySelector('b')?.textContent === MAIN)
  const plainDetails = plain.host.querySelector('details')
  assert.equal(plainRow.compareDocumentPosition(plainDetails) & after, after)
  await plain.unmount()
})

test('the main-page captions hint exists in all eight locales', () => {
  for (const lang of LANGS) {
    const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    assert.ok(catalog[HINT], lang)
    assert.ok(catalog[MAIN], lang)
    if (lang !== 'zh') assert.notEqual(catalog[HINT], HINT, lang)
  }
})
