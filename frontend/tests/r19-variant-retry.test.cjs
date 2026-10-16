// R19 #108: partial page 「重试这条」 -> real StudioResults onRetry -> real studioApi -> real tracker.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { loadTs } = require('./load-ts.cjs')

function setup() {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const tracker = new workflow.WorkflowTracker({ getItem: () => null, setItem() {}, removeItem() {} },
    () => true, (event, props) => { events.push({ event, props }); return true })
  const posts = []
  const api = loadTs(path.resolve(__dirname, '../src/features/studio/api.ts'), {
    '../../analytics/posthog': { captureBusinessEvent() {} },
    '../../analytics/workflow': workflow,
    '../../analytics/studio': {
      observeStudioOperation: async (_n, action, accepted = () => {}, props = {}) => { const r = await action(); accepted(r, { ...props }); return r },
      studioImportProperties: () => ({}), studioGoals: () => ({}), observeStudioWorkspace: () => {},
    },
    '../../analytics/observer': { workflow: tracker },
    '../../services/api': { default: { defaults: { baseURL: '' }, post: async (url) => { posts.push(url); return { job_id: 'job-2' } }, put: async () => ({}), get: async () => ({}) }, __esModule: true },
    './noticeRuntime': { noteWorkspaceCompletion() {} },
    './subtitleState': { effectiveSubtitles: x => x },
  })
  return { tracker, events, posts, studioApi: api.studioApi }
}

function renderResults(workspace, studioApi, cards) {
  const empty = () => null
  const moduleRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name)
    if (name === 'react-i18next') return { useTranslation() {} }
    if (name === 'react-router-dom') return { useNavigate: () => () => {} }
    if (name === '../../i18n') return { t: v => v }
    if (name === '../../ui') return { Btn: p => React.createElement('button', null, p.children), Section: ({ children }) => React.createElement('section', null, children), Dialog: empty, fmtDuration: String }
    if (name === './useWorkspace') return { useWorkspace: () => ({ workspace, loaded: true, loading: false, refresh() {} }) }
    if (name === './api') return { studioApi, errorText: String }
    if (name === './OutputVariantCard') return { default: props => { cards.push(props); return null } }
    if (name === '../../utils/llmFailure') return loadTs(path.resolve(__dirname, '../src/utils/llmFailure.ts'))
    if (name === './failureAction') return loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
    if (name === './platformLabel') return { platformLabel: String }
    if (name === '../../analytics/flags') return { flagEnabled: () => false, flagAssigned: () => false }
    if (name === '../../analytics/studio') return { trackLegacyEntry() {} }
    if (name === './legacyEntrypoints') return { legacyEntrypointsHidden: () => false }
    return { default: empty }
  }
  const exportsObject = {}
  const source = fs.readFileSync(path.join(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX } }).outputText, { exports: exportsObject, require: moduleRequire, console })
  renderToStaticMarkup(React.createElement(exportsObject.default, { project: { id: 'p1', status: 'completed', settings: { smart_import: {} }, clips: [], collections: [] }, onCreateCollection() {}, onReload() {} }))
}

/** #416 per-flow definition: follow retry_of to the root (max 4 hops); a flow counts once, outcome = last attempt. */
function flows(finished) {
  const byId = new Map(finished.map(p => [p.attempt_id, p]))
  const root = p => { let cur = p; for (let i = 0; i < 4 && cur.retry_of && byId.has(cur.retry_of); i++) cur = byId.get(cur.retry_of); return cur.attempt_id }
  const out = new Map()
  for (const p of finished) out.set(root(p), p.outcome)  // events arrive in order: last attempt wins
  return out
}

test('R19 #108 partial page 「重试这条」 links retry_of and the flow counts once (last attempt wins)', async () => {
  const { tracker, events, posts, studioApi } = setup()
  const partial = { material_origin: 'user', generation: { auto_start: true, status: 'partial', error_code: 'timeout', completed_variant_count: 1 },
    analysis: { status: 'completed', outcome: 'partial' }, drafts: [], jobs: [], events: [],
    output_variants: [{ id: 'v-ok', status: 'completed', strategy_id: 'douyin' }, { id: 'v-bad', status: 'failed', strategy_id: 'xhs', render_job_id: 'job-1' }] }
  tracker.watch('studio-generation', 'p1')
  tracker.observeStudio(tracker.list().find(w => w.kind === 'studio-generation'), partial)
  const genFinished = events.filter(e => e.event === 'studio_generation_finished').map(e => e.props)
  assert.equal(genFinished.length, 1); assert.equal(genFinished[0].outcome, 'partial')

  const cards = []
  renderResults(partial, studioApi, cards)
  const bad = cards.find(c => c.variant.id === 'v-bad')
  await bad.onRetry()  // exactly what the card's 「重试这条」 button calls
  assert.deepEqual(posts, ['/studio/p1/output-variants/v-bad/retry'])
  const watch = tracker.list().filter(w => w.kind === 'studio-variant' && w.id === 'v-bad').at(-1)
  assert.equal(watch.properties.retry_of, genFinished[0].attempt_id)

  tracker.observeStudio(watch, { ...partial, output_variants: [{ id: 'v-bad', status: 'completed', strategy_id: 'xhs', render_job_id: 'job-2' }] })
  const variantFinished = events.filter(e => e.event === 'studio_variant_finished').map(e => e.props)
  assert.equal(variantFinished.length, 1)
  assert.equal(variantFinished[0].retry_of, genFinished[0].attempt_id)
  assert.notEqual(variantFinished[0].attempt_id, genFinished[0].attempt_id)
  const result = flows([...genFinished, ...variantFinished])
  assert.equal(result.size, 1)                                   // one flow, counted once
  assert.equal([...result.values()][0], 'success')  // canonical outcome of the completed retry             // last attempt decides
})

test('R19 #108 a second 「重试这条」 after the variant failed again chains to the variant attempt', async () => {
  const { tracker, events, studioApi } = setup()
  tracker.watch('studio-variant', 'v-bad', 'p1', undefined, {}, false, 'job-1')
  tracker.observeStudio(tracker.list()[0], { output_variants: [{ id: 'v-bad', status: 'failed', render_job_id: 'job-1' }], jobs: [] })
  const first = events.find(e => e.event === 'studio_variant_finished').props
  await studioApi.retryOutputVariant('p1', 'v-bad')
  assert.equal(tracker.list().filter(w => w.kind === 'studio-variant' && w.id === 'v-bad').at(-1).properties.retry_of, first.attempt_id)
})

test('R19 #107 studio_screen_finished on failure carries upstream type + status, never the error text', () => {
  const { tracker, events } = setup()
  tracker.watch('studio-screen', 'p1')
  tracker.observeStudio(tracker.list()[0], { material_origin: 'user', analysis: { status: 'failed', phase: 'screening', error: '云端转写失败：HTTP 401 sk-secret https://asr.example', error_code: 'authentication', failure_stage: 'subtitle', http_status: 401, upstream_error_type: 'invalid_key' } })
  const p = events.find(e => e.event === 'studio_screen_finished').props
  assert.equal(p.upstream_error_type, 'invalid_key'); assert.equal(p.http_status, 401); assert.equal(p.failure_stage, 'subtitle')
  assert.ok(!JSON.stringify(p).includes('sk-secret') && !JSON.stringify(p).includes('asr.example') && !('error' in p))
})
