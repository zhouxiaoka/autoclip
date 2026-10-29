const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')
const React = require('react')
const { act } = React
const { runInSandbox } = require('./vm-sandbox.cjs')
const { loadTs } = require('./load-ts.cjs')

const studio = path.resolve(__dirname, '../src/features/studio')
const langs = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']
const catalogs = Object.fromEntries(langs.map(lang => [lang, require('../src/i18n/locales/' + lang + '.json')]))
const recovery = loadTs(path.join(studio, 'browserCookieRecovery.ts'))

test('#481 recovery path stages only an http(s) link and names the import focus', () => {
  const store = new Map()
  const sessionStorage = {
    setItem: (key, value) => store.set(key, String(value)),
    getItem: key => store.has(key) ? store.get(key) : null,
    removeItem: key => store.delete(key),
  }
  const local = loadTs(path.join(studio, 'browserCookieRecovery.ts'), { __globals: { sessionStorage } })
  assert.equal(local.stageBrowserCookieRecovery('https://www.youtube.com/watch?v=abc'), '/?focus=browser-cookies')
  assert.equal(local.stagedRecoveryUrl(), 'https://www.youtube.com/watch?v=abc')
  assert.equal(local.stageBrowserCookieRecovery('javascript:alert(1)'), '/?focus=browser-cookies')
  assert.equal(local.stagedRecoveryUrl(), '')
  assert.equal(local.cookieAssistFromLocation('?focus=browser-cookies'), true)
  assert.equal(local.cookieAssistFromLocation('?focus=other'), false)
  assert.equal(local.browserCookieRecovery('source_blocked', 'anything'), true)
  assert.equal(local.browserCookieRecovery('file_locked', local.COOKIE_ACCESS_HINT), true)
  assert.equal(local.browserCookieRecovery('source_not_found', '找不到这个视频'), false)
})

test('#481 locked-browser hint matches the backend sentence and all eight catalogs', () => {
  const src = fs.readFileSync(path.resolve(__dirname, '../../backend/utils/download_recovery.py'), 'utf8')
  const hint = src.match(/^COOKIE_ACCESS_HINT = '([^']+)'$/m)[1]
  assert.equal(hint, recovery.COOKIE_ACCESS_HINT)
  assert.match(hint, /完全退出/)
  assert.match(hint, /换一个已登录的浏览器/)
  const keys = [
    hint,
    '下一步：回到导入，选择一个已登录的浏览器后再生成。',
    '选择已登录的浏览器',
    '还没有选择浏览器。选一个已登录的浏览器后再生成。这个浏览器如果正开着，请先完全退出，或换一个浏览器。',
  ]
  for (const key of keys) {
    for (const lang of langs) {
      assert.ok(catalogs[lang][key], lang + ' ' + key)
      if (lang !== 'zh') assert.notEqual(catalogs[lang][key], key, lang + ' ' + key)
    }
  }
})

function loadStudio(file, mocks, sandbox) {
  const abs = path.join(studio, file)
  const { outputText } = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
    fileName: abs,
  })
  const exports = {}
  const req = id => {
    if (id === './ImportSetupCard') return { default: () => null }
    if (id in mocks) return mocks[id]
    if (id === 'react' || id === 'react/jsx-runtime') return require(id)
    if (id.startsWith('./')) {
      const stem = id.slice(2)
      const ext = fs.existsSync(path.join(studio, stem + '.tsx')) ? '.tsx' : '.ts'
      return loadStudio(stem + ext, mocks, sandbox)
    }
    throw new Error('unexpected import ' + id)
  }
  runInSandbox(outputText, { exports, require: req, console, ...sandbox })
  return exports
}

async function withWindow(url, run) {
  const { Window } = require('happy-dom')
  const window = new Window({ url })
  const previous = {
    window: globalThis.window, document: globalThis.document, navigator: globalThis.navigator,
    HTMLElement: globalThis.HTMLElement, IS_REACT_ACT_ENVIRONMENT: globalThis.IS_REACT_ACT_ENVIRONMENT,
  }
  globalThis.window = window
  globalThis.document = window.document
  globalThis.navigator = window.navigator
  globalThis.HTMLElement = window.HTMLElement
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  try {
    await run(window)
  } finally {
    window.happyDOM.abort?.()
    window.close()
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete globalThis[key]
      else globalThis[key] = value
    }
  }
}

test('#481 import expands the browser picker and keeps the chosen browser on submit', async () => {
  await withWindow('http://localhost/?focus=browser-cookies', async window => {
    window.sessionStorage.setItem('autoclip.browserCookieRecoveryUrl', 'https://www.youtube.com/watch?v=abc')
    const { createRoot } = require('react-dom/client')
    const calls = []
    const ready = { analysis_mode: 'auto', ready: true, checks: { analysis: { ok: true, code: 'ok', repair: 'none' }, transcription: { ok: true, code: 'ok', repair: 'none' }, visual: { ok: true, code: 'ok', repair: 'none' }, ffmpeg: { ok: true, code: 'ok', repair: 'none' } } }
    const h = React.createElement
    const mocks = {
      'react-i18next': { useTranslation() {} },
      '../../i18n': { t: value => value, getLocale: () => 'zh-CN' },
      antd: { Select: () => null },
      'react-router-dom': { useNavigate: () => () => {} },
      '../../ui': {
        Btn: ({ children, onClick, variant }) => h('button', { type: 'button', onClick, 'data-variant': variant || '' }, children),
        Segmented: () => null,
        Dialog: ({ open, children }) => open ? h('div', { role: 'dialog' }, children) : null,
        StatusDot: () => null,
      },
      './PlatformPicker': { default: () => null },
      './api': {
        studioApi: { readiness: async () => ready, readinessProbe: async () => ready, import: async body => { calls.push(body); return { project_id: 'p' } } },
        errorText: value => String(value),
        errorCode: () => undefined,
      },
      '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
      '../../analytics/workflow': { telemetryId: () => 't-cookie' },
      '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
      '../../analytics/experience': { trackExperience() {} },
      './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
      './StyleProbeLine': { default: () => null },
      './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
      './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
      './ImportPreferences': { default: () => null },
      '../../services/api': { speechApi: {} },
      './platformLabel': { platformLabel: id => id },
      './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
      './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: () => null, isVideoFile: () => false, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000 },
      './importPreferencesStore': { readImportPreferences: () => null },
      './TranscriptionGatePrompt': { default: () => null },
      './transcriptionRecovery': { isRecoveryCode: () => false, probeConfig: () => ({}) },
      './useTranscriptionRecovery': { useTranscriptionRecovery: () => [{ phase: 'idle', percent: null }, { open() {}, close() {}, install: async () => {}, retry: async () => {} }] },
      './settingsReturn': { SETTINGS_SAVED_EVENT: 'autoclip:model-settings-saved' },
      '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
      './studio.css': {}, './quick-output.css': {},
    }
    const sandbox = {
      window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement,
      FormData: window.FormData, URL: window.URL, sessionStorage: window.sessionStorage,
      Promise, setTimeout, clearTimeout, queueMicrotask,
    }
    const CreativeImport = loadStudio('CreativeImport.tsx', mocks, sandbox).default
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(h(CreativeImport, { onImported: async () => {} })) })
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
    const select = host.querySelector('#studio-browser-cookie')
    assert.ok(select, 'the browser picker is on the import form')
    assert.equal(select.closest('details').open, true)
    assert.equal(host.querySelector('textarea').value, 'https://www.youtube.com/watch?v=abc')
    assert.match(host.textContent, /还没有选择浏览器/)
    assert.equal(host.querySelector('[role="dialog"]'), null)
    const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set
    await act(async () => {
      setter.call(select, 'edge')
      select.dispatchEvent(new window.Event('change', { bubbles: true }))
    })
    const start = [...host.querySelectorAll('button')].find(button => button.textContent === '生成成片')
    await act(async () => { start.click() })
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)) })
    assert.equal(calls.length, 1)
    assert.equal(calls[0].get('browser'), 'edge')
    assert.equal(calls[0].get('url'), 'https://www.youtube.com/watch?v=abc')
    await act(async () => { root.unmount() })
  })
})

test('#481 a normal import keeps the browser picker inside the closed preferences dialog', async () => {
  await withWindow('http://localhost/', async window => {
    const { createRoot } = require('react-dom/client')
    const h = React.createElement
    const ready = { analysis_mode: 'auto', ready: true, checks: { analysis: { ok: true }, transcription: { ok: true }, visual: { ok: true }, ffmpeg: { ok: true } } }
    const mocks = {
      'react-i18next': { useTranslation() {} },
      '../../i18n': { t: value => value, getLocale: () => 'zh-CN' },
      antd: { Select: () => null },
      'react-router-dom': { useNavigate: () => () => {} },
      '../../ui': {
        Btn: ({ children, onClick }) => h('button', { type: 'button', onClick }, children),
        Segmented: () => null,
        Dialog: ({ open, children }) => open ? h('div', { role: 'dialog' }, children) : null,
        StatusDot: () => null,
      },
      './PlatformPicker': { default: () => null },
      './api': { studioApi: { readiness: async () => ready, readinessProbe: async () => ready, import: async () => ({ project_id: 'p' }) }, errorText: String, errorCode: () => undefined },
      '../../analytics/studio': { trackQuickOutputPlatforms() {}, trackAsrReadiness() {}, trackOneClickStarted() {}, trackOneClickUndone() {}, trackAutoChoiceOverridden() {} },
      '../../analytics/workflow': { telemetryId: () => 't-cookie' },
      '../../analytics/flags': { useFlag: () => false, flagEnabled: () => false, flagValue: () => 'button', flagAssigned: () => false, featureSnapshot: () => ({}) },
      '../../analytics/experience': { trackExperience() {} },
      './TemplatePicker': { default: () => null, templateImportFields: () => ({}) },
      './StyleProbeLine': { default: () => null },
      './editingStyleSession': { readStyle: () => ({ key: '', result: null }) },
      './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
      './ImportPreferences': { default: () => null },
      '../../services/api': { speechApi: {} },
      './platformLabel': { platformLabel: id => id },
      './platformMemory': { readRememberedPlatforms: () => null, resolvePlatforms: () => ({ platforms: ['douyin'], source: 'user' }), samePlatforms: () => true, writeRememberedPlatforms() {} },
      './pasteStart': { claimBackgroundWhisperInstall: () => false, importUrlKind: () => null, isVideoFile: () => false, shouldAutoStart: () => false, shouldBackgroundInstallWhisper: () => false, UNDO_MS: 3000 },
      './importPreferencesStore': { readImportPreferences: () => null },
      './TranscriptionGatePrompt': { default: () => null },
      './transcriptionRecovery': { isRecoveryCode: () => false, probeConfig: () => ({}) },
      './useTranscriptionRecovery': { useTranscriptionRecovery: () => [{ phase: 'idle', percent: null }, { open() {}, close() {}, install: async () => {}, retry: async () => {} }] },
      './settingsReturn': { SETTINGS_SAVED_EVENT: 'autoclip:model-settings-saved' },
      '../settings/OutputCaptionsSetting': { OutputCaptionsSwitch: () => null },
      './studio.css': {}, './quick-output.css': {},
    }
    const sandbox = { window, document: window.document, navigator: window.navigator, HTMLElement: window.HTMLElement, FormData: window.FormData, URL: window.URL, sessionStorage: window.sessionStorage, Promise, setTimeout, clearTimeout }
    const CreativeImport = loadStudio('CreativeImport.tsx', mocks, sandbox).default
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)
    await act(async () => { root.render(h(CreativeImport, { onImported: async () => {} })) })
    assert.equal(host.querySelector('#studio-browser-cookie'), null)
    assert.equal(host.querySelector('[role="dialog"]'), null)
    await act(async () => { root.unmount() })
  })
})

test('#481 import review uses the same browser action for source_blocked', () => {
  const navigations = []
  const buttons = []
  const hint = '这个视频当前无法访问'
  const mocks = {
    'react-i18next': { useTranslation() {} },
    '../../i18n': { t: value => value },
    'react-router-dom': { useNavigate: () => to => navigations.push(to), useParams: () => ({ id: 'p1' }) },
    '../../ui': { Btn: props => { buttons.push(props); return React.createElement('button', null, props.children) } },
    './useWorkspace': { useWorkspace: () => ({ workspace: { analysis: { status: 'failed', error_code: 'source_blocked', error: hint }, plan: null, drafts: [], events: [], jobs: [] }, error: '', refresh() {} }) },
    './api': { studioApi: {}, errorText: String },
    './PlanSummary': { default: () => null },
    './importReadiness': loadTs(path.join(studio, 'importReadiness.ts')),
    './browserCookieRecovery': recovery,
    './failureAction': loadTs(path.join(studio, 'failureAction.ts')),
    './types': { defaultImportOptions: { goal: 'auto', language: 'source', aspect: null, duration: null, instruction: '' } },
    './studio.css': {},
  }
  const exports = loadStudio('ImportReview.tsx', mocks, { URLSearchParams })
  const { renderToStaticMarkup } = require('react-dom/server')
  const html = renderToStaticMarkup(React.createElement(exports.default))
  assert.match(html, /下一步：回到导入/)
  assert.ok(html.includes(hint))
  const go = buttons.find(button => button.children === '选择已登录的浏览器')
  assert.equal(go.variant, 'cta')
  go.onClick()
  assert.deepEqual(navigations, ['/?focus=browser-cookies'])
  assert.equal(buttons.some(button => button.children === '重新识别' || button.children === '模型设置'), false)
})
