// R23 #226/#227 for #419: concurrent retries keep one watch per attempt; retry_of follows attempt order, not arrival order.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

function harness(postResult = {}) {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = [], store = new Map()
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
  return { workflow, tracker, studioApi: api.studioApi, finished, watches, tick: ms => { clock += ms }, storage, store }
}
const gen = status => ({ material_origin: 'user', generation: { status, created_at: '2026-10-10T00:00:00Z' }, analysis: { status: 'completed' } })
const prod = status => ({ material_origin: 'user', plan: { id: 'plan1' }, analysis: { status } })

// Older attempt A (production, plan1) and newer attempt B (generation); terminals arrive B first, then A.
function twoAttempts() {
  const h = harness()
  h.tracker.watch('studio-production', 'plan1', 'p1')
  h.tick(1000)
  h.tracker.watch('studio-generation', 'p1')
  return { h, a: h.watches('studio-production')[0], b: h.watches('studio-generation')[0] }
}

test('#227: an older success arriving after a newer failure keeps retry_of on the newer failure', () => {
  const { h, a, b } = twoAttempts()
  h.tracker.observeStudio(b, gen('failed'))
  h.tracker.observeStudio(a, prod('completed'))
  assert.equal(h.tracker.lastFailedAttempt('p1'), b.token)
})

test('#227: an older failure arriving late does not repoint retry_of to the older attempt', () => {
  const { h, a, b } = twoAttempts()
  h.tracker.observeStudio(b, gen('failed'))
  h.tracker.observeStudio(a, prod('failed'))
  assert.equal(h.tracker.lastFailedAttempt('p1'), b.token)
})

test('#227: the attempt order survives a reload (persisted with the context)', () => {
  const { h, a, b } = twoAttempts()
  h.tracker.observeStudio(b, gen('failed'))
  const again = new h.workflow.WorkflowTracker(h.storage, () => true, () => true, () => Date.parse('2026-10-10T00:00:02Z'))
  const [late] = again.list().filter(w => w.kind === 'studio-production')
  again.observeStudio(late, prod('completed'))
  assert.equal(again.lastFailedAttempt('p1'), b.token)
})

test('#227: in-order terminals still move retry_of forward (newer success clears it)', () => {
  const { h, a, b } = twoAttempts()
  h.tracker.observeStudio(a, prod('failed'))
  assert.equal(h.tracker.lastFailedAttempt('p1'), a.token)
  h.tracker.observeStudio(b, gen('completed'))
  assert.equal(h.tracker.lastFailedAttempt('p1'), undefined)
})

test('#226: two concurrent 「重试这条」 keep two attempts, each reaching its own terminal', async () => {
  const h = harness({ value: { id: 'v1', status: 'queued', render_attempt_id: 'ra1' } })
  h.tracker.watch('studio-generation', 'p1')
  h.tracker.observeStudio(h.watches('studio-generation')[0], gen('failed'))
  const failed = h.finished('studio_generation_finished')[0].attempt_id
  await Promise.all([h.studioApi.retryOutputVariant('p1', 'v1'), h.studioApi.retryOutputVariant('p1', 'v2')])
  const open = h.watches('studio-generation').filter(w => !w.settled)
  assert.equal(open.length, 2, 'the second retry must not drop the first attempt')
  for (const w of open) h.tracker.observeStudio(w, gen('completed'))
  const after = h.finished('studio_generation_finished').slice(1)
  assert.equal(after.length, 2)
  assert.notEqual(after[0].attempt_id, after[1].attempt_id)
  assert.deepEqual(after.map(p => p.retry_of), [failed, failed])
})

test('#228: the production terminal carries the secondary causes, positional and allow-listed', () => {
  const h = harness()
  h.tracker.watch('studio-production', 'plan1', 'p1')
  h.tracker.observeStudio(h.watches('studio-production')[0], { plan: { id: 'plan1' }, analysis: { status: 'failed', error_code: 'timeout', upstream_error_type: 'timeout',
    secondary_error_codes: ['authentication', '/Users/x/secret'], secondary_upstream_error_types: ['invalid_key', 'sk-abc'] } })
  const [p] = h.finished('studio_production_finished')
  assert.equal(p.error_code, 'timeout')
  assert.equal(p.secondary_error_codes, 'authentication,unknown')
  assert.equal(p.secondary_upstream_error_types, 'invalid_key,')
})

// R24 #266: attempts started in the same millisecond are ordered by a stable sequence, not by arrival.
function sameMs() {
  const h = harness()
  h.tracker.watch('studio-production', 'plan1', 'p1')
  h.tracker.watch('studio-generation', 'p1')           // same clock: newer attempt, same since
  return { h, a: h.watches('studio-production')[0], b: h.watches('studio-generation')[0] }
}
test('#266: same-ms older success arriving after the newer failure keeps retry_of on the newer', () => {
  const { h, a, b } = sameMs()
  h.tracker.observeStudio(b, gen('failed'))
  h.tracker.observeStudio(a, prod('completed'))
  assert.equal(h.tracker.lastFailedAttempt('p1'), b.token)
})
test('#266: same-ms order survives a reload', () => {
  const { h, a, b } = sameMs()
  h.tracker.observeStudio(b, gen('failed'))
  const again = new h.workflow.WorkflowTracker(h.storage, () => true, () => true, () => Date.parse('2026-10-10T00:00:00Z'))
  const [late] = again.list().filter(w => w.kind === 'studio-production')
  again.observeStudio(late, prod('failed'))
  assert.equal(again.lastFailedAttempt('p1'), b.token)
})
