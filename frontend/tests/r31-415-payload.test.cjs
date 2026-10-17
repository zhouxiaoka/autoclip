// R31 #415 (Dong I565): runtime payload tests are the primary guard for the frontend serializer.
// Dirty studio records go through the real WorkflowTracker; every terminal event's attribution properties
// must be a subset of ATTRIBUTION_KEYS with valid values, whatever the reader code looks like.
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
const SECRET = 'sk-r31-SECRET-0000 https://user:pw@private.example/v1 /Users/someone/clip.mp4'
const DIRTY = { attribution_source: 'request', provider: 'kimi', config_source: 'customized', model: 'kimi-k2',
  base_url_host: 'kimi.fixture.example', http_status: '503;drop', upstream_error_type: 'upstream_unavailable', failure_stage: 'analyze',
  raw_message: SECRET, api_key: SECRET, url: SECRET }
const ATTR = new Set(['attribution_source', 'provider', 'config_source', 'model', 'base_url_host', 'http_status', 'upstream_error_type', 'failure_stage'])

function checkClean(props) {
  const text = JSON.stringify(props)
  assert.ok(!text.includes('SECRET') && !text.includes('private.example') && !text.includes('/Users/'), text)
  assert.ok(!text.includes('503;drop'), text)
  assert.equal(props.http_status, undefined, text)
}

test('I565: pickAttribution copies only whitelisted keys with valid values and freezes the result', () => {
  for (const status of ['503;drop', '503', true, 302, 600, 503.5]) {
    const out = workflow.pickAttribution({ ...DIRTY, status: 'failed', http_status: status })
    assert.ok(Object.keys(out).every(k => workflow.ATTRIBUTION_KEYS.includes(k)), JSON.stringify(out))
    assert.equal(out.http_status, undefined, String(status))
    assert.ok(Object.isFrozen(out))
  }
  assert.equal(workflow.pickAttribution({ ...DIRTY, status: 'failed', http_status: 503 }).http_status, 503)
  assert.deepEqual({ ...workflow.pickAttribution({ status: 'failed', attribution_source: 'guess', provider: 'kimi' }) }, {})
})

test('I565: dirty production / generation / screen records never put a non-whitelisted or invalid value in an event', () => {
  const cases = [
    observe('studio-production', 'plan', { plan: { id: 'plan', confirmed_analysis: 'subtitle' }, analysis: { ...DIRTY, status: 'failed', error_code: 'provider_error' } }, 'p1'),
    observe('studio-generation', 'p1', { generation: { ...DIRTY, status: 'failed', error_code: 'provider_error' }, plan: { id: 'plan', mode: 'ai' } }),
    observe('studio-screening', 'p1', { analysis: { ...DIRTY, status: 'failed', phase: 'screening', error_code: 'provider_error' }, plan: { id: 'plan' } }),
  ]
  let finished = 0
  for (const events of cases) for (const { event, props } of events) {
    if (!event.endsWith('_finished')) continue
    finished++
    checkClean(props)
  }
  assert.ok(finished >= 2, 'terminal events were emitted')
})

test('X14: a production record with status=partial and no outcome keeps its failure fields', () => {
  const events = observe('studio-production', 'plan', {
    plan: { id: 'plan', confirmed_analysis: 'subtitle' },
    analysis: { status: 'partial', error_code: 'provider_error', attribution_source: 'request', provider: 'kimi', config_source: 'customized',
      http_status: 503, upstream_error_type: 'upstream_unavailable', failure_stage: 'analyze' },
  }, 'p1')
  const done = events.find(e => e.event === 'studio_production_finished')
  assert.ok(done, JSON.stringify(events))
  assert.equal(done.props.outcome, 'partial')
  assert.equal(done.props.http_status, 503)
  assert.equal(done.props.upstream_error_type, 'upstream_unavailable')
  assert.equal(done.props.failure_stage, 'analyze')
})
