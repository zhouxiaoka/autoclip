const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(name, mocks = {}, globals = {}) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, {
    exports: module.exports, module, Date, Math, console,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key' },
    require: (id) => {
      if (id in mocks) return mocks[id]
      throw new Error(`Unexpected dependency: ${id}`)
    },
    ...globals,
  }, { filename: file })
  return module.exports
}

const workflow = load('workflow')

test('run-level allowlist keeps provider fields and drops keys, prompts and full URLs', () => {
  const props = workflow.safeStudioProperties({
    provider: 'api88', model: 'gpt-4o-mini', base_url_host: '88api.ai',
    http_status: 429, upstream_error_type: 'rate_limited', failure_stage: 'analyze',
    billable_calls_before_failure: 2, retry_count: 1, prompt_tokens: 40, llm_calls: 3,
    code: 'whisper_not_installed', has_subtitle: false, blocked: true,
    api_key: 'sk-secret', prompt: 'private instruction', caption: 'secret subtitle',
    base_url: 'https://88api.ai/v1/chat/completions',
  })
  assert.equal(props.provider, 'api88')
  assert.equal(props.model, 'gpt-4o-mini')
  assert.equal(props.base_url_host, '88api.ai')
  assert.equal(props.upstream_error_type, 'rate_limited')
  assert.equal(props.billable_calls_before_failure, 2)
  assert.equal(props.blocked, true)
  assert.equal(props.code, 'whisper_not_installed')
  assert.equal(props.api_key, undefined)
  assert.equal(props.base_url, undefined)
  assert.equal(JSON.stringify(props).includes('sk-'), false)
  assert.equal(JSON.stringify(props).includes('private'), false)
  assert.equal(JSON.stringify(props).includes('chat/completions'), false)
  const rejected = workflow.safeStudioProperties({
    provider: 'evil', model: 'sk-abc123', base_url_host: 'https://evil.example/v1',
    upstream_error_type: 'authentication', http_status: 200,
  })
  assert.equal(rejected.provider, undefined)
  assert.equal(rejected.model, undefined)
  assert.equal(rejected.base_url_host, undefined)
  assert.equal(rejected.upstream_error_type, undefined)
  assert.equal(rejected.http_status, undefined)
})

test('generation and production finished carry run identity; failures keep stage and code', () => {
  const events = []
  const storage = { getItem: () => null, setItem() {}, removeItem() {} }
  const tracker = new workflow.WorkflowTracker(storage, () => true, (event, props) => {
    events.push({ event, props }); return true
  })
  tracker.watch('studio-generation', 'p1')
  tracker.observeStudio(tracker.list()[0], {
    generation: {
      status: 'failed', error_code: 'provider_error', failure_stage: 'analyze',
      http_status: 429, provider: 'api88', model: 'gpt-4o-mini', base_url_host: '88api.ai',
      upstream_error_type: 'rate_limited', billable_calls_before_failure: 1, retry_count: 2,
    },
    analysis: { status: 'failed', phase: 'production' },
    plan: { id: 'plan', mode: 'ai', recommended_analysis: 'subtitle' },
  })
  const finished = events.find(item => item.event === 'studio_generation_finished').props
  assert.equal(finished.provider, 'api88')
  assert.equal(finished.model, 'gpt-4o-mini')
  assert.equal(finished.base_url_host, '88api.ai')
  assert.equal(finished.upstream_error_type, 'rate_limited')
  assert.equal(finished.failure_stage, 'analyze')
  assert.equal(finished.error_code, 'provider_error')
  assert.equal(finished.billable_calls_before_failure, 1)
  assert.equal(finished.retry_count, 2)

  const prod = []
  const production = new workflow.WorkflowTracker(storage, () => true, (event, props) => {
    prod.push({ event, props }); return true
  })
  production.watch('studio-production', 'plan', 'p1')
  production.observeStudio(production.list()[0], {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: {
      status: 'failed', outcome: 'failed', failure_stage: 'analyze', error_code: 'authentication',
      provider: 'openai', model: 'gpt-4o-mini', base_url_host: 'api.openai.com',
      upstream_error_type: 'invalid_key', http_status: 401, billable_calls_before_failure: 0,
    },
  })
  const row = prod.find(item => item.event === 'studio_production_finished').props
  assert.equal(row.failure_stage, 'analyze')
  assert.equal(row.provider, 'openai')
  assert.equal(row.upstream_error_type, 'invalid_key')
  assert.equal(row.error_code, 'authentication')

  const screen = []
  const screening = new workflow.WorkflowTracker(storage, () => true, (event, props) => {
    screen.push({ event, props }); return true
  })
  screening.watch('studio-screen', 'p1')
  screening.observeStudio(screening.list()[0], {
    analysis: { status: 'failed', phase: 'screening', error_code: 'source_no_audio', failure_stage: 'ingest' },
  })
  const screened = screen.find(item => item.event === 'studio_screen_finished').props
  assert.equal(screened.outcome, 'failed')
  assert.equal(screened.error_code, 'source_no_audio')
  assert.equal(screened.failure_stage, 'ingest')
})

test('trackAsrReadiness posts the allowlisted probe', () => {
  const events = []
  const studio = load('studio', {
    './posthog': { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } },
    './observer': { workflow: { generation: () => 1, active: () => true, list: () => [], rememberProject() {}, observeStudio() {}, context: () => ({}) } },
    './workflow': workflow,
  })
  studio.trackAsrReadiness({
    provider: 'whisper_local', code: 'whisper_not_installed', has_subtitle: false, blocked: true,
    model: 'sk-secret', url: 'https://private.example',
  })
  assert.equal(events[0].event, 'asr_readiness_checked')
  assert.equal(events[0].props.provider, 'whisper_local')
  assert.equal(events[0].props.blocked, true)
  assert.equal(JSON.stringify(events).includes('sk-'), false)
})

test('Sentry keeps only a valid anonymous id and drops emails', () => {
  let config
  let user
  const source = fs.readFileSync(path.join(__dirname, '../src/desktop/sentry.ts'), 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, {
    exports: module.exports, module, console,
    __env: { PROD: true, VITE_PUBLIC_SENTRY_DSN: 'https://public@example.invalid/1', VITE_APP_VERSION: '1.5.8' },
    require: (id) => {
      if (id === '@sentry/react') return {
        init: (cfg) => { config = cfg },
        setUser: (value) => { user = value },
        captureException() {},
        withScope(fn) { fn({ setTag() {} }) },
      }
      throw new Error(id)
    },
    localStorage: { getItem: () => null, setItem() {} },
  })
  module.exports.initSentry()
  module.exports.setAnonymousUser('018f6b2a-7c3d-7b2a-8c11-111111111111')
  assert.equal(user.id, '018f6b2a-7c3d-7b2a-8c11-111111111111')
  const event = config.beforeSend({
    event_id: 'e', release: 'r',
    user: { id: '018f6b2a-7c3d-7b2a-8c11-111111111111', email: 'a@b.com', ip_address: '1.2.3.4' },
    exception: { values: [{ type: 'Error', value: 'private', stacktrace: { frames: [{ filename: 'app.js', lineno: 1 }] } }] },
  })
  assert.equal(event.user.id, '018f6b2a-7c3d-7b2a-8c11-111111111111')
  assert.equal(Object.keys(event.user).join(','), 'id')
  assert.equal(JSON.stringify(event).includes('a@b.com'), false)
  assert.equal(JSON.stringify(event).includes('private'), false)
  module.exports.setAnonymousUser('short')
  assert.equal(user, null)
})
