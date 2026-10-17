// R27 #415 I420 + design: every studio finished event reads attribution through pickAttribution (one record, whole).
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(name) {
  const file = path.join(__dirname, '../src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, Date, Math, console, __env: { DEV: false },
    require: (id) => { throw new Error(`Unexpected dependency: ${id}`) } }, { filename: file })
  return module.exports
}
const workflow = load('workflow')
const storage = { getItem: () => null, setItem() {}, removeItem() {} }
function observe(kind, id, state, extra) {
  const events = []
  const t = new workflow.WorkflowTracker(storage, () => true, (event, props) => { events.push({ event, props }); return true })
  t.watch(kind, id, extra)
  t.observeStudio(t.list()[0], state)
  return events
}

test('I420: studio_screen_finished carries attribution_source; a local failure has no upstream', () => {
  const events = observe('studio-screen', 'p1', {
    analysis: { status: 'failed', phase: 'screening', error_code: 'store_lock_timeout', failure_stage: 'screening',
      attribution_source: 'local', provider: 'glm', config_source: 'preset', upstream_error_type: 'upstream_unavailable', http_status: 503 },
  })
  const screen = events.find(e => e.event === 'studio_screen_finished')
  assert.ok(screen, JSON.stringify(events))
  assert.equal(screen.props.attribution_source, 'local')
  assert.equal(screen.props.upstream_error_type, undefined)
  assert.equal(screen.props.http_status, undefined)
})

test('I420: generation reads ONE record whole (generation local beats a complete analysis phase identity)', () => {
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'failed', error_code: 'store_lock_timeout', attribution_source: 'local' },
    analysis: { status: 'failed', provider: 'kimi', config_source: 'customized', attribution_source: 'phase', http_status: 503, upstream_error_type: 'upstream_unavailable' },
    plan: { id: 'plan', mode: 'ai' },
  })
  const props = events.find(e => e.event === 'studio_generation_finished').props
  assert.equal(props.attribution_source, 'local')
  assert.equal(props.provider, undefined)
  assert.equal(props.http_status, undefined)
})

test('production reads through pickAttribution: local status is dropped, half identity is no identity', () => {
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'failed', outcome: 'failed', error_code: 'store_lock_timeout', attribution_source: 'local',
      provider: 'openai', http_status: 503, upstream_error_type: 'upstream_unavailable' },
  }, 'p1')
  const props = events.find(e => e.event === 'studio_production_finished').props
  assert.equal(props.attribution_source, 'local')
  assert.equal(props.provider, undefined)
  assert.equal(props.http_status, undefined)
  assert.equal(props.upstream_error_type, undefined)
})

test('pickAttribution mirrors read_attribution (one record)', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(workflow.pickAttribution({ status: 'failed', attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503 }))),
    { provider: 'kimi', config_source: 'customized', attribution_source: 'request', http_status: 503 })
  assert.equal(workflow.pickAttribution({ status: 'completed', attribution_source: 'request', provider: 'kimi', config_source: 'customized', http_status: 503 }).http_status, undefined)
  assert.equal(workflow.attributionOf, undefined, 'the old multi-record reader is gone')
  assert.equal(workflow.pickAttribution.length, 1, 'one record, no list')
})

test('I451: completed + outcome=partial keeps its failure fields; no status is undecided (kept)', () => {
  const partial = workflow.pickAttribution({ status: 'completed', outcome: 'partial', attribution_source: 'phase', provider: 'glm', config_source: 'preset', failure_stage: 'render', http_status: 503 })
  assert.equal(partial.failure_stage, 'render'); assert.equal(partial.http_status, 503)
  const bare = workflow.pickAttribution({ attribution_source: 'phase', http_status: 502 })
  assert.equal(bare.http_status, 502)
  assert.equal(workflow.isFailedTerminal({ status: 'completed' }), false)
  assert.equal(workflow.isFailedTerminal({}), null)
})

test('I453: generation never borrows the analysis record (no source_blocked + kimi + 503 mix)', () => {
  const events = observe('studio-generation', 'p1', {
    generation: { status: 'failed', error_code: 'source_blocked', failure_stage: 'ingest' },
    analysis: { status: 'failed', provider: 'kimi', config_source: 'customized', attribution_source: 'request', http_status: 503, upstream_error_type: 'upstream_unavailable' },
    plan: { id: 'plan', mode: 'ai' },
  })
  const props = events.find(e => e.event === 'studio_generation_finished').props
  assert.equal(props.provider, undefined); assert.equal(props.http_status, undefined); assert.equal(props.upstream_error_type, undefined)
  assert.equal(props.failure_stage, 'ingest')
})

test('I451: a completed+partial production keeps stage/status in its event', () => {
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'completed', outcome: 'partial', failure_stage: 'analyze', attribution_source: 'phase', provider: 'glm', config_source: 'preset', http_status: 503, upstream_error_type: 'upstream_unavailable' },
  }, 'p1')
  const props = events.find(e => e.event === 'studio_production_finished').props
  assert.equal(props.failure_stage, 'analyze'); assert.equal(props.http_status, 503)
})

test('I424: a store_lock_timeout failure shows the i18n key', () => {
  const src = fs.readFileSync(path.join(__dirname, '../src/utils/llmFailure.ts'), 'utf8')
  assert.match(src, /if \(code === STORE_LOCK_TIMEOUT\) return STORE_LOCK_TIMEOUT_TEXT/)
})
