const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const React = require('react')
const { Dropdown } = require('antd')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

const SRC = path.join(__dirname, '../src')
const ATTEMPT = `t-${'a'.repeat(32)}`

function installGlobals(values) {
  const saved = Object.keys(values).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
  for (const [key, value] of Object.entries(values)) Object.defineProperty(globalThis, key, { value, writable: true, configurable: true, enumerable: true })
  return () => { for (const [key, descriptor] of saved) { if (descriptor) Object.defineProperty(globalThis, key, descriptor); else delete globalThis[key] } }
}

function resolveFile(fromFile, id) {
  const abs = path.resolve(path.dirname(fromFile), id)
  const files = [`${abs}.tsx`, `${abs}.ts`, `${abs}.json`]
  const file = files.find(candidate => fs.existsSync(candidate) && fs.statSync(candidate).isFile())
  if (file) return file
  if (fs.existsSync(abs) && fs.statSync(abs).isDirectory()) {
    return ['index.tsx', 'index.ts', 'index.json'].map(name => path.join(abs, name)).find(candidate => fs.existsSync(candidate))
  }
  if (fs.existsSync(abs) && fs.statSync(abs).isFile()) return abs
  return undefined
}

async function mount(entry, render) {
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/project/proj' })
  const submitted = []
  const diagnosticsApi = {
    preview: async () => ({
      manifest: { attempt: { attempt_id: ATTEMPT, error_code: 'timeout', failure_stage: 'analyze', sequence: 2 } },
      files: [],
      consent: { diagnostics: false, media: false, full_original: false },
      excerpt_limitation: '',
      not_for_training: true,
    }),
    submit: async (body) => { submitted.push(body); return { id: 'local-1', status: 'queued' } },
    getCase: async () => ({ id: 'local-1', status: 'saved_local', export_path: 'diagnostics-export-folder' }),
    remove: async () => ({ status: 'deleted' }),
  }
  const project = {
    id: 'proj', name: 'Example', status: 'failed', created_at: '2026-11-16T00:00:00Z',
    error_message: 'timeout', error_code: 'timeout', settings: {}, processing_config: {},
  }
  const api = {
    diagnosticsApi,
    projectApi: {
      getProject: async () => project,
      getProcessingStatus: async () => ({}),
      getClips: async () => [],
      getCollections: async () => [],
      startProcessing: async () => ({}),
      retryProcessing: async () => ({}),
      getClipVideoUrl: () => '',
      downloadVideo: async () => {},
    },
    speechApi: { getRuntimeStatus: async () => ({ status: 'installed' }) },
  }
  const empty = () => null
  const stubs = {
    'components/FeedbackDialog.tsx': { __esModule: true, default: empty },
    'features/studio/DiagnosePanel.tsx': { __esModule: true, default: empty },
    'features/studio/SwitchModelDialog.tsx': { __esModule: true, default: empty },
    'components/UnifiedStatusBar.tsx': { UnifiedStatusBar: empty },
    'features/studio/StudioResults.tsx': { __esModule: true, default: empty },
    'components/ClipCard.tsx': { __esModule: true, default: empty },
    'components/CollectionCard.tsx': { __esModule: true, default: empty },
    'components/CollectionPreviewModal.tsx': { __esModule: true, default: empty },
    'components/CreateCollectionModal.tsx': { __esModule: true, default: empty },
    'components/ProjectTaskManager.tsx': { ProjectTaskManager: empty },
    'components/LlmKeyFailureEmpty.tsx': { __esModule: true, default: empty },
    'components/SubtitleFailureEmpty.tsx': { __esModule: true, default: empty },
    'hooks/useCollectionVideoDownload.ts': { useCollectionVideoDownload: () => ({ generateAndDownloadCollectionVideo: async () => {} }) },
    'services/api.ts': api,
    'features/studio/api.ts': { studioApi: { retry: async () => ({}) }, errorText: () => '' },
    'i18n/index.ts': { t: (key) => key, getLocale: () => 'zh', languages: [] },
    'analytics/posthog.ts': { captureBusinessEvent() { return false }, isAnalyticsEnabled: () => false, onAnalyticsPreferenceChange() {} },
    'analytics/experience.ts': { trackExperience() {} },
    'analytics/observer.ts': { workflow: { context: () => ({}) } },
    'analytics/flags.ts': { flagAssigned: () => false, flagEnabled: () => false },
    'analytics/studio.ts': { trackLegacyEntry() {} },
  }
  const restore = installGlobals({
    window, document: window.document, navigator: window.navigator, localStorage: window.localStorage,
    HTMLElement: window.HTMLElement, Element: window.Element, Node: window.Node,
    SVGElement: window.SVGElement, ShadowRoot: window.ShadowRoot, MessageChannel: window.MessageChannel,
    getComputedStyle: window.getComputedStyle.bind(window), ResizeObserver: window.ResizeObserver,
    IS_REACT_ACT_ENVIRONMENT: true,
  })
  const cache = new Map()
  const load = (file) => {
    if (cache.has(file)) return cache.get(file)
    if (file.endsWith('.json')) {
      const data = JSON.parse(fs.readFileSync(file, 'utf8'))
      cache.set(file, data)
      return data
    }
    const exports = {}
    cache.set(file, exports)
    let output
    try {
      output = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
        fileName: file,
      }).outputText.replace(/import\.meta/g, 'globalThis.__importMeta')
    } catch (error) {
      throw new Error(`transpile ${path.relative(SRC, file)}: ${error.message}`)
    }
    const module = { exports }
    try {
    runInSandbox(output, {
      exports, module, window, document: window.document, navigator: window.navigator, localStorage: window.localStorage,
      __importMeta: { env: {}, url: 'file:///test' },
      console, Promise, setTimeout, clearTimeout, queueMicrotask, URL, URLSearchParams, AbortController,
      Event: window.Event, CustomEvent: window.CustomEvent, Date, Math, JSON, TextEncoder, TextDecoder,
      require: (id) => {
        if (id === 'react') return React
        if (id === 'react/jsx-runtime') return require('react/jsx-runtime')
        if (id === 'react-dom' || id === 'react-dom/client') return require(id)
        if (id === 'react-router-dom') return {
          useNavigate: () => () => {},
          useParams: () => ({ id: 'proj' }),
          useLocation: () => ({ pathname: '/project/proj', search: '' }),
          Navigate: () => null,
          Link: ({ children }) => React.createElement('a', null, children),
        }
        if (id === 'react-i18next') return { useTranslation: () => ({ t: (key) => key }) }
        if (id === 'antd') return {
          Dropdown,
          message: { success() {}, error() {}, warning() {}, info() {} },
          ConfigProvider: ({ children }) => React.createElement(React.Fragment, null, children),
        }
        if (id === '@event-catalog' || id === '@failure-messages' || id === '@provider-presets' || id === '@provider-quality') {
          const catalog = id === '@event-catalog' ? '../../backend/core/event_catalog.json'
            : id === '@failure-messages' ? '../../backend/core/failure_messages.json'
            : id === '@provider-presets' ? '../../backend/presets/provider_presets.json'
            : '../../backend/presets/provider_quality.json'
          const data = JSON.parse(fs.readFileSync(path.join(__dirname, catalog), 'utf8'))
          return { default: data, __esModule: true }
        }
        if (id.endsWith('.css')) return {}
        if (id.startsWith('.')) {
          const hit = resolveFile(file, id)
          if (!hit) throw new Error(`cannot resolve ${id} from ${file}`)
          const key = path.relative(SRC, hit)
          if (key in stubs) return stubs[key]
          return load(hit)
        }
        return require(id)
      },
    })
    } catch (error) {
      throw new Error(`run ${path.relative(SRC, file)}: ${error.message}`)
    }
    return module.exports
  }
  const Page = load(path.join(SRC, entry)).default
  const { createRoot } = require('react-dom/client')
  const host = window.document.createElement('div')
  window.document.body.appendChild(host)
  const root = createRoot(host)
  const settle = async () => { for (let i = 0; i < 6; i += 1) await React.act(async () => { await new Promise(resolve => setTimeout(resolve, 5)) }) }
  await React.act(async () => { root.render(render(Page, project)) })
  await settle()
  return {
    submitted, document: window.document, settle,
    close: async () => { try { await React.act(async () => { root.unmount() }) } finally { try { window.close() } finally { restore() } } },
  }
}

function button(document, label) {
  return [...document.querySelectorAll('button')].find(node => node.textContent === label)
}

async function submitFrom(entry, render) {
  const page = await mount(entry, render)
  try {
    const more = page.document.querySelector('button[aria-label="更多选项"]')
    if (more) {
      await React.act(async () => { more.click() })
      await page.settle()
    }
    const open = button(page.document, '提交诊断') || [...page.document.querySelectorAll('[role="menuitem"]')]
      .find(item => item.textContent === '提交诊断')
    assert.ok(open, `${entry} renders 提交诊断`)
    await React.act(async () => { open.click() })
    await page.settle()
    const submit = button(page.document, '我将对照清单再提交')
    assert.ok(submit, `${entry} opens the real dialog`)
    assert.equal(submit.disabled, false)
    await React.act(async () => { submit.click() })
    await page.settle()
    assert.equal(page.submitted.length, 1)
    assert.equal(page.submitted[0].project_id, 'proj')
    assert.equal(page.submitted[0].attempt_id, ATTEMPT)
    assert.equal(page.submitted[0].informed, true)
    assert.equal(page.submitted[0].save_local, false)
  } finally {
    await page.close()
  }
}

test('project card enables submit from the preview attempt and sends that id', async () => {
  await submitFrom('components/ProjectCard.tsx', (Card, project) => React.createElement(Card, { project, onDelete() {} }))
})

test('project detail enables submit from the preview attempt and sends that id', async () => {
  await submitFrom('pages/ProjectDetailPage.tsx', (Page) => React.createElement(Page))
})

test('saving locally displays the completed export path from the worker', async () => {
  const page = await mount('features/diagnostics/DiagnosticsDialog.tsx', (Dialog) =>
    React.createElement(Dialog, { open: true, onClose() {}, projectId: 'proj' }))
  try {
    await React.act(async () => { button(page.document, '保存到本机').click() })
    await page.settle()
    assert.equal(page.submitted[0].save_local, true)
    assert.match(page.document.body.textContent, /diagnostics-export-folder/)
  } finally {
    await page.close()
  }
})
