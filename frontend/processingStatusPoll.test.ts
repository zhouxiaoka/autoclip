import assert from 'node:assert/strict'
import test from 'node:test'

import {
  classifyStatusPollError,
  httpStatusOf,
  normalizeProcessingPhase,
  shouldStopProcessingPoll,
  toProcessingView,
} from './src/utils/processingStatusPoll.ts'

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

test('TaskProgressModal stops on completed, failed, 404, and 5xx', () => {
  const completed = toProcessingView({ task_status: 'completed', task_progress: 100 })
  const failed = toProcessingView({ task_status: 'failed', error_message: 'clip failed' })
  assert.equal(shouldStopProcessingPoll({ phase: completed.status }), true)
  assert.equal(completed.status, 'completed')
  assert.equal(shouldStopProcessingPoll({ phase: failed.status }), true)
  assert.equal(failed.status, 'error')
  assert.equal(failed.error_message, 'clip failed')

  const missing = { response: { status: 404 } }
  const server = { response: { status: 500 } }
  assert.equal(classifyStatusPollError(missing), 'not_found')
  assert.equal(classifyStatusPollError(server), 'server')
  assert.equal(shouldStopProcessingPoll({ error: missing }), true)
  assert.equal(shouldStopProcessingPoll({ error: server }), true)
  assert.equal(shouldStopProcessingPoll({ httpStatus: 503 }), true)
})

test('TaskProgressModal keeps polling after a timeout and warns only as a transient error', () => {
  const timeout = { code: 'ECONNABORTED' }
  const network = { code: 'ERR_NETWORK' }
  assert.equal(classifyStatusPollError(timeout), 'timeout')
  assert.equal(classifyStatusPollError(network), 'transient')
  assert.equal(shouldStopProcessingPoll({ error: timeout }), false)
  assert.equal(shouldStopProcessingPoll({ error: network }), false)
  assert.equal(httpStatusOf(timeout), undefined)
  assert.equal(shouldStopProcessingPoll({ httpStatus: 408 }), false)
})

test('view keeps orchestrator task_progress when status is absent', () => {
  const view = toProcessingView({ task_status: 'running', task_progress: 40, error_message: null })
  assert.equal(view.status, 'processing')
  assert.equal(view.progress, 40)
  assert.equal(view.error_message, undefined)
})
