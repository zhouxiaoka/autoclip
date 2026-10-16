// R25 #415: a stored identity is ONE record; terminal events never stitch run and analysis fields.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/analytics/workflow.ts'), 'utf8')
const mod = {}
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
  { exports: mod, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL })
const workflow = mod

function finished(state) {
  const events = [], store = new Map()
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: k => store.delete(k) }
  const t = new workflow.WorkflowTracker(storage, () => true, (name, props) => { events.push({ name, props }); return true })
  t.watch('studio-generation', 'p1')
  t.observeStudio(t.list()[0], state)
  return events.find(e => e.name === 'studio_generation_finished').props
}

test('#332 generation_finished takes provider/model/host/status from ONE record, never run+analysis', () => {
  // legacy run record: provider only (no pair) + GLM's host/model/503; analysis: the full kimi record
  const props = finished({
    generation: { status: 'failed', provider: 'glm', model: 'glm-4', base_url_host: 'other.example', http_status: 503 },
    analysis: { status: 'failed', phase: 'production', provider: 'kimi', config_source: 'preset', model: 'kimi-k2', base_url_host: 'api.moonshot.cn', http_status: 429, upstream_error_type: 'rate_limited' },
  })
  assert.deepEqual([props.provider, props.config_source, props.model, props.base_url_host, props.http_status, props.upstream_error_type],
    ['kimi', 'preset', 'kimi-k2', 'api.moonshot.cn', 429, 'rate_limited'])
})

test('#332 an unpaired legacy screening identity reads as empty, not half an identity', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'kimi' } })
  assert.equal(id.provider, undefined)
  assert.equal(id.config_source, undefined)
})

test('#332 a half screening_identity is ignored; the paired flat identity is used whole', () => {
  const id = workflow.screeningIdentity({ analysis: { status: 'failed', phase: 'screening', provider: 'glm', config_source: 'customized', screening_identity: { provider: 'kimi' } } })
  assert.deepEqual({ ...id }, { provider: 'glm', config_source: 'customized' })
})
