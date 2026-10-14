const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const root = path.join(__dirname, '..', '..')
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'docs/analytics/event_catalog.json'), 'utf8'))

function load() {
  const file = path.join(__dirname, '../src/analytics/eventCatalog.ts')
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, Set, Map, Object, String, JSON, URL }, { filename: file })
  return module.exports
}

function walk(dir) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const next = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walk(next))
    else if (/\.tsx?$/.test(entry.name)) out.push(next)
  }
  return out
}

const catalogApi = load()

test('catalog lists the success-rate funnel and attribution enums', () => {
  const names = catalogApi.listedEvents(catalog)
  for (const name of [
    'app_installed', 'app_opened', 'provider_validation_finished', 'asr_readiness_checked',
    'studio_import_requested', 'studio_generation_finished', 'studio_production_finished',
    'llm_request_finished', 'studio_download_saved',
  ]) {
    assert.equal(names.has(name), true, name)
  }
  assert.ok(catalog.attribution.user_caused_upstream_types.includes('insufficient_quota'))
  assert.ok(catalog.attribution.user_caused_error_codes.includes('source_no_audio'))
  assert.ok(catalog.attribution.environment_error_codes.includes('source_blocked'))
})

test('unregistered events and missing required fields fail', () => {
  const unknown = catalogApi.validateEvent('not_a_real_event', {}, catalog)
  assert.equal(unknown.length, 1)
  assert.equal(unknown[0], 'unregistered event: not_a_real_event')
  const missing = catalogApi.validateEvent('llm_request_finished', { provider: 'openai' }, catalog)
  assert.ok(missing.some(item => item.includes('missing required fields')))
  assert.ok(String(missing[0]).includes('kind') && String(missing[0]).includes('outcome'))
  const ok = catalogApi.validateEvent('llm_request_finished', {
    success_rate_schema_version: 1, provider: 'openai', kind: 'text', outcome: 'success', duration_ms: 4,
  }, catalog)
  assert.equal(ok.length, 0)
})

test('privacy rules reject keys, secrets and full URL paths', () => {
  const errors = catalogApi.validateEvent('llm_request_finished', {
    success_rate_schema_version: 1, provider: 'openai', kind: 'text', outcome: 'success', duration_ms: 1,
    api_key: 'x', prompt: '用户口播', href: 'https://api.openai.com/v1/chat',
  }, catalog)
  assert.ok(errors.some(item => item.includes('forbidden property')))
  assert.ok(errors.some(item => item.includes('full URL')))
})

test('frontend producers are all registered in the catalog', () => {
  const allowed = new Set([...catalogApi.listedEvents(catalog), ...catalogApi.ignoreEvents(catalog)])
  const found = new Set()
  for (const file of walk(path.join(root, 'frontend/src'))) {
    for (const name of catalogApi.extractProducerEvents(fs.readFileSync(file, 'utf8'))) found.add(name)
  }
  const leftover = [...found].filter(name => !allowed.has(name)).sort()
  assert.equal(leftover.join(','), '')
})

test('trackAsrReadiness payload matches the catalog', () => {
  const workflowSource = fs.readFileSync(path.join(__dirname, '../src/analytics/workflow.ts'), 'utf8')
  const studioSource = fs.readFileSync(path.join(__dirname, '../src/analytics/studio.ts'), 'utf8')
  const workflow = { exports: {} }
  vm.runInNewContext(ts.transpileModule(workflowSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports: workflow.exports, module: workflow, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL })
  const events = []
  const studioModule = { exports: {} }
  vm.runInNewContext(ts.transpileModule(studioSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, {
    exports: studioModule.exports, module: studioModule,
    require: (id) => {
      if (id === './posthog') return { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } }
      if (id === './observer') return { workflow: { generation: () => 1, active: () => true, list: () => [], rememberProject() {}, observeStudio() {}, context: () => ({}) } }
      if (id === './workflow') return workflow.exports
      throw new Error(id)
    },
  })
  studioModule.exports.trackAsrReadiness({
    provider: 'whisper_local', code: 'whisper_not_installed', has_subtitle: false, blocked: true,
    api_key: 'sk-secret', prompt: '用户口播',
  })
  assert.equal(events[0].event, 'asr_readiness_checked')
  const errors = catalogApi.validateEvent(events[0].event, events[0].props, catalog)
  assert.equal(errors.join(';'), '')
  assert.equal(events[0].props.success_rate_schema_version, 1)
  assert.equal(JSON.stringify(events).includes('sk-'), false)
})

test('os aliases normalize to macos/windows/linux', () => {
  assert.equal(catalogApi.normalizeOs('darwin', catalog), 'macos')
  assert.equal(catalogApi.normalizeOs('win32', catalog), 'windows')
  assert.equal(catalogApi.normalizeOs('linux', catalog), 'linux')
})

test('feedback_submitted may include user text and contact', () => {
  assert.equal(catalog.events.feedback_submitted.kind, 'user_submitted')
  assert.deepEqual(catalog.events.feedback_submitted.allow, ['text', 'contact'])
  const errors = catalogApi.validateEvent('feedback_submitted', {
    text: '进度停住了', contact: 'person@example.com',
  }, catalog)
  assert.equal(errors.join(';'), '')
})

test('auto-collected events still reject user content', () => {
  const errors = catalogApi.validateEvent('llm_request_finished', {
    success_rate_schema_version: 1, provider: 'openai', kind: 'text', outcome: 'success', duration_ms: 1,
    text: '用户口播', contact: 'person@example.com',
  }, catalog)
  assert.ok(errors.some(item => item.includes('user content')))
})
