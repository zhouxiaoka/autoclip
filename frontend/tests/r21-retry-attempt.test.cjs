const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

function harness(postResult = {}, store = new Map()) {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }
  let clock = Date.parse('2026-10-10T00:00:00Z')
  const tracker = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true }, () => clock)
  const studio = { observeStudioOperation: async (_n, action, accepted = () => {}, props = {}) => { const r = await action(); accepted(r, { ...props }); return r }, studioImportProperties: () => ({}), studioGoals: () => ({}), observeStudioWorkspace: () => {} }
  const api = loadTs(path.resolve(__dirname, '../src/features/studio/api.ts'), {
    '../../analytics/posthog': { captureBusinessEvent() {} }, '../../analytics/workflow': workflow, '../../analytics/studio': studio,
    '../../analytics/observer': { workflow: tracker },
    '../../services/api': { default: { post: async () => postResult.value, put: async () => ({}), get: async () => ({}) }, __esModule: true },
    './noticeRuntime': { noteWorkspaceCompletion() {} }, './subtitleState': { effectiveSubtitles: x => x },
  })
  const finished = name => events.filter(e => e.event === name).map(e => e.props)
  const watches = kind => tracker.list().filter(w => w.kind === kind)
  return { workflow, tracker, studioApi: api.studioApi, finished, watches, tick: ms => { clock += ms }, store, storage }
}
const partialGen = { material_origin: 'user', generation: { status: 'partial', error_code: 'timeout', created_at: '2026-10-10T00:00:00Z' }, analysis: { status: 'completed', outcome: 'partial' } }
const doneGen = { ...partialGen, generation: { status: 'completed', created_at: '2026-10-10T00:00:00Z' } }

test('R21 #157: 「重试这条」 always opens a new aggregate attempt; retry_of survives the 7-day watch TTL', async () => {
  const store = new Map()
  const h = harness({ value: { id: 'v1', status: 'queued', render_attempt_id: 'ra1' } }, store)
  h.tracker.watch('studio-generation', 'p1')
  h.tracker.observeStudio(h.watches('studio-generation')[0], partialGen)
  const failed = h.finished('studio_generation_finished')[0].attempt_id
  h.tick(8 * 86400000)                       // the old watch expires
  assert.equal(h.watches('studio-generation').length, 0)
  await h.studioApi.retryOutputVariant('p1', 'v1')
  const [gen] = h.watches('studio-generation')
  assert.ok(gen, 'a generation attempt is registered even without the old watch')
  assert.equal(gen.properties.retry_of, failed)
  h.tracker.observeStudio(gen, doneGen)
  const [, after] = h.finished('studio_generation_finished')
  assert.equal(after.retry_of, failed)
  assert.notEqual(after.attempt_id, failed)
})

test('R21 #157: no known failed terminal -> still a new attempt that reaches a terminal, without retry_of', async () => {
  const h = harness({ value: { id: 'v1', status: 'queued', render_attempt_id: 'ra1' } })
  await h.studioApi.retryOutputVariant('p1', 'v1')
  const [gen] = h.watches('studio-generation')
  assert.ok(gen)
  assert.equal(gen.properties.retry_of, undefined)
  h.tracker.observeStudio(gen, doneGen)
  assert.equal(h.finished('studio_generation_finished').length, 1)
})

test('R21 #158: needs_prepare retry (preparing, no render_job_id) is a new variant attempt keyed by preparation_run_id', async () => {
  const result = { value: { id: 'v1', status: 'preparing', preparation_run_id: 'prep-2' } }
  const h = harness(result)
  h.tracker.watch('studio-variant', 'v1', 'p1')          // an earlier, still unsettled attempt
  const old = h.watches('studio-variant')[0].token
  await h.studioApi.retryOutputVariant('p1', 'v1')
  const [w] = h.watches('studio-variant')
  assert.notEqual(w.token, old, 'restart: consecutive retries never share an attempt')
  assert.equal(w.runId, 'prep-2')
  // a stale snapshot of another attempt is ignored; the prepared -> rendered variant (same preparation run) settles it
  h.tracker.observeStudio(w, { output_variants: [{ id: 'v1', status: 'failed', preparation_run_id: 'prep-1' }] })
  assert.equal(h.finished('studio_variant_finished').length, 0)
  h.tracker.observeStudio(w, { output_variants: [{ id: 'v1', status: 'completed', preparation_run_id: 'prep-2', render_attempt_id: 'ra9', render_job_id: 'j9' }], jobs: [{ job_id: 'j9', status: 'completed' }] })
  assert.equal(h.finished('studio_variant_finished')[0].attempt_id, w.token)
})

test('R21 #159: first clip is reported once per real generation, not once per watch', async () => {
  const h = harness({ value: { id: 'v1', status: 'queued', render_attempt_id: 'ra1' } })
  const snap = { material_origin: 'user', generation: { status: 'partial', created_at: '2026-10-10T00:00:00Z' }, output_variants: [{ id: 'v0', status: 'completed', render_job_id: 'j0', strategy_id: 's' }], jobs: [{ job_id: 'j0', status: 'completed', finished_at: '2026-10-10T00:01:00Z' }], drafts: [] }
  h.tracker.watch('studio-generation', 'p1')
  h.tracker.noteFirstClip(h.watches('studio-generation')[0], snap, true)
  await h.studioApi.retryOutputVariant('p1', 'v1')
  h.tracker.noteFirstClip(h.watches('studio-generation')[0], snap, true)
  assert.equal(h.finished('studio_first_clip_ready').length, 1)
  // a genuinely new generation reports its own first clip
  h.tracker.noteFirstClip(h.watches('studio-generation')[0], { ...snap, generation: { status: 'completed', created_at: '2026-10-11T00:00:00Z' }, jobs: [{ job_id: 'j0', status: 'completed', finished_at: '2026-10-11T00:01:00Z' }] }, true)
  assert.equal(h.finished('studio_first_clip_ready').length, 2)
})

test('R21 #164: retry_of only ever references a v4 success-rate terminal', () => {
  const h = harness()
  h.tracker.watch('studio-screen', 'p1')
  h.tracker.observeStudio(h.watches('studio-screen')[0], { material_origin: 'user', analysis: { status: 'failed', phase: 'screening', error_code: 'timeout' } })
  assert.equal(h.tracker.lastFailedAttempt('p1'), undefined)
  h.tracker.watch('studio-generation', 'p1')
  h.tracker.observeStudio(h.watches('studio-generation')[0], partialGen)
  assert.equal(h.tracker.lastFailedAttempt('p1'), h.finished('studio_generation_finished')[0].attempt_id)
  assert.deepEqual([...h.workflow.SUCCESS_RATE_TERMINALS], ['studio_generation_finished', 'studio_production_finished'])
})
