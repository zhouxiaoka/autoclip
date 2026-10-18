// R25 #415: a stored identity is ONE record; terminal events never stitch run and analysis fields.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')

const workflow = require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))

function finished(summary, analysis) {
  const events = [], store = new Map()
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }
  const t = new workflow.WorkflowTracker(storage, () => true, (name, props) => { events.push({ name, props }); return true })
  const attempt = 't-aaaaaaaaaaaaaaaa'
  t.watch('studio-generation', 'p1')
  t.observeStudio(t.list()[0], {
    generation: { status: 'failed', attempt_id: attempt },
    analysis,
    attempts: [{ attempt_id: attempt, flow_id: 't-ffffffffffffffff', sequence: 1, kind: 'generation', state: 'failed', summary }],
  })
  return events.find(e => e.name === 'studio_generation_finished')
}

test('#332 the results page does not emit studio_generation_finished (the backend settles that terminal)', () => {
  // A half identity on the receipt and a full identity on analysis used to be stitched by the frontend projector.
  // That projector is gone: opening the page must not emit the success-rate terminal at all.
  const event = finished(
    { provider: 'glm', model: 'glm-4', base_url_host: 'other.example', http_status: 503 },
    { status: 'failed', phase: 'production', provider: 'kimi', config_source: 'preset', model: 'kimi-k2', base_url_host: 'api.moonshot.cn', http_status: 429, upstream_error_type: 'rate_limited' },
  )
  assert.equal(event, undefined)
})

test('#332 an unpaired legacy screening identity reads as empty, not half an identity', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'kimi' } })
  assert.equal(id.provider, undefined)
  assert.equal(id.config_source, undefined)
})

test('#332 a half screening_identity is ignored; the paired flat identity is used whole', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'glm', config_source: 'customized', screening_identity: { provider: 'kimi' } } })
  assert.deepEqual({ ...id }, { provider: 'glm', config_source: 'customized' })
})
