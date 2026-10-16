// R25 #345/#347: the v4 terminal is projected from the receipt only - flow_id is the receipt's (two backend flows
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
  const flows = Object.fromEntries(h.finished('studio_generation_finished').map(p => [p.attempt_id, p.flow_id]))
  assert.deepEqual(flows, { [A]: FA, [B]: FB })
})

test('#345: cleared browser storage does not change the flow_id', () => {
  const a = gen(A, 1, FA, 'completed')
  for (let i = 0; i < 2; i++) {
    const h = tracker(memory())
    h.t.watchAttempt('p1', a)
    h.t.observeStudio(h.t.list()[0], live([a]))
    assert.equal(h.finished('studio_generation_finished')[0].flow_id, FA)
  }
})

test('#347: a historical receipt reports its own frozen counts, not the live workspace', () => {
  const h = tracker()
  const old = gen(A, 1, FA, 'failed', { variant_count: 2, completed_variant_count: 0, failed_variant_count: 2, recommendation_mode: 'local', route: 'subtitle' })
  const now = gen(B, 2, FA, 'completed', { variant_count: 2, completed_variant_count: 2 })
  h.t.watchAttempt('p1', old)
  h.t.observeStudio(h.t.list()[0], live([old, now]))
  const [e] = h.finished('studio_generation_finished')
  assert.equal(e.completed_variant_count, 0); assert.equal(e.failed_variant_count, 2)
  assert.equal(e.recommendation_mode, 'local'); assert.equal(e.route, 'subtitle')
  assert.equal(e.platform_count, undefined)  // not in the frozen summary: never filled from the live generation
})
