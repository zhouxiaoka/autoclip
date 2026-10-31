// (replaces helpers/backend-receipts.cjs, which copied backend receipt rules into the tests): telemetry tests
// that observe bare workspace snapshots get the attempt receipt from the REAL backend. Each terminal snapshot is
// written through backend/tests/receipt_bridge.py (attempts.open_attempt -> store.write -> attempts.reconcile), and
// the receipt it settled is attached to the snapshot the observer sees. No receipt rule is reimplemented here;
// only the choice of which snapshot a watch is looking at (run_id / history row) mirrors the old harness.
const { execFileSync } = require('node:child_process')
const path = require('node:path')
const ROOT = path.resolve(__dirname, '../../..')
const PYTHON = process.env.AUTOCLIP_TEST_PYTHON || process.env.PYTHON || 'python'
const TERMINAL = ['completed', 'partial', 'failed']
const cache = new Map()

function backendReceipts(payload) {
  const key = JSON.stringify(payload)
  if (!cache.has(key)) {
    const out = execFileSync(PYTHON, ['-m', 'backend.tests.receipt_bridge'], { cwd: ROOT, input: key, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 60000 })
    cache.set(key, JSON.parse(out))
  }
  return cache.get(key)
}

function withReceipt(w, s) {
  const kind = w.kind === 'studio-production' ? 'production' : w.kind === 'studio-generation' ? 'generation' : null
  if (!kind || !s || s.attempts) return s
  let snapshot = s
  if (w.runId) {
    const row = s.analysis_history?.find(r => r.run_id === w.runId)
    if (row) snapshot = { ...s, plan: row.plan, analysis: row.analysis }
    else if (kind === 'production' && s.analysis?.run_id !== w.runId) return { ...s, attempts: [] }
  }
  const settled = kind === 'generation' ? TERMINAL.includes(snapshot.generation?.status) : ['completed', 'failed'].includes(snapshot.analysis?.status)
  if (!settled || (kind === 'production' && snapshot.plan?.id !== w.id)) return { ...s, attempts: [] }
  const run = w.runId || snapshot.analysis?.run_id || 'run-legacy'
  const { attempts, attempt_id } = backendReceipts({ kind, run_id: run, seed: w.runId || w.token || w.id, retry: !!w.properties?.retry_of,
    snapshot: { ...snapshot, analysis: { ...(snapshot.analysis || {}), run_id: snapshot.analysis?.run_id || run } } })
  return { ...s, attempts: attempts.filter(a => a.run_id === run || a.attempt_id === attempt_id || kind === 'generation'),
    ...(kind === 'production' && !s.analysis?.run_id ? { analysis: { ...(s.analysis || {}), run_id: run } } : {}),
    ...(kind === 'generation' && s.generation ? { generation: { ...s.generation, attempt_id } } : {}) }
}

/** Wrap a loaded workflow module's tracker so bare snapshots get the receipt the real backend settles. */
function withRealBackend(workflow) {
  const proto = workflow.WorkflowTracker.prototype
  if (proto.__realBackend) return workflow
  const original = proto.observeStudio
  proto.observeStudio = function (w, snapshot) { return original.call(this, w, withReceipt(w, snapshot)) }
  proto.__realBackend = true
  return workflow
}

module.exports = { withRealBackend }
