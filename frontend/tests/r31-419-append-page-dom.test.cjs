// R31 #419 Dong addition 2 (round 31 review): rendering-level proof, replacing the StudioResults source-text regexes.
// The real StudioResults page is mounted in happy-dom with react-dom/client, together with its real data hook
// (useWorkspace + pollWorkspace), the real failure UI (FailureActions, failureAction, llmFailure, settingsReturn) and
// the real tracker singleton from analytics/observer.ts driven by the real startWorkflowObserver poll. Only the HTTP
// layer (studioApi.get / axios.get) and leaf UI modules are stubbed; both HTTP stubs serve one backend-shaped state.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')
const React = require('react')
const SRC = path.resolve(__dirname, '../src')
const PAGE = path.join(SRC, 'features/studio/StudioResults.tsx')

const A = 't-aaaaaaaaaaaaaaaa', OLD = 't-0000000000000000', RUN = 'r'.repeat(32), RUN1 = 'q'.repeat(32)
const variant = { id: 'v1', strategy_id: 'douyin', status: 'completed', draft_id: 'd1', render_job_id: 'j1' }     // round 1's output
const round1 = { attempt_id: OLD, flow_id: 't-f1f1f1f1f1f1f1f1', sequence: 1, kind: 'generation', trigger: 'initial', state: 'completed', run_id: RUN1, causes: [], summary: { duration_ms: 900 } }
const append = { attempt_id: A, flow_id: 't-f1f1f1f1f1f1f1f1', sequence: 2, kind: 'generation', trigger: 'retry', retry_of: OLD, state: 'open', run_id: RUN, causes: [], summary: {} }
// What the workspace GET returns while the append is preparing (the append response itself was lost).
const openSnapshot = () => ({ material_origin: 'user', drafts: [], events: [], jobs: [], output_variants: [variant],
  generation: { status: 'running', auto_start: true, attempt_id: A, branding: { outro_enabled: true } },
  analysis: { status: 'completed', phase: 'production', run_id: RUN }, attempts: [round1, append] })
// After preparation failed (_fail_generation + attempts.settle): the analysis record mirrors the primary cause only;
// the settled receipt bound to the same run carries the ranked structured causes, here a vision key problem second.
const failedSnapshot = (receiptRun = RUN) => ({ ...openSnapshot(),
  generation: { status: 'failed', auto_start: true, attempt_id: A, error_code: 'rate_limited', failure_stage: 'production', upstream_error_type: 'rate_limited', http_status: 429, branding: { outro_enabled: true } },
  analysis: { status: 'failed', phase: 'production', run_id: RUN, error: 'provider said: secret-ish raw text', error_code: 'rate_limited', failure_stage: 'production', upstream_error_type: 'rate_limited', http_status: 429, duration_ms: 1200 },
  attempts: [round1, { ...append, state: 'failed', run_id: receiptRun, error_code: 'rate_limited', summary: { duration_ms: 1200 },
    causes: [{ goal: null, stage: 'production', code: 'rate_limited', upstream: 'rate_limited' }, { goal: null, stage: 'vision', code: 'invalid_key', upstream: 'invalid_key' }] }] })

function installGlobals(values) {
  const saved = Object.keys(values).map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
  for (const [key, value] of Object.entries(values)) Object.defineProperty(globalThis, key, { value, writable: true, configurable: true, enumerable: true })
  return () => { for (const [key, d] of saved) { if (d) Object.defineProperty(globalThis, key, d); else delete globalThis[key] } }
}

/** Mount the page; `server.state` is what both GET /studio/p1 paths return. `override` replaces a source file's text (mutations). */
async function mount(server, override = {}) {
  const { Window } = await import('happy-dom')
  const window = new Window({ url: 'http://localhost/project/p1' })
  const restore = installGlobals({ window, document: window.document, navigator: window.navigator, IS_REACT_ACT_ENVIRONMENT: true })
  const h = React.createElement
  const empty = () => null
  const t = (key, vars) => String(key).replace(/\{\{(\w+)\}\}/g, (_, k) => (vars || {})[k] ?? '')
  const events = [], navigations = [], gets = { page: 0, observer: [] }
  const Btn = ({ children, onClick, disabled, variant: v }) => h('button', { onClick, disabled, 'data-variant': v || '' }, children)
  const external = {
    react: React, 'react/jsx-runtime': require('react/jsx-runtime'),
    'react-i18next': { useTranslation: () => ({ t }) },
    'react-router-dom': { useNavigate: () => to => navigations.push(to), useLocation: () => ({ search: '' }) },
    axios: { __esModule: true, default: { get: async url => { gets.observer.push(url); return { data: JSON.parse(JSON.stringify(server.state)) } } } },
  }
  const stubs = {
    'i18n': { t }, 'ui': { Btn, Section: ({ title, description, right, children }) => h('section', null, h('h2', null, title), h('p', { className: 'desc' }, description), right, children), Dialog: empty, fmtDuration: String },
    'features/studio/api': { studioApi: { get: async () => { gets.page++; return JSON.parse(JSON.stringify(server.state)) }, source: () => '' }, errorText: String },
    'features/studio/ExportHistory': { __esModule: true, default: empty }, 'features/studio/DraftResultCard': { __esModule: true, default: empty },
    'features/studio/OutputVariantCard': { __esModule: true, default: empty }, 'features/studio/PlatformPicker': { __esModule: true, default: empty },
    'features/studio/noticeRuntime': { clearCompletionBadge: async () => {}, subscribeCompletionNotice: () => () => {}, noteWorkspaceCompletion() {} },
    'features/studio/overrides': { followOutputLeave: () => () => {} },
    'analytics/flags': { flagEnabled: () => false, flagAssigned: () => false },
    'analytics/studio': { trackLegacyEntry() {} },
    'analytics/posthog': { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true }, isAnalyticsEnabled: () => true, onAnalyticsPreferenceChange() {} },
    'utils/apiConfig': { apiConfigManager: { isReady: () => true, getBaseUrl: () => '' } },
  }
  const cache = new Map()
  const load = file => {
    if (cache.has(file)) return cache.get(file)
    const exports = {}
    cache.set(file, exports)
    const code = override[path.relative(SRC, file)] ?? fs.readFileSync(file, 'utf8')
    const out = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true }, fileName: file }).outputText
    runInSandbox(out, { exports, module: { exports }, window, document: window.document, localStorage: window.localStorage, console, Promise,
      setTimeout, clearTimeout, URL, URLSearchParams, AbortController, Event: window.Event, Date, Math, JSON,
      require: id => {
        if (id in external) return external[id]
        if (/\.css$/.test(id)) return {}
        if (id === '@event-catalog' || id === '@failure-messages') {
          const data = JSON.parse(fs.readFileSync(path.join(__dirname, id === '@event-catalog' ? '../../backend/core/event_catalog.json' : '../../backend/core/failure_messages.json'), 'utf8'))
          return { default: data, __esModule: true }
        }
        if (!id.startsWith('.')) throw new Error('Unexpected dependency: ' + id)
        const abs = path.resolve(path.dirname(file), id), key = path.relative(SRC, abs)
        if (key in stubs) return stubs[key]
        const hit = ['.ts', '.tsx'].map(ext => abs + ext).find(f => fs.existsSync(f))
        if (!hit) throw new Error('Unresolved: ' + id)
        return load(hit)
      } })
    return exports
  }
  const observer = load(path.join(SRC, 'analytics/observer.ts'))
  const Page = load(PAGE).default
  const { createRoot } = require('react-dom/client')
  const container = window.document.createElement('div')
  window.document.body.appendChild(container)
  const root = createRoot(container)
  const settle = async () => { for (let i = 0; i < 5; i++) await React.act(async () => { await new Promise(r => setTimeout(r, 2)) }) }
  await React.act(async () => { root.render(h(Page, { project: { id: 'p1', status: 'completed', settings: { smart_import: {} }, clips: [], collections: [] }, onCreateCollection() {}, onReload() {} })) })
  await settle()
  return {
    container, events, navigations, gets, tracker: observer.workflow, storage: window.localStorage, settle,
    /** One run of the real observer poll (startWorkflowObserver polls once immediately). */
    pollObserver: async () => { const stop = observer.startWorkflowObserver(); await settle(); stop() },
    /** The page refetches on window focus (useWorkspace). */
    refocus: async () => { await React.act(async () => { window.dispatchEvent(new window.Event('focus')) }); await settle() },
    close: async () => { try { await React.act(async () => { root.unmount() }) } finally { try { window.happyDOM.abort?.(); window.close() } finally { restore() } } },
  }
}

const finished = events => events.filter(e => e.event === 'studio_generation_finished')
const settingsButton = container => [...container.querySelectorAll('button')].find(b => b.textContent === '去设置')

async function pageFlow(override) {
  const server = { state: openSnapshot() }
  const page = await mount(server, override)
  try {
    const result = { gets: page.gets.page }
    // (a) the open retry attempt from the snapshot is adopted: a persisted generation watch bound to its attempt id.
    result.watches = page.tracker.list().map(w => ({ kind: w.kind, attemptId: w.attemptId, settled: !!w.settled }))
    result.persisted = JSON.stringify(Object.fromEntries(Array.from({ length: page.storage.length }, (_, i) => page.storage.key(i)).map(k => [k, page.storage.getItem(k)]))).includes(A)
    await page.pollObserver()                             // the observer watches it: GET /studio/p1 while still open
    result.observedWhileOpen = [...page.gets.observer]
    result.finishedWhileOpen = finished(page.events).length
    server.state = failedSnapshot()
    await page.pollObserver()
    await page.pollObserver()                             // a second poll must not report it again
    result.finished = finished(page.events).map(e => ({ attempt_id: e.props.attempt_id, trigger: e.props.trigger, outcome: e.props.outcome }))
    // (b) the page shows the failure of this run.
    await page.refocus()
    result.text = page.container.textContent
    const button = settingsButton(page.container)
    result.hasSettings = !!button
    if (button) { await React.act(async () => { button.click() }); result.navigations = [...page.navigations] }
    return JSON.parse(JSON.stringify(result))                 // plain test-realm values (the tracker lives in a vm realm)
  } finally { await page.close() }
}

test('retry page (DOM): the mounted page adopts the open retry attempt, the observer watches it to one terminal, and the failure leads to its settings fix', async () => {
  const r = await pageFlow()
  assert.ok(r.gets > 0, 'the page loaded the workspace through its real data hook')
  assert.deepEqual(r.watches, [{ kind: 'studio-generation', attemptId: A, settled: false }])          // (a) adopted from the snapshot
  assert.ok(r.persisted, '(a) the adopted watch is persisted, so a reload keeps watching it')
  assert.deepEqual(r.observedWhileOpen, ['/studio/p1'])                                                   // (a) the observer polls it
  assert.equal(r.finishedWhileOpen, 0)
  assert.deepEqual(r.finished, [])
  assert.ok(!r.text.includes('追加平台'), 'no append-platform entry on the page')
  assert.ok(r.text.includes('这次制作未完成'), '(b) failure block rendered')
  assert.ok(r.text.includes('API Key 无效或已过期，请到设置里更新后再试'), '(b) the cause from the receipt of run_id ' + RUN)
  assert.ok(!r.text.includes('secret-ish raw text'), '(b) never the raw upstream text')
  assert.ok(r.hasSettings, '(b) the page offers 「去设置」')
  assert.deepEqual(r.navigations, ['/settings?section=vision&return_project=p1'])                       // (b) the vision key row, back to p1
})

test('R31 addition 2 (DOM): a settled receipt of another run is not shown for this failure (looked up by run_id)', async () => {
  const server = { state: failedSnapshot('s'.repeat(32)) }
  const page = await mount(server)
  try {
    const text = page.container.textContent
    assert.ok(text.includes('这次制作未完成'))
    assert.ok(!text.includes('API Key 无效或已过期'), 'the receipt of another run must not supply the cause')
    assert.equal(settingsButton(page.container), undefined, 'the analysis primary (rate_limited) is a retry, not a settings fix')
  } finally { await page.close() }
})

module.exports = { pageFlow, mount, failedSnapshot, PAGE }
