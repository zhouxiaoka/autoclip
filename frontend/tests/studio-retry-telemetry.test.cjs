const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), ts = require('typescript')
function load(file, mocks) {
  const exports = {}
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, require: name => mocks[name], Date, Math, JSON, Number, Array, Object, Map, Set, String, URL })
  return exports
}
test('automatic retry enrolls a fresh terminal watch on the same flow and deduplicates completion', async () => {
  const { WorkflowTracker, safeStudioProperties } = load('analytics/workflow.ts', {})
  const events = [], storage = new Map(), requests = []
  const workflow = new WorkflowTracker({ getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }, () => true, (event, props) => { events.push({ event, props }); return true })
  workflow.rememberProject('p', { material_origin: 'user' })
  workflow.watch('studio-generation', 'p')
  workflow.observeStudio(workflow.list()[0], { generation: { auto_start: true, status: 'failed', error_code: 'whisper_not_installed' }, analysis: { status: 'failed' } })
  const api = load('features/studio/api.ts', {
    '../../analytics/posthog': {}, '../../analytics/workflow': { safeStudioProperties },
    '../../analytics/observer': { workflow }, '../../services/api': { default: { post: async url => { requests.push(url); return { analysis_run_id: 'new-run' } } } },
    '../../analytics/studio': { observeStudioOperation: async (_name, action, accepted) => { const result = await action(); accepted(result, {}); return result } },
  }).studioApi
  await api.analyze('p', true)
  assert.deepEqual(requests, ['/studio/p/analyze'])
  const watch = workflow.list().find(item => item.kind === 'studio-generation' && !item.settled)
  assert.ok(watch, 'retry needs a fresh automatic terminal watch')
  const state = { generation: { auto_start: true, status: 'completed' }, analysis: { status: 'completed', run_id: 'new-run' } }
  workflow.observeStudio(watch, state); workflow.observeStudio(watch, state)
  const finished = events.filter(item => item.event === 'studio_generation_finished')
  assert.deepEqual(finished.map(item => item.props.outcome), ['failed', 'completed'])
  assert.equal(finished[0].props.flow_id, finished[1].props.flow_id)
  assert.notEqual(finished[0].props.attempt_id, finished[1].props.attempt_id)
})
