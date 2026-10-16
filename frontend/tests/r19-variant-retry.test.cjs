// R19 #108: partial page 「重试这条」 -> real StudioResults onRetry -> real studioApi -> real tracker.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')
const { loadTs } = require('./load-ts.cjs')

const { setup, renderResults } = require('./helpers/studio-harness.cjs')

test('R19/R20 #108 partial page 「重试这条」: new generation attempt_id with retry_of -> partial attempt', async () => {
  const { events } = await require('./helpers/variant-retry-flow.cjs').run()
  const gen = events.filter(e => e.event === 'studio_generation_finished').map(e => e.props)
  assert.equal(gen.length, 2)
  assert.equal(gen[0].outcome, 'partial')
  assert.notEqual(gen[1].attempt_id, gen[0].attempt_id)       // never reuses the partial attempt_id
  assert.equal(gen[1].retry_of, gen[0].attempt_id)
  assert.equal(gen[1].outcome, 'success')
  const variant = events.filter(e => e.event === 'studio_variant_finished').map(e => e.props)
  assert.equal(variant.length, 1)
})

test('R20 #123 retry endpoint returns the variant: the watch follows variant.render_job_id', async () => {
  const { tracker } = await require('./helpers/variant-retry-flow.cjs').run({ stopAfterClick: true })
  assert.equal(tracker.list().filter(w => w.kind === 'studio-variant' && w.id === 'v-bad').at(-1).runId, 'job-2')
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
