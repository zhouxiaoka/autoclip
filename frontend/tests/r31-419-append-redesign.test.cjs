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
  // R31 review: the StudioResults source-text regexes were removed; the page wiring is proven by rendering in
  // r31-419-append-page-dom.test.cjs.
})
