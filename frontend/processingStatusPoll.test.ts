import assert from 'node:assert/strict'
import test from 'node:test'

import {
  httpStatusOf,
  normalizeProcessingPhase,
  shouldStopProcessingPoll,
  toProcessingView,
} from './src/pages/processingStatusPoll.ts'

test('completion and failure stop polling, including task_status from the API', () => {
  assert.equal(normalizeProcessingPhase({ status: 'completed' }), 'completed')
  assert.equal(normalizeProcessingPhase({ task_status: 'completed' }), 'completed')
  assert.equal(normalizeProcessingPhase({ task_status: 'failed' }), 'error')
  assert.equal(normalizeProcessingPhase({ status: 'error' }), 'error')
  assert.equal(normalizeProcessingPhase({ task_status: 'cancelled' }), 'error')
  assert.equal(normalizeProcessingPhase({ status: 'pending' }), 'pending')
  assert.equal(normalizeProcessingPhase({ task_status: 'running' }), 'processing')

  assert.equal(shouldStopProcessingPoll({ phase: 'completed' }), true)
  assert.equal(shouldStopProcessingPoll({ phase: 'error' }), true)
  assert.equal(shouldStopProcessingPoll({ phase: 'processing' }), false)
  assert.equal(shouldStopProcessingPoll({ phase: 'pending' }), false)
})

test('404 and 5xx stop polling; timeouts do not', () => {
  assert.equal(shouldStopProcessingPoll({ httpStatus: 404 }), true)
  assert.equal(shouldStopProcessingPoll({ httpStatus: 500 }), true)
  assert.equal(shouldStopProcessingPoll({ httpStatus: 503 }), true)
  assert.equal(shouldStopProcessingPoll({ httpStatus: 408 }), false)
  assert.equal(shouldStopProcessingPoll({}), false)
  assert.equal(httpStatusOf({ response: { status: 404 } }), 404)
  assert.equal(httpStatusOf({ code: 'ECONNABORTED' }), undefined)
})

test('view keeps orchestrator task_progress when status is absent', () => {
  const view = toProcessingView({ task_status: 'running', task_progress: 40, error_message: null })
  assert.equal(view.status, 'processing')
  assert.equal(view.progress, 40)
  assert.equal(view.error_message, undefined)
})
