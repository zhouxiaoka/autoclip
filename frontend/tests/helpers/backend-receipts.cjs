// #419: v4 terminals are projections of backend AttemptReceipts (backend/services/studio/attempts.py). Telemetry
// tests that predate receipts feed the observer bare generation/analysis snapshots; this stands in for the backend
// by attaching the receipt attempts.reconcile would have written for that state (settled from the same record,
// primary cause first, summary = the same content-free keys). Backend settlement itself is tested in
// backend/tests/test_r25_419_attempts.py; the receipt-only rules are tested in r25-419-attempt-receipts.test.cjs.
const SUMMARY = ['provider', 'model', 'base_url_host', 'billable_calls_before_failure', 'retry_count', 'degrade_count', 'llm_calls',
  'prompt_tokens', 'completion_tokens', 'route', 'http_status', 'duration_ms', 'requested_goals', 'succeeded_goals', 'failed_goals',
  'result_count', 'completed_variant_count']
const TERMINAL = ['completed', 'partial', 'failed']
const id = seed => 't-' + Buffer.from(String(seed)).toString('hex').slice(0, 40).padEnd(12, '0')

function receiptFor(w, s, workflow) {
  const kind = w.kind === 'studio-production' ? 'production' : w.kind === 'studio-generation' ? 'generation' : null
  if (!kind || !s || s.attempts) return s
  let snapshot = s
  if (w.runId) {
    const row = s.analysis_history?.find(r => r.run_id === w.runId)
    if (row) snapshot = { ...s, plan: row.plan, analysis: row.analysis }
    else if (kind === 'production' && s.analysis?.run_id !== w.runId) return { ...s, attempts: [] }
  }
  let record, state
  if (kind === 'generation') {
    record = { ...Object.fromEntries(Object.entries(snapshot.analysis || {}).filter(([k]) => SUMMARY.includes(k))), ...(snapshot.generation || {}) }
    state = TERMINAL.includes(snapshot.generation?.status) ? snapshot.generation.status : 'open'
  } else {
    if (snapshot.plan?.id !== w.id) return { ...s, attempts: [] }
    record = snapshot.analysis || {}
    state = ['completed', 'failed'].includes(record.status) ? (TERMINAL.includes(record.outcome) ? record.outcome : record.status) : 'open'
  }
  const failed = state === 'partial' || state === 'failed'
  const code = record.error_code || (kind === 'generation' ? snapshot.analysis?.error_code : undefined)
  const receipt = {
    attempt_id: w.attemptId || id(w.runId || (kind === 'generation' ? snapshot.generation?.created_at : '') || w.token), flow_id: w.properties?.flow_id || 't-flow000000000', sequence: 1,
    kind, state, run_id: w.runId || (kind === 'production' ? 'run-legacy' : undefined), retry_of: w.properties?.retry_of,
    ...(snapshot.plan?.degrade_reason ? { degrade_reason: snapshot.plan.degrade_reason } : {}),
    // R25 #347: the backend freezes the generation counts (attempts.generation_summary, same rules as
    // workflow.generationSummary) and the plan modes into the receipt at settle.
    summary: { ...(kind === 'generation' && workflow ? Object.fromEntries(Object.entries(workflow.generationSummary(snapshot)).filter(([, v]) => v !== undefined)) : {}),
      ...Object.fromEntries(SUMMARY.filter(k => record[k] !== undefined && record[k] !== null).map(k => [k, record[k]])),
      ...(snapshot.plan?.mode ? { recommendation_mode: snapshot.plan.mode } : {}), ...(snapshot.plan?.confirmed_analysis ? { analysis_mode: snapshot.plan.confirmed_analysis } : {}) },
    ...(failed ? { error_code: code || 'unexpected', failure_stage: record.failure_stage || (kind === 'generation' ? snapshot.analysis?.failure_stage : undefined),
      upstream_error_type: record.upstream_error_type || (kind === 'generation' ? snapshot.analysis?.upstream_error_type : undefined),
      ...(record.secondary_error_codes ? { secondary_error_codes: record.secondary_error_codes, secondary_upstream_error_types: record.secondary_upstream_error_types } : {}) } : {}),
  }
  if (kind === 'generation' && !receipt.summary.route && snapshot.plan?.recommended_analysis) receipt.summary.route = snapshot.plan.recommended_analysis
  if (failed && kind === 'generation') receipt.summary.http_status = record.http_status ?? snapshot.analysis?.http_status
  if (failed && kind === 'generation' && receipt.summary.billable_calls_before_failure === undefined) receipt.summary.billable_calls_before_failure = snapshot.analysis?.billable_calls_before_failure
  if (kind === 'production' && !w.runId) s = { ...s, analysis: { ...(s.analysis || {}), run_id: 'run-legacy' } }
  return { ...s, attempts: [receipt], ...(kind === 'generation' && s.generation ? { generation: { ...s.generation, attempt_id: receipt.attempt_id } } : {}) }
}

/** Wrap a loaded workflow module's tracker so bare snapshots get the backend receipt. */
function withBackendReceipts(workflow) {
  const proto = workflow.WorkflowTracker.prototype
  if (proto.__receipts) return workflow
  const original = proto.observeStudio
  proto.observeStudio = function (w, snapshot) { return original.call(this, w, receiptFor(w, snapshot, workflow)) }
  proto.__receipts = true
  return workflow
}

module.exports = { withBackendReceipts, receiptFor }
