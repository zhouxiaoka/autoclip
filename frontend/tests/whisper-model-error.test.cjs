// Whisper download failure copy is chosen by errorCode and translated in 8 locales.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const KEY = 'Whisper 模型下载失败。请检查网络后到「设置 → 默认模型 → 语音转字幕」重新下载，或在下载源中改用 hf-mirror 镜像。'

test('errorCode selects translated copy; unknown code falls back to the server message', () => {
  const { whisperModelErrorText } = loadTs(path.join(__dirname, '../src/utils/whisperModelError.ts'))
  const t = s => `T(${s})`
  assert.equal(whisperModelErrorText(t, { errorCode: 'whisper_download_failed', errorMessage: 'raw' }), `T(${KEY})`)
  assert.equal(whisperModelErrorText(t, { errorCode: null, errorMessage: 'legacy text' }), 'legacy text')
  assert.equal(whisperModelErrorText(t, {}), '')
})

// mount the real SpeechRecognitionConfig in a DOM (happy-dom + react-dom/client), with
// its real state logic. Only the HTTP layer is mocked, with backend-shaped responses.
const React = require('react')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
// happy-dom is ESM-only; dynamic import works on Node 20 and 22 (require(esm) is not unflagged on every 22.x).
const loadWindow = async () => (await import('happy-dom')).Window
const LANGS = ['zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru']
const SOURCE = path.join(__dirname, '../src/components/SpeechRecognitionConfig.tsx')

function runtimeResponse() {
  return { status: 'installed', progress: 100, message: '', platform_supported: true, packages: ['faster-whisper'] }
}
function modelsResponse(errorCode) {
  // Shape of GET /whisper-models (backend/api/v1/speech_recognition.py).
  return ['tiny', 'base', 'small'].map(name => ({
    name, size: name === 'base' ? '142 MB' : '75 MB', sizeBytes: 1, description: '', accuracy: '', speed: '',
    status: name === 'base' ? 'error' : 'available', downloadProgress: 0, localPath: null,
    errorMessage: name === 'base' ? 'server raw text: HTTPSConnectionPool timed out' : null,
    errorCode: name === 'base' ? errorCode : null, source: 'huggingface',
  }))
}

async function mount(lang, errorCode, source = fs.readFileSync(SOURCE, 'utf8')) {
  const cat = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
  const t = (key, vars) => String(cat[key] || key).replace(/\{\{(\w+)\}\}/g, (_, k) => (vars || {})[k] ?? '')
  const Window = await loadWindow()
  const window = new Window({ url: 'http://localhost/' })
  // Node 21+ makes global.navigator a getter-only accessor, so plain assignment throws.
  // Swap the property descriptors and always restore them in finally.
  const restore = installGlobals({ window, document: window.document, navigator: window.navigator, IS_REACT_ACT_ENVIRONMENT: true })
  try {
  const h = React.createElement
  const ui = {
    Row: ({ label, hint, children }) => h('section', null, h('b', null, label), h('i', { className: 'hint' }, hint), children),
    Btn: ({ children }) => h('button', null, children), ProgressLine: () => null, StatusDot: () => null,
  }
  const calls = { runtime: 0, models: 0 }
  const speechApi = {
    getRuntimeStatus: async () => { calls.runtime++; return runtimeResponse() },
    getModels: async () => { calls.models++; return modelsResponse(errorCode) },
    getModelSource: async () => ({ source: 'auto', effective: 'huggingface' }),
  }
  const mocks = {
    react: React, 'react/jsx-runtime': require('react/jsx-runtime'),
    '../i18n': { t }, '../../i18n': { t }, 'react-i18next': { useTranslation: () => ({ t }) },
    antd: { Select: () => null, Popconfirm: ({ children }) => children, message: { error() {} } },
    '../services/api': { speechApi }, '../ui': ui, '../../ui': ui,
    '../utils/pipInstallError': loadTs(path.join(__dirname, '../src/utils/pipInstallError.ts')),
    '../utils/whisperModelError': loadTs(path.join(__dirname, '../src/utils/whisperModelError.ts')),
  }
  const load = (code, file) => {
    const exports = {}
    const out = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true }, fileName: file }).outputText
    runInSandbox(out, { exports, module: { exports }, window, console, Promise, setTimeout, clearTimeout, require: (id) => {
      if (id in mocks) return mocks[id]
      if (id === '../features/settings/LocalModelPrepare') return load(fs.readFileSync(path.join(__dirname, '../src/features/settings/LocalModelPrepare.tsx'), 'utf8'), 'LocalModelPrepare.tsx')
      throw new Error('Unexpected dependency: ' + id)
    } })
    return exports
  }
  const Component = load(source, SOURCE).default
  const { createRoot } = require('react-dom/client')
  const container = window.document.createElement('div')
  window.document.body.appendChild(container)
  const root = createRoot(container)
  await React.act(async () => { root.render(h(Component, { selectedModel: 'base' })) })
  // Wait for the real effect → Promise.all → setRuntime/setModels round trip to land.
  for (let i = 0; i < 50 && (calls.models === 0 || !container.textContent.includes('base · 142 MB') && container.querySelector('.hint') === null); i++) {
    await React.act(async () => { await new Promise(r => setTimeout(r, 5)) })
  }
  await React.act(async () => { await new Promise(r => setTimeout(r, 5)) })
  const hints = [...container.querySelectorAll('.hint')].map(n => n.textContent)
  await React.act(async () => { root.unmount() })
  return { hints, cat, calls }
  } finally {
    try { window.happyDOM.abort?.(); window.close() } finally { restore() }
  }
}

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

test('mount restores window/document/navigator exactly', async () => {
  const before = ['window', 'document', 'navigator'].map(k => Object.getOwnPropertyDescriptor(globalThis, k))
  await mount('en', 'whisper_download_failed')
  const after = ['window', 'document', 'navigator'].map(k => Object.getOwnPropertyDescriptor(globalThis, k))
  assert.deepEqual(after, before)
})

test('mounted SpeechRecognitionConfig shows the errorCode copy from loaded backend data in all eight locales', async () => {
  for (const lang of LANGS) {
    const { hints, cat, calls } = await mount(lang, 'whisper_download_failed')
    assert.ok(calls.runtime > 0 && calls.models > 0, lang + ': real data load must run')
    assert.ok(hints.includes(cat[KEY] || KEY), `${lang}: ${JSON.stringify(hints)}`)
    assert.ok(!hints.some(x => x.includes('server raw text')), lang)
  }
})

test('mounted SpeechRecognitionConfig falls back to the server text for an unknown errorCode', async () => {
  for (const lang of LANGS) {
    const { hints } = await mount(lang, 'something_new')
    assert.ok(hints.some(x => x.includes('server raw text')), `${lang}: ${JSON.stringify(hints)}`)
  }
})

test('sensitivity: breaking the received-model-list code makes the display assertion fail', async () => {
  const original = fs.readFileSync(SOURCE, 'utf8')
  const needle = 'setModels(Array.isArray(ms) ? ms : [])'
  assert.ok(original.includes(needle), 'component must store the received model list')
  const broken = original.replace(needle, 'setModels([])')
  const { hints, cat } = await mount('en', 'whisper_download_failed', broken)
  assert.ok(!hints.includes(cat[KEY]), 'with the model list dropped, the error copy cannot appear')
})

test('download failure copy exists in all eight locales', () => {
  for (const lang of ['zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru']) {
    const cat = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${lang}.json`), 'utf8'))
    assert.ok(cat[KEY], lang)
    if (lang !== 'zh') assert.notEqual(cat[KEY], KEY, lang)
  }
})
