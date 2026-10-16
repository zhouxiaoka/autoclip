// #419 rewrite acceptance (design-retro.md "Attempt 回执模型"), frontend half: the observer only projects backend
// AttemptReceipts. It never creates an attempt, never orders by time, dedupes by the receipt's attempt_id, and
// retries go through the one backend retry command. Backend half: backend/tests/test_r25_419_attempts.py; the
// real chain store -> observer -> SQL: backend/tests/test_r25_419_receipt_chain_duckdb.py.
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
  const [e] = h.events.filter(x => x.event === 'studio_generation_finished')
  assert.equal(e.props.attempt_id, B); assert.equal(e.props.retry_of, A); assert.equal(e.props.outcome, 'success')
  assert.equal(e.props.$insert_id, `studio-v1:${B}:finished`)
})

test('#227/#266: arrival order and identical timestamps change nothing - lineage is the backend sequence', () => {
  for (const order of [[A, B], [B, A]]) {
    const h = tracker()  // fixed clock: both watches start in the same millisecond
    for (const id of order) h.t.watchAttempt('p1', id === A ? failedA : doneB)
    for (const w of h.t.list()) h.t.observeStudio(w, snap([failedA, doneB]))
    const got = Object.fromEntries(h.finished('studio_generation_finished').map(p => [p.attempt_id, p.retry_of ?? null]))
    assert.deepEqual(got, { [A]: null, [B]: A })
  }
})

test('one event per attempt across two watches and a reload; cleared storage keeps the backend lineage', () => {
  const storage = memory()
  const h = tracker(storage)
  h.t.watch('studio-generation', 'p1')                // a watch from before receipts (no run): pinned on first sight
  h.t.watchAttempt('p1', doneB)
  for (const w of h.t.list()) h.t.observeStudio(w, snap([failedA, doneB], { status: 'completed', attempt_id: B }))
  assert.equal(h.finished('studio_generation_finished').length, 1)
  const again = new h.workflow.WorkflowTracker(storage, () => true, h.capture)
  for (const w of again.list()) again.observeStudio(w, snap([failedA, doneB], { status: 'completed', attempt_id: B }))
  assert.equal(h.finished('studio_generation_finished').length, 1)
  const fresh = tracker()                              // browser storage cleared
  fresh.t.watchAttempt('p1', doneB)
  fresh.t.observeStudio(fresh.t.list()[0], snap([failedA, doneB]))
  assert.equal(fresh.finished('studio_generation_finished')[0].retry_of, A)
})

test('an open or abandoned receipt reports nothing; the settled state does, once', () => {
  const h = tracker()
  h.t.watchAttempt('p1', receipt(B, 2, 'open'))
  h.t.observeStudio(h.t.list()[0], snap([receipt(B, 2, 'open')]))
  h.t.observeStudio(h.t.list()[0], snap([receipt(B, 2, 'abandoned')]))
  assert.equal(h.events.length, 0)
  h.t.observeStudio(h.t.list()[0], snap([{ ...failedA, attempt_id: B, run_id: 'run-bbbb' }]))
  assert.equal(h.finished('studio_generation_finished')[0].error_code, 'timeout')
})

test('#228/#268: secondary causes come from the receipt, positional and allow-listed', () => {
  const h = tracker()
  const prod = { attempt_id: A, flow_id: FLOW, sequence: 1, kind: 'production', state: 'failed', run_id: 'run-p', error_code: 'timeout', upstream_error_type: 'timeout',
    secondary_error_codes: ['authentication', '/Users/x/secret'], secondary_upstream_error_types: ['invalid_key', 'sk-abc'] }
  h.t.watch('studio-production', 'plan1', 'p1', undefined, {}, false, 'run-p')
  h.t.observeStudio(h.t.list()[0], { plan: { id: 'plan1' }, analysis: { status: 'failed', run_id: 'run-p' }, attempts: [prod] })
  const [p] = h.finished('studio_production_finished')
  assert.equal(p.error_code, 'timeout'); assert.equal(p.secondary_error_codes, 'authentication,unknown'); assert.equal(p.secondary_upstream_error_types, 'invalid_key,')
  assert.equal(JSON.stringify(p).includes('secret') || JSON.stringify(p).includes('sk-'), false)
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
  const [e] = h.events.filter(x => x.event === 'studio_generation_finished')
  assert.equal(e.props.attempt_id, B); assert.equal(e.props.retry_of, A)
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
  assert.deepEqual(h.finished('studio_generation_finished').map(p => [p.attempt_id, p.outcome]).sort(), [[A, 'error'], [B, 'success']])
})
