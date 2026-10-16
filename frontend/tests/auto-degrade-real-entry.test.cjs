// R14 #32: the AUTO path registers its observer through the real studioApi.import entry
// (no injected runId) and sees backend-shaped snapshots from 'screening' onwards.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs'), path = require('node:path'), ts = require('typescript')
const { runInSandbox } = require('./vm-sandbox.cjs')
function load(file, mocks) {
  const exports = {}
  const resolve = name => {
    if (name in mocks) return mocks[name]
    // Real pure helpers (errorText, successRateContract, …) load from source too.
    const base = path.join(path.dirname(file), name)
    const hit = ['.ts', '/index.ts'].map(ext => base + ext).find(f => fs.existsSync(path.join(__dirname, '../src', f)))
    if (!name.startsWith('.') || !hit) throw new Error('Unexpected dependency: ' + name)
    return load(hit, {})
  }
  runInSandbox(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src', file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, require: resolve, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL, Promise, crypto: globalThis.crypto })
  return exports
}

for (const reason of ['frame_extract_subtitle_fallback', 'source_too_long_subtitle_route']) {
  test(`real import entry → screening → production → completed carries ${reason} once`, async () => {
    const wf = load('analytics/workflow.ts', {})
    const events = [], storage = new Map()
    const workflow = new wf.WorkflowTracker({ getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
      () => true, (event, props) => { events.push({ event, props }); return true })
    const posthog = { captureBusinessEvent: (event, props) => { events.push({ event, props }); return true } }
    const studio = load('analytics/studio.ts', { './flags': { flagAssigned: () => false }, './posthog': posthog, './observer': { workflow }, './workflow': wf })
    const snapshots = []
    const http = {
      defaults: { baseURL: '/api/v1' },
      post: async (url) => { assert.equal(url, '/studio/import'); return { project_id: 'p1', analysis_run_id: 'run-1' } },
      get: async (url) => { assert.equal(url, '/studio/p1'); return JSON.parse(JSON.stringify(snapshots.shift())) },
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
    assert.equal(watch.runId, undefined, 'no injected runId')
    const plan = { id: 'plan-1', mode: 'local', recommended_analysis: 'subtitle', degrade_reason: reason, preferences: {} }
    // Backend sequence written by inspect_project / _inspect / settle_generation (jobs.py).
    snapshots.push(
      { analysis: { status: 'running', phase: 'screening', run_id: 'run-1' }, generation: { auto_start: true, status: 'screening' }, output_variants: [], jobs: [] },
      { plan, analysis: { status: 'running', phase: 'production', run_id: 'run-1' }, generation: { auto_start: true, status: 'production', route: 'subtitle' }, output_variants: [], jobs: [] },
      { plan, analysis: { status: 'completed', phase: 'rendering', run_id: 'run-1', outcome: 'completed' }, generation: { auto_start: true, status: 'completed', route: 'subtitle' }, output_variants: [{ id: 'v', status: 'completed' }], jobs: [] },
      { plan, analysis: { status: 'completed', phase: 'rendering', run_id: 'run-1', outcome: 'completed' }, generation: { auto_start: true, status: 'completed', route: 'subtitle' }, output_variants: [{ id: 'v', status: 'completed' }], jobs: [] },
    )
    for (let i = 0; i < 4; i++) await api.get('p1')
    const finished = events.filter(e => e.event === 'studio_generation_finished')
    assert.equal(finished.length, 1, 'duplicate observation counted once')
    assert.equal(finished[0].props.outcome, 'success')
    assert.equal(finished[0].props.degrade_reason, reason)
    const screen = events.filter(e => e.event === 'studio_screen_finished')
    assert.equal(screen.length, 1)
    assert.equal(screen[0].props.degrade_reason, reason)
  })
}
