const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load() {
  const file = path.join(__dirname, '../src/analytics/successRateContract.ts')
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, URL }, { filename: file })
  return module.exports
}

const contract = load()
const SECRET = 'sk-live-secret-should-never-leak'
const PROMPT = '用户口播：把这段广告词发到抖音'

test('hostname helper keeps domain only and never returns a key or path', () => {
  assert.equal(contract.hostnameOfBaseUrl('https://88api.ai/v1/chat/completions'), '88api.ai')
  assert.equal(contract.hostnameOfBaseUrl(`https://user:${SECRET}@api.deepseek.com/v1`), 'api.deepseek.com')
  assert.equal(contract.hostnameOfBaseUrl('http://127.0.0.1:11434/v1'), 'local')
  assert.equal(contract.hostnameOfBaseUrl('http://localhost:1234/v1'), 'local')
  assert.equal(contract.hostnameOfBaseUrl(SECRET), undefined)
  assert.equal(JSON.stringify(contract.hostnameOfBaseUrl(`https://88api.ai/v1?api_key=${SECRET}`)).includes('sk-'), false)
})

test('request sanitizer drops secrets, prompts and full URLs', () => {
  const props = contract.sanitizeLlmRequestProperties({
    provider: 'api88',
    model: 'gpt-4o-mini',
    base_url: `https://user:${SECRET}@88api.ai/v1/chat/completions?api_key=${SECRET}`,
    kind: 'vision',
    stage: 'screening',
    http_status: 403,
    upstream_error_type: 'permission_denied',
    prompt_tokens: 80,
    retry_count: 0,
    duration_ms: 12,
    outcome: 'error',
    api_key: SECRET,
    prompt: PROMPT,
    url: 'https://88api.ai/v1/chat/completions',
  })
  const dumped = JSON.stringify(props)
  assert.equal(props.success_rate_schema_version, 1)
  assert.equal(props.provider, 'api88')
  assert.equal(props.base_url_host, '88api.ai')
  assert.equal(props.upstream_error_type, 'permission_denied')
  assert.equal(dumped.includes(SECRET), false)
  assert.equal(dumped.includes(PROMPT), false)
  assert.equal(dumped.includes('/v1'), false)
})

test('run sanitizer rejects unknown enums and success HTTP statuses', () => {
  const props = contract.sanitizeRunProperties({
    provider: 'mystery',
    model: 'ok-model',
    failure_stage: 'private-stage',
    http_status: 200,
    upstream_error_type: 'authentication',
    billable_calls_before_failure: 0,
    retry_count: 2,
  })
  assert.equal(props.provider, undefined)
  assert.equal(props.model, 'ok-model')
  assert.equal(props.failure_stage, undefined)
  assert.equal(props.http_status, undefined)
  assert.equal(props.upstream_error_type, undefined)
  assert.equal(props.billable_calls_before_failure, 0)
  assert.equal(props.retry_count, 2)
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
