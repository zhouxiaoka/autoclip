// C1: service_restarted generations report restart_reason on studio_generation_finished.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const workflow = require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))
const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../../backend/core/event_catalog.json'), 'utf8'))
const REASONS = ['user_quit', 'update', 'unknown', 'crash']

test('safeStudioProperties keeps restart_reason and drops other shutdown labels', () => {
  for (const value of REASONS) {
    assert.equal(workflow.safeStudioProperties({ restart_reason: value }).restart_reason, value)
  }
  for (const value of ['clean', 'parent_lost', 'unacked', 'system_kill']) {
    assert.equal(workflow.safeStudioProperties({ restart_reason: value }).restart_reason, undefined)
  }
})

test('generation snapshot details keep restart_reason next to shutdown_kind', () => {
  const details = workflow.safeStudioProperties({
    outcome: 'error',
    error_code: 'service_restarted',
    failure_stage: 'render',
    shutdown_kind: 'clean',
    restart_reason: 'update',
  })
  assert.equal(details.restart_reason, 'update')
  assert.equal(details.shutdown_kind, 'clean')
  assert.equal(details.error_code, 'service_restarted')
})

test('catalog registers restart_reason on studio_generation_finished', () => {
  assert.deepEqual(catalog.enums.restart_reason, REASONS)
  assert.equal(catalog.events.studio_generation_finished.enums.restart_reason, 'restart_reason')
  const described = catalog.events.studio_generation_finished.optional_properties.restart_reason
  assert.equal(described.values, 'restart_reason')
})
