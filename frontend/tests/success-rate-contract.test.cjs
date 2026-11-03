const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

function load() {
  return loadTs(path.join(__dirname, '../src/analytics/successRateContract.ts'))
}

const contract = load()
const SECRET = 'sk-live-secret-should-never-leak'

test('hostname helper keeps domain only and never returns a key or path', () => {
  assert.equal(contract.hostnameOfBaseUrl('https://88api.ai/v1/chat/completions'), '88api.ai')
  assert.equal(contract.hostnameOfBaseUrl(`https://user:${SECRET}@api.deepseek.com/v1`), 'api.deepseek.com')
  assert.equal(contract.hostnameOfBaseUrl('http://127.0.0.1:11434/v1'), 'local')
  assert.equal(contract.hostnameOfBaseUrl('http://localhost:1234/v1'), 'local')
  assert.equal(contract.hostnameOfBaseUrl(SECRET), undefined)
  assert.equal(JSON.stringify(contract.hostnameOfBaseUrl(`https://88api.ai/v1?api_key=${SECRET}`)).includes('sk-'), false)
})

test('studio send path rejects unknown enums and success HTTP statuses', () => {
  const workflow = loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))
  const props = workflow.safeStudioProperties({
    provider: 'mystery',
    model: 'ok-model',
    failure_stage: 'private-stage',
    http_status: 200,
    upstream_error_type: 'authentication',
    billable_calls_before_failure: 0,
    retry_count: 2,
    degrade_count: 3,
  })
  assert.equal(props.provider, undefined)
  assert.equal(props.model, 'ok-model')
  assert.equal(props.failure_stage, undefined)
  assert.equal(props.http_status, undefined)
  assert.equal(props.upstream_error_type, undefined)
  assert.equal(props.billable_calls_before_failure, 0)
  assert.equal(props.retry_count, 2)
  assert.equal(props.degrade_count, 3)
})

test('validation sanitizer maps ok to success and never keeps secrets', () => {
  const props = contract.sanitizeProviderValidationProperties({
    provider: 'api88',
    base_url: `https://88api.ai/v1?api_key=${SECRET}`,
    result: 'ok',
    error_type: 'not-a-type',
    api_key: SECRET,
    model: 'gpt-4o',
  })
  const dumped = JSON.stringify(props)
  assert.equal(props.result, 'success')
  assert.equal(props.base_url_host, '88api.ai')
  assert.equal(props.upstream_error_type, undefined)
  assert.equal(props.model, undefined)
  assert.equal(dumped.includes(SECRET), false)
  assert.equal(dumped.includes('/v1'), false)
})

test('hint keys and retryable set cover every upstream type', () => {
  for (const type of contract.UPSTREAM_ERROR_TYPES) {
    assert.ok(contract.UPSTREAM_HINT_KEYS[type])
    assert.equal(typeof contract.hintKeyForUpstreamError(type), 'string')
  }
  assert.equal(
    Array.from(contract.RETRYABLE_UPSTREAM_ERROR_TYPES).join(','),
    'rate_limited,upstream_unavailable,timeout,connection',
  )
  assert.equal(contract.isRetryableUpstreamError('rate_limited'), true)
  assert.equal(contract.isRetryableUpstreamError('invalid_key'), false)
})
