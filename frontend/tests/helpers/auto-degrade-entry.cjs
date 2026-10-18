// (#419): the AUTO path through the real studioApi.import entry and the real observer, fed the
// workspace snapshots the REAL backend wrote (store -> attempt receipt -> GET /studio/{pid}). Driven by
// backend/tests/test_studio_attempts.py, which produces the snapshots; no receipt is synthesized
// here (the old version built receipts from the live plan and could not prove the freeze).
// stdin: {"run_id": str, "project_id": str, "snapshots": [workspace, ...]}  stdout: [{event, props}, ...]
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const { runInSandbox } = require('../vm-sandbox.cjs')
function load(file, mocks) {
  const exports = {}
  const resolve = name => {
    if (name === './failureCodes') return require('../load-ts.cjs').loadTs(path.resolve(__dirname, '../../src/analytics/failureCodes.ts'))
    if (name in mocks) return mocks[name]
    // Real pure helpers (errorText, successRateContract, …) load from source too.
    const base = path.join(path.dirname(file), name)
    const hit = ['.ts', '/index.ts'].map(ext => base + ext).find(f => fs.existsSync(path.join(__dirname, '../../src', f)))
    if (!name.startsWith('.') || !hit) throw new Error('Unexpected dependency: ' + name)
    return load(hit, {})
  }
  runInSandbox(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, require: resolve, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL, Promise, crypto: globalThis.crypto })
  return exports
}


async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'))
  const wf = load('analytics/workflow.ts', {})
  const events = [], storage = new Map()
  const workflow = new wf.WorkflowTracker({ getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    () => true, (event, props) => { events.push({ event, props }); return true })
  const posthog = { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } }
  const studio = load('analytics/studio.ts', { './flags': { flagAssigned: () => false }, './posthog': posthog, './observer': { workflow }, './workflow': wf })
  const snapshots = input.snapshots.slice()
  const http = {
    defaults: { baseURL: '/api/v1' },
    post: async (url) => { assert.equal(url, '/studio/import'); return { project_id: input.project_id, analysis_run_id: input.run_id } },
    get: async (url) => { assert.equal(url, '/studio/' + input.project_id); return JSON.parse(JSON.stringify(snapshots.shift())) },
  }
  const api = load('features/studio/api.ts', {
    '../../analytics/posthog': posthog, '../../analytics/workflow': wf, '../../analytics/studio': studio,
    '../../analytics/observer': { workflow }, '../../services/api': { default: http },
    './types': {}, './noticeRuntime': { noteWorkspaceCompletion() {} }, './subtitleState': { effectiveSubtitles: () => true },
  }).studioApi
  const body = { get: k => ({ auto_start: 'true', goal: 'content', aspect: 'original' })[k] ?? null, entries: () => [][Symbol.iterator](), has: () => false }
  await api.import(body)
  const watch = workflow.list().find(w => w.kind === 'studio-generation')
  assert.ok(watch, 'auto import must register the generation observer')
  assert.equal(watch.runId, input.run_id, 'bound to the backend run id from the import response, not inferred')
  for (let i = 0; i < input.snapshots.length; i++) await api.get(input.project_id)
  process.stdout.write(JSON.stringify(events))
}
main().catch(error => { console.error(error); process.exit(1) })
