// R19 #108: partial page 「重试这条」 -> real StudioResults onRetry -> real studioApi -> real tracker.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
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
