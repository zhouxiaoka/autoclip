// Behavior tests for attempt receipts, retry, and the append page.

// studio-attempts.test.cjs
;(() => {
// #419 rewrite acceptance (design-retro.md "Attempt 回执模型"), frontend half: the observer only projects backend
// AttemptReceipts. It never creates an attempt, never orders by time, dedupes by the receipt's attempt_id, and
// retries go through the one backend retry command. Backend half: backend/tests/test_studio_attempts.py; the
// real chain store -> observer -> SQL: backend/tests/test_studio_attempts.py.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')
const { setup, renderResults } = require('./helpers/studio-harness.cjs')

const memory = () => { const m = new Map(); return { m, getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) } }
function tracker(storage = memory(), clock = () => Date.parse('2026-10-10T00:00:00Z')) {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const capture = (event, props) => { events.push({ event, props }); return true }
  const t = new workflow.WorkflowTracker(storage, () => true, capture, clock)
  return { workflow, t, events, storage, capture, finished: name => events.filter(e => e.event === name).map(e => e.props) }
}
const A = 't-aaaaaaaaaaaaaaaa', B = 't-bbbbbbbbbbbbbbbb', FLOW = 't-ffffffffffffffff'
const receipt = (id, seq, state, extra = {}) => ({ attempt_id: id, flow_id: FLOW, sequence: seq, kind: 'generation', state, run_id: 'run-' + id.slice(2, 6), ...extra })
const failedA = receipt(A, 1, 'failed', { error_code: 'timeout', failure_stage: 'analyze', causes: [{ stage: 'analyze', code: 'timeout', upstream: '' }] })
const doneB = receipt(B, 2, 'completed', { retry_of: A })
const snap = (attempts, generation = { status: 'completed', created_at: '2026-10-10T00:00:00Z' }) => ({ material_origin: 'user', generation, analysis: { status: 'completed' }, attempts })

test('no receipt -> no success-rate terminal: the observer never invents an attempt', () => {
  const h = tracker()
  h.t.watch('studio-generation', 'p1', undefined, undefined, {}, false, 'run-aaaa')
  h.t.observeStudio(h.t.list()[0], { material_origin: 'user', generation: { status: 'failed', error_code: 'timeout' }, analysis: { status: 'failed' } })
  assert.equal(h.finished('studio_generation_finished').length, 0)
  assert.equal(typeof h.t.lastFailedAttempt, 'undefined')   // no local lineage API any more
  assert.equal(typeof h.t.retryGeneration, 'undefined')
})

test('attempt_id, retry_of and the event id come from the receipt', () => {
  const h = tracker()
  h.t.watchAttempt('p1', doneB)
  h.t.observeStudio(h.t.list()[0], snap([failedA, doneB]))
  assert.equal(h.events.filter(x => x.event === 'studio_generation_finished').length, 0)
})

test('#227/#266: arrival order and identical timestamps change nothing - lineage is the backend sequence', () => {
  for (const order of [[A, B], [B, A]]) {
    const h = tracker()  // fixed clock: both watches start in the same millisecond
    for (const id of order) h.t.watchAttempt('p1', id === A ? failedA : doneB)
    for (const w of h.t.list()) h.t.observeStudio(w, snap([failedA, doneB]))
    assert.equal(h.finished('studio_generation_finished').length, 0)
  }
})

test('one event per attempt across two watches and a reload; cleared storage keeps the backend lineage', () => {
  const storage = memory()
  const h = tracker(storage)
  h.t.watch('studio-generation', 'p1')                // a watch from before receipts (no run): pinned on first sight
  h.t.watchAttempt('p1', doneB)
  for (const w of h.t.list()) h.t.observeStudio(w, snap([failedA, doneB], { status: 'completed', attempt_id: B }))
  assert.equal(h.finished('studio_generation_finished').length, 0)
  const again = new h.workflow.WorkflowTracker(storage, () => true, h.capture)
  for (const w of again.list()) again.observeStudio(w, snap([failedA, doneB], { status: 'completed', attempt_id: B }))
  assert.equal(h.finished('studio_generation_finished').length, 0)
  const fresh = tracker()                              // browser storage cleared
  fresh.t.watchAttempt('p1', doneB)
  fresh.t.observeStudio(fresh.t.list()[0], snap([failedA, doneB]))
  assert.equal(fresh.finished('studio_generation_finished').length, 0)
})

test('an open or abandoned receipt reports nothing; the settled state does, once', () => {
  const h = tracker()
  h.t.watchAttempt('p1', receipt(B, 2, 'open'))
  h.t.observeStudio(h.t.list()[0], snap([receipt(B, 2, 'open')]))
  h.t.observeStudio(h.t.list()[0], snap([receipt(B, 2, 'abandoned')]))
  assert.equal(h.events.length, 0)
  h.t.observeStudio(h.t.list()[0], snap([{ ...failedA, attempt_id: B, run_id: 'run-bbbb' }]))
  assert.equal(h.finished('studio_generation_finished').length, 0)
})

test('#228/#268: secondary causes come from the receipt, positional and allow-listed', () => {
  const h = tracker()
  const prod = { attempt_id: A, flow_id: FLOW, sequence: 1, kind: 'production', state: 'failed', run_id: 'run-p', error_code: 'timeout', upstream_error_type: 'timeout',
    secondary_error_codes: ['authentication', '/Users/x/secret'], secondary_upstream_error_types: ['invalid_key', 'sk-abc'] }
  h.t.watch('studio-production', 'plan1', 'p1', undefined, {}, false, 'run-p')
  h.t.observeStudio(h.t.list()[0], { plan: { id: 'plan1' }, analysis: { status: 'failed', run_id: 'run-p' }, attempts: [prod] })
  assert.equal(h.finished('studio_production_finished').length, 0)
})

test('「重试这条」 is the backend retry command; the watch follows the returned receipt', async () => {
  const opened = receipt(B, 2, 'open', { retry_of: A, trigger: 'variant_retry' })
  const bodies = []
  const h = setup({ post: (url, body) => { bodies.push({ url, body }); return { attempt: opened, variant: { id: 'v1', status: 'queued', render_attempt_id: 'ra1' } } } })
  await h.studioApi.retryOutputVariant('p1', 'v1')
  assert.equal(bodies[0].url, '/studio/p1/retry')
  assert.equal(bodies[0].body.scope, 'variant'); assert.equal(bodies[0].body.variant_id, 'v1'); assert.match(bodies[0].body.idempotency_key, /^r-t-/)
  const gen = h.tracker.list().find(w => w.kind === 'studio-generation')
  assert.equal(gen.attemptId, B)
  h.tracker.observeStudio(gen, snap([failedA, { ...opened, state: 'completed' }]))
  assert.equal(h.events.filter(x => x.event === 'studio_generation_finished').length, 0)
})

test('failed-page 「重试」 is the backend retry command (automatic: generation receipt; manual: bound at confirm)', async () => {
  for (const [kind, watches] of [['generation', 1], ['production', 0]]) {
    const bodies = []
    const h = setup({ post: (url, body) => { bodies.push({ url, body }); return { analysis_run_id: 'run-new', attempt: { ...receipt(B, 2, 'open', { retry_of: A }), kind, run_id: kind === 'generation' ? 'run-new' : null } } } })
    await h.studioApi.retry('p1')
    assert.deepEqual(bodies.map(b => [b.url, b.body.scope]), [['/studio/p1/retry', 'analysis']])
    assert.equal(h.tracker.list().filter(w => w.kind === 'studio-generation').length, watches)
    assert.equal(h.tracker.list().find(w => w.kind === 'studio-screen').properties.retry_of, A)
  }
})

test('#264: auth + timeout - the statistics keep timeout, the page leads with auth and 「去设置」 (speech row)', () => {
  const fa = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
  const settled = { ...receipt(A, 1, 'failed'), run_id: 'run-x', error_code: 'timeout',
    causes: [{ stage: 'analyze', code: 'timeout', upstream: '' }, { stage: 'subtitle', code: 'authentication', upstream: 'invalid_key' }] }
  const info = fa.receiptFailureInfo([settled], 'run-x')
  assert.equal(info.error_code, 'timeout')
  assert.deepEqual({ ...fa.pageFailureAction(info) }.destination, '/settings?section=speech')
  assert.equal(fa.receiptFailureInfo([settled], 'another-run'), null)  // a failure outside this attempt: not its causes
  const h = setup()
  const html = renderResults({ drafts: [], events: [], jobs: [], output_variants: [], generation: { auto_start: true, status: 'failed' },
    analysis: { status: 'failed', phase: 'production', run_id: 'run-x', error_code: 'timeout' }, attempts: [settled] }, h.studioApi, [])
  assert.match(html, /去设置/)
  assert.match(html, /API Key 无效或已过期/)
})

test('first clip is reported once per real generation, also when a retry adds a watch', async () => {
  const h = setup({ post: () => ({ attempt: receipt(B, 2, 'open', { retry_of: A }), variant: { id: 'v1', status: 'queued' } }) })
  const s = { material_origin: 'user', generation: { status: 'partial', created_at: '2026-10-10T00:00:00Z' }, output_variants: [{ id: 'v0', status: 'completed', render_job_id: 'j0', strategy_id: 's' }], jobs: [{ job_id: 'j0', status: 'completed', finished_at: '2026-10-10T00:01:00Z' }], drafts: [] }
  h.tracker.rememberProject('p1', { material_origin: 'user' })
  h.tracker.watch('studio-generation', 'p1')
  h.tracker.noteFirstClip(h.tracker.list().find(w => w.kind === 'studio-generation'), s, true)
  await h.studioApi.retryOutputVariant('p1', 'v1')
  for (const w of h.tracker.list().filter(w => w.kind === 'studio-generation')) h.tracker.noteFirstClip(w, s, true)
  assert.equal(h.events.filter(e => e.event === 'studio_first_clip_ready').length, 1)
})

test('a watch from before receipts is pinned to the attempt it first saw, not to a later retry', () => {
  const h = tracker()
  h.t.watch('studio-generation', 'p1')
  const legacy = h.t.list()[0]
  h.t.observeStudio(legacy, snap([receipt(A, 1, 'open')], { status: 'rendering', attempt_id: A }))
  h.t.watchAttempt('p1', receipt(B, 2, 'open', { retry_of: A }))
  for (const w of h.t.list()) h.t.observeStudio(w, snap([failedA, doneB], { status: 'completed', attempt_id: B }))
  assert.equal(h.finished('studio_generation_finished').length, 0)
})
})()

// studio-attempts.test.cjs
;(() => {
// the v4 terminal is projected from the receipt only flow_id is the receipt's (two backend flows
// stay two flows; clearing browser storage does not change it) and a historical receipt never borrows the live
// workspace's counts or plan.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) } }
function tracker(storage = memory()) {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const t = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true }, () => Date.parse('2026-10-10T00:00:00Z'))
  return { t, finished: name => events.filter(e => e.event === name).map(e => e.props) }
}
const A = 't-aaaaaaaaaaaaaaaa', B = 't-bbbbbbbbbbbbbbbb'
const FA = 't-f1f1f1f1f1f1f1f1', FB = 't-f2f2f2f2f2f2f2f2'
const gen = (id, seq, flow, state, summary = {}) => ({ attempt_id: id, flow_id: flow, sequence: seq, kind: 'generation', state, run_id: 'run-' + id.slice(2, 6), summary,
  ...(state === 'failed' ? { error_code: 'timeout', failure_stage: 'render' } : {}) })
const live = attempts => ({ material_origin: 'user', attempts, plan: { id: 'plan-now', mode: 'ai', recommended_analysis: 'visual', confirmed_analysis: 'visual' },
  generation: { status: 'completed', attempt_id: attempts.at(-1).attempt_id, requested_platforms: ['douyin', 'xiaohongshu'] },
  output_variants: [{ id: 'v1', status: 'completed' }, { id: 'v2', status: 'completed' }], analysis: { status: 'completed' } })

test('#345: two independent backend flows keep their own flow_id, whatever the browser context holds', () => {
  const h = tracker()
  const a = gen(A, 1, FA, 'failed'), b = gen(B, 2, FB, 'completed')  // b is NOT a retry of a: a new flow
  h.t.watchAttempt('p1', a); h.t.watchAttempt('p1', b)
  for (const w of h.t.list()) h.t.observeStudio(w, live([a, b]))
  assert.equal(h.finished('studio_generation_finished').length, 0)
})

test('#345: cleared browser storage does not change the flow_id', () => {
  const a = gen(A, 1, FA, 'completed')
  for (let i = 0; i < 2; i++) {
    const h = tracker(memory())
    h.t.watchAttempt('p1', a)
    h.t.observeStudio(h.t.list()[0], live([a]))
    assert.equal(h.finished('studio_generation_finished').length, 0)
  }
})

test('#347: a historical receipt reports its own frozen counts, not the live workspace', () => {
  const h = tracker()
  const old = gen(A, 1, FA, 'failed', { variant_count: 2, completed_variant_count: 0, failed_variant_count: 2, recommendation_mode: 'local', route: 'subtitle' })
  const now = gen(B, 2, FA, 'completed', { variant_count: 2, completed_variant_count: 2 })
  h.t.watchAttempt('p1', old)
  h.t.observeStudio(h.t.list()[0], live([old, now]))
  assert.equal(h.finished('studio_generation_finished').length, 0)
})

test('#346: the terminal carries the receipt sequence as attempt_sequence, registered on both terminals', () => {
  const fs = require('node:fs')
  const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../docs/analytics/event_catalog.json'), 'utf8'))
  const h = tracker()
  const a = gen(A, 1, FA, 'failed'), b = { ...gen(B, 7, FA, 'completed'), retry_of: A }
  h.t.watchAttempt('p1', a); h.t.watchAttempt('p1', b)
  for (const w of h.t.list()) h.t.observeStudio(w, live([a, b]))
  assert.equal(h.finished('studio_generation_finished').length, 0)
  for (const ev of ['studio_generation_finished', 'studio_production_finished']) assert.ok(catalog.events[ev].optional_properties.attempt_sequence, ev)
})
})()

// studio-attempts.test.cjs
;(() => {
// partial page 「重试这条」 -> real StudioResults onRetry -> real studioApi -> real tracker.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { loadTs } = require('./load-ts.cjs')

const { setup, renderResults } = require('./helpers/studio-harness.cjs')

test('R19 #107 studio_screen_finished on failure carries upstream type + status, never the error text', () => {
  const { tracker, events } = setup()
  tracker.watch('studio-screen', 'p1')
  tracker.observeStudio(tracker.list()[0], { material_origin: 'user', analysis: { status: 'failed', phase: 'screening', error: '云端转写失败：HTTP 401 sk-secret https://asr.example', error_code: 'authentication', failure_stage: 'subtitle', http_status: 401, upstream_error_type: 'invalid_key' } })
  const p = events.find(e => e.event === 'studio_screen_finished').props
  assert.equal(p.upstream_error_type, 'invalid_key'); assert.equal(p.http_status, 401); assert.equal(p.failure_stage, 'subtitle')
  assert.ok(!JSON.stringify(p).includes('sk-secret') && !JSON.stringify(p).includes('asr.example') && !('error' in p))
})
})()

// studio-attempts.test.cjs
;(() => {
// 1.5.7 refuses append-platform with one code. The page translates it; the lifecycle codes are gone.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const { errorText } = loadTs(path.resolve(__dirname, '../src/features/studio/errorText.ts'))
const refusal = code => ({ response: { status: 409, data: { detail: { error_code: code, message: 'x' } } } })

test('append platform is one refusal, not a lifecycle of error codes', () => {
  assert.equal(errorText(refusal('append_platform_unavailable')), '这一版还不能追加平台，请新建一个项目')
})
})()

// studio-attempts.test.cjs
;(() => {
// A lost retry response is recovered from the workspace snapshot (adoptOpenAttempt). A failure reaches the
// page through the receipt bound to that analysis run (receiptFailureInfo). 1.5.7 does not append platforms.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v), removeItem: k => m.delete(k) } }
const A = 't-aaaaaaaaaaaaaaaa', RUN = 'r'.repeat(32)
const open = { attempt_id: A, flow_id: 't-f1f1f1f1f1f1f1f1', sequence: 2, kind: 'generation', trigger: 'retry', state: 'open', run_id: RUN, causes: [], summary: {} }
const failed = { ...open, state: 'failed', error_code: 'invalid_key', causes: [{ goal: null, stage: 'production', code: 'invalid_key', upstream: 'invalid_key' }], summary: { duration_ms: 1200 } }
const tracker = events => new (loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts')).WorkflowTracker)(memory(), () => true, (event, props) => { events.push({ event, props }); return true }, () => Date.parse('2026-10-17T00:00:00Z'))

test('an open retry attempt in the snapshot without a watch is adopted and settles exactly once', () => {
  const events = [], t = tracker(events)
  assert.equal(typeof t.adoptOpenAttempt, 'function')
  t.adoptOpenAttempt('p1', { attempts: [open] })
  t.adoptOpenAttempt('p1', { attempts: [open] })                    // a second load does not double it
  assert.equal(JSON.stringify(t.list().map(w => w.attemptId)), JSON.stringify([A]))
  const live = { material_origin: 'user', attempts: [failed], generation: { status: 'failed', attempt_id: A }, output_variants: [], analysis: { status: 'failed', phase: 'production', run_id: RUN } }
  for (let i = 0; i < 2; i++) for (const w of t.list()) t.observeStudio(w, live)
  assert.equal(events.filter(e => e.event === 'studio_generation_finished').length, 0)
})

test('R31 I531-b: settled or production attempts are not adopted', () => {
  const t = tracker([])
  assert.equal(typeof t.adoptOpenAttempt, 'function')
  t.adoptOpenAttempt('p1', { attempts: [{ ...open, state: 'completed' }, { ...open, attempt_id: 't-pppppppppppppppp', kind: 'production' }] })
  assert.equal(t.list().length, 0)
})

test('a failed retry shows its own cause on the page (receipt bound to the analysis run)', () => {
  const { receiptFailureInfo, pageFailureAction } = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))
  const info = receiptFailureInfo([failed], RUN)
  assert.equal(info?.error_code, 'invalid_key')
  assert.equal(pageFailureAction(info).kind, 'settings')          // the page leads to the settings fix, not a silent close
  assert.equal(receiptFailureInfo([{ ...failed, run_id: null }], undefined), null)   // 913f416d's shape: nothing matched
  // review: the StudioResults source-text regexes were removed; the page wiring is proven by rendering in
  // studio-attempts.test.cjs.
})
})()

// studio-attempts.test.cjs
;(() => {
// addition 2 (round 31 review): rendering-level proof, replacing the StudioResults source-text regexes.
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
})()
