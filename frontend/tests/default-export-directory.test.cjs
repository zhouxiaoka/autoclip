const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const React = require('react')
const { loadTs } = require('./load-ts.cjs')
const { runInSandbox } = require('./vm-sandbox.cjs')
const h = React.createElement, { act } = React
let saved = null, calls = [], chooseResult, fail = '', gate, dom
const fallback = '/isolated/Downloads'
const current = () => ({ configuredPath: saved, effectivePath: saved || fallback })
async function invoke(command, args) {
  calls.push({ command, args })
  if (command === 'is_autostart_enabled') return false
  if (fail) throw new Error(fail)
  if (command === 'choose_export_directory') {
    if (gate) await gate
    if (chooseResult !== null) saved = chooseResult
  } else if (command === 'reset_export_directory') saved = null
  else assert.equal(command, 'get_export_directory')
  return current()
}
function Row({ label, hint, children }) { return h('section', null, h('h3', null, label), h('small', null, hint), children) }
const Btn = ({ children, disabled, loading, onClick }) => h('button', { disabled: !!(disabled || loading), onClick }, children)
function mocks() {
  return {
    __globals: { window: dom, document: dom.document, HTMLElement: dom.HTMLElement, Promise },
    'react-i18next': { useTranslation() {} },
    '@tauri-apps/api/core': { invoke },
    '../../i18n': { t: key => key }, '../i18n': { t: key => key },
    '../../ui': { Row, Btn }, '../ui': { Row, Btn, Section: ({ children }) => h('div', null, children), Segmented: () => null, Icon: {} },
    antd: { Switch: () => null, message: { info() {}, warning() {}, error() {}, success() {} } },
  }
}
function setting() { return loadTs('ExportDirectorySetting.tsx', mocks()).default }
function appSection() {
  const nil = { default: () => null }
  const table = {
    ...mocks(),
    '../analytics/experience': { trackExperience() {} },
    'react-router-dom': { useLocation: () => ({ search: '', state: null }), useNavigate: () => () => {} },
    '../services/api': { settingsApi: { getPrivacy: async () => ({ crash_reports: false }) }, diagnosticsApi: { consent: async () => ({ diagnostics: false, media: false, full_original: false }) } },
    '../features/settings/AIModelSettings': nil, '../features/settings/OutputBrandingSetting': nil,
    '../features/settings/OutputCaptionsSetting': nil, '../components/FeedbackDialog': nil,
    '../components/PublishSettings': nil, '../utils/desktopMode': { isDesktopMode: async () => true },
    '../utils/externalLinks': { openExternalLink() {} }, '../analytics/posthog': { isAnalyticsEnabled: () => false, setAnalyticsEnabled() {} },
    '../analytics/lifecycle': { getRuntimeInfo: () => ({ version: '1.6.0' }) },
    '../desktop/sentry': { isCrashReportsEnabled: () => false, setCrashReportsEnabled() {} },
    '../features/studio/keepAwake': { isKeepAwakeEnabled: () => false, getKeepAwakeController: () => ({ onEnabledChange() {} }) },
    '../desktop/updater': { getAppVersion: async () => '1.6.0' },
    '../desktop/UpdatePrompt': { useAppUpdate: () => ({ phase: 'idle', preview: false }) },
    '../analytics/feedback': { FEEDBACK_DISCUSSIONS_URL: '', FEEDBACK_ISSUES_URL: '' },
    '../context/ThemeContext': { useTheme: () => ({ theme: 'light', setTheme() {} }) },
    '../features/settings/FlagOverrides': { ...nil, flagOverridesVisible: () => false },
    '../features/settings/ObsSettings': nil, '../features/settings/ImportPreferenceSettings': nil,
    '../features/settings/ExportDirectorySetting': { default: setting() },
  }
  const file = path.resolve(__dirname, '../src/pages/SettingsPage.tsx')
  const output = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX } }).outputText
  const exports = {}
  runInSandbox(output + '\nexports.AppSection = AppSection;', { exports, console, ...table.__globals, require: id => {
    if (id in table) return table[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    throw new Error('Unmocked import ' + id)
  } })
  return exports.AppSection
}
async function open() {
  const Window = (await import('happy-dom')).Window
  dom = new Window({ url: 'http://localhost/' })
  const previous = {}
  for (const [key, value] of Object.entries({ window: dom, document: dom.document, navigator: dom.navigator, HTMLElement: dom.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true })) {
    previous[key] = Object.getOwnPropertyDescriptor(globalThis, key)
    Object.defineProperty(globalThis, key, { value, writable: true, configurable: true })
  }
  return () => {
    dom.happyDOM.abort(); dom.close()
    for (const [key, descriptor] of Object.entries(previous)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
}
async function flush() { await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) }) }
async function mount(Component, props = {}) {
  const host = document.createElement('div'); document.body.append(host)
  const root = require('react-dom/client').createRoot(host)
  await act(async () => root.render(h(Component, props))); await flush()
  return { host, root, close: async () => { await act(async () => root.unmount()); host.remove() } }
}
function button(host, name) { return [...host.querySelectorAll('button')].find(node => node.textContent === name) }
async function click(node) { assert.ok(node); await act(async () => node.click()); await flush() }
function reset() { saved = null; calls = []; chooseResult = '/isolated/成片 folder'; fail = ''; gate = null }

test('application settings exposes the native default export folder control', async () => {
  const closeDom = await open(); reset(); let ui
  try {
    ui = await mount(appSection(), { analyticsOn: false, onAnalyticsChange() {} }); await flush()
    assert.ok(button(ui.host, 'exportFolder.choose'), 'actual app settings must expose the new control')
    await click(button(ui.host, 'exportFolder.choose'))
    assert.equal(ui.host.querySelector('[data-testid="export-directory-path"]').textContent, saved)
    assert.ok(calls.some(call => call.command === 'choose_export_directory'))
  } finally { await ui?.close(); closeDom() }
})

test('selection is reread after remount; cancelling and resetting preserve native semantics', async () => {
  const closeDom = await open(); reset(); let ui
  try {
    const Component = setting(); ui = await mount(Component, { desktop: true })
    await click(button(ui.host, 'exportFolder.choose')); const chosen = saved
    await ui.close(); ui = await mount(Component, { desktop: true })
    assert.equal(ui.host.querySelector('[data-testid="export-directory-path"]').textContent, chosen)
    chooseResult = null; await click(button(ui.host, 'exportFolder.choose'))
    assert.equal(saved, chosen)
    await click(button(ui.host, 'exportFolder.reset'))
    assert.equal(saved, null); assert.equal(ui.host.querySelector('[data-testid="export-directory-path"]').textContent, fallback)
    assert.ok(calls.every(call => call.args === undefined), 'webview must not submit a target directory')
  } finally { await ui?.close(); closeDom() }
})

test('failed native preference write keeps the previous displayed folder and hides raw error paths', async () => {
  const closeDom = await open(); reset(); saved = '/isolated/previous'; let ui
  try {
    ui = await mount(setting(), { desktop: true }); fail = 'disk failure PRIVATE-FAILED-PATH'
    await click(button(ui.host, 'exportFolder.choose'))
    assert.equal(ui.host.querySelector('[data-testid="export-directory-path"]').textContent, '/isolated/previous')
    assert.equal(ui.host.querySelector('[role="alert"]').textContent, 'exportFolder.saveError')
    assert.ok(!ui.host.textContent.includes('PRIVATE-FAILED-PATH'))
  } finally { await ui?.close(); closeDom() }
})

test('rapid clicks cannot open duplicate pickers or reset during a pending selection', async () => {
  const closeDom = await open(); reset(); let release, ui
  gate = new Promise(resolve => { release = resolve })
  try {
    ui = await mount(setting(), { desktop: true }); const select = button(ui.host, 'exportFolder.choose')
    await act(async () => { select.click(); select.click() }); await flush()
    assert.equal(calls.filter(call => call.command === 'choose_export_directory').length, 1)
    assert.equal(button(ui.host, 'exportFolder.reset').disabled, true)
    release(); await flush(); await flush()
  } finally { release?.(); await ui?.close(); closeDom() }
})

test('browser settings do not invoke native directory commands', async () => {
  const closeDom = await open(); reset(); let ui
  try {
    ui = await mount(setting(), { desktop: false })
    assert.equal(ui.host.querySelectorAll('button').length, 0)
    assert.equal(calls.length, 0); assert.ok(ui.host.textContent.includes('exportFolder.browser'))
  } finally { await ui?.close(); closeDom() }
})
