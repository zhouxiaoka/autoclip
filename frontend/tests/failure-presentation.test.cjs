const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const presentation = loadTs(path.resolve(__dirname, '../src/features/studio/failurePresentation.ts'))
const { presentFailure, resolveFailureCause, isKnownBudgetFailure } = presentation
const BUDGET = '这次制作已超过时间上限，已停止。请重试；服务商一直很慢时可以换一个更快的模型。'

function same(listInput, detailInput) {
  const list = presentFailure(listInput)
  const detail = presentFailure(detailInput)
  assert.deepEqual(
    { status: list.status, step: list.step, reason: list.reason, outcome: list.outcome, primary: list.primary },
    { status: detail.status, step: detail.step, reason: detail.reason, outcome: detail.outcome, primary: detail.primary },
  )
  return list
}

test('budget timeout is the same on the list and the detail, and is not an add-provider prompt', () => {
  const cause = {
    error: BUDGET,
    error_code: 'job_budget',
    failure_stage: 'analyze',
    phase: 'production',
    llm_calls: 9,
    billable_calls_before_failure: 8,
    connectionCount: 1,
    preservedCount: 0,
  }
  const view = same(cause, { ...cause })
  assert.equal(view.step, '分析')
  assert.equal(view.reason, BUDGET)
  assert.equal(view.outcome, '本次没有可用成果')
  assert.equal(view.primary.label, '重试制作')
  assert.equal(view.technical.requests, 9)
  assert.equal(view.technical.successes, 8)
  assert.equal(view.reason.includes('建议再加一个服务商'), false)
})

test('an old timeout row is budget only when the stored sentence is the budget sentence', () => {
  assert.equal(isKnownBudgetFailure('timeout', BUDGET), true)
  assert.equal(isKnownBudgetFailure('timeout', '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。'), false)
  const provider = same(
    { error: '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。', error_code: 'timeout', failure_stage: 'analyze', connectionCount: 1, preservedCount: 0 },
    { error: '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。', error_code: 'timeout', failure_stage: 'analyze', connectionCount: 1, preservedCount: 0 },
  )
  assert.equal(provider.primary.label, '重试')
  assert.equal(provider.reason.includes('建议再加一个服务商'), false)
})

test('screening is not labeled as download, and a missing stage is not guessed', () => {
  const screening = same(
    { error: '筛选时崩溃', error_code: 'unexpected', failure_stage: 'screening', preservedCount: 0 },
    { error: '筛选时崩溃', error_code: 'unexpected', failure_stage: 'screening', preservedCount: 0 },
  )
  assert.equal(screening.step, '筛选')
  const missing = presentFailure({ error: '筛选时崩溃', error_code: 'unexpected', preservedCount: 0 })
  assert.equal(missing.step, null)
})

test('kept results lead with viewing them, and a download connection does not open model settings', () => {
  const kept = same(
    { error: '后来的制作失败了', error_code: 'provider_error', failure_stage: 'render', preservedCount: 2 },
    { error: '后来的制作失败了', error_code: 'provider_error', failure_stage: 'render', preservedCount: 2 },
  )
  assert.equal(kept.primary.id, 'view_results')
  assert.equal(kept.outcome, '已保留 {{count}} 条成片')
  const download = same(
    { error: '下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。', error_code: 'connection', failure_stage: 'ingest', preservedCount: 0 },
    { error: '下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。', error_code: 'connection', failure_stage: 'download', preservedCount: 0 },
  )
  assert.equal(download.step, '下载')
  assert.equal(download.primary.label, '重试')
})

test('the card sentence stays short when the stored error is a long vendor message', () => {
  const vendor = 'Traceback (most recent call last): provider returned ' + 'x'.repeat(400) + ' sk-secret'
  const cases = [
    { error: vendor, error_code: 'timeout', failure_stage: 'analyze', brief: '响应超时了，可以重试。' },
    { error: vendor, error_code: 'job_budget', failure_stage: 'production', brief: '制作时间太长，已经停止。' },
    { error: vendor, error_code: 'connection', failure_stage: 'download', brief: '下载时网络中断了。' },
    { error: vendor, error_code: 'connection', failure_stage: 'render', brief: '网络中断了，可以重试。' },
    { error: vendor, error_code: 'service_restarted', failure_stage: 'production', brief: '应用刚重启，这次制作中断了。' },
    { error: vendor, error_code: 'llm_auth_invalid', upstream_error_type: 'invalid_key', brief: '密钥或权限有问题，请到设置里检查。' },
    { error: vendor, error_code: 'insufficient_quota', upstream_error_type: 'insufficient_quota', brief: '额度用完了，请检查余额。' },
    { error: vendor, error_code: 'rate_limited', brief: '请求太频繁，请稍后再试。' },
    { error: vendor, error_code: 'unexpected', brief: '制作中断了，可以重试。' },
  ]
  for (const item of cases) {
    const view = presentFailure({ ...item, preservedCount: 0 })
    assert.equal(view.brief, item.brief)
    assert.equal(view.brief.length < 40, true)
    assert.equal(view.brief.includes('sk-secret'), false)
    assert.equal(view.reason.startsWith('Traceback'), false)
    assert.notEqual(view.reason, vendor.slice(0, view.reason.length))
    assert.equal(view.primary !== null, true)
  }
  const kept = presentFailure({ error: vendor, error_code: 'timeout', preservedCount: 2 })
  assert.equal(kept.primary.id, 'view_results')
  assert.equal(kept.outcome, '已保留 {{count}} 条成片')
})

test('a receipt for this run wins over a placeholder generation', () => {
  const resolved = resolveFailureCause({
    analysis: { error_code: 'job_budget', failure_stage: 'analyze', phase: 'production', llm_calls: 9 },
    generation: { error_code: 'validation', error: '没有自动生成的成片，可选择备选片段继续生成' },
    receipt: { error_code: 'job_budget', failure_stage: 'analyze' },
  })
  assert.equal(resolved.error_code, 'job_budget')
  assert.equal(resolved.failure_stage, 'analyze')
  const mismatched = resolveFailureCause({
    analysis: { error_code: 'rate_limited', failure_stage: 'production', error: '请求过于频繁，请稍后重试。' },
    generation: { error_code: 'validation', error: '没有自动生成的成片，可选择备选片段继续生成' },
    receipt: null,
  })
  assert.equal(mismatched.error_code, 'rate_limited')
})
