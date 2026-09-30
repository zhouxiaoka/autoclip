// Historical audit reproducer for the 2026-09-29 source, not a current regression test.
// Fix verification now lives in frontend/tests/analytics.test.cjs.
if (!process.env.AUTOCLIP_RUN_HISTORICAL_REPRO) {
  console.log("Historical reproducer skipped. Run: cd frontend && npm test"); process.exit(0)
}
// No network calls. Run from any directory after frontend dependencies are installed.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../..')
const ts = require(path.join(root, 'frontend/node_modules/typescript'))

// Compile the actual source in memory. No new runner dependency or network calls.
function load(name, mocks = {}, globals = {}) {
  const file = path.join(root, 'frontend/src/analytics', `${name}.ts`)
  const source = fs.readFileSync(file, 'utf8').replaceAll('import.meta.env', '__env')
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  } }).outputText
  const module = { exports: {} }
  vm.runInNewContext(js, { exports: module.exports, module, Blob, Date, Math, console,
    __env: { DEV: false, VITE_PUBLIC_POSTHOG_KEY: 'test-only-not-a-real-key' },
    require: (id) => {
      if (id in mocks) return mocks[id]
      throw new Error(`Unexpected dependency: ${id}`)
    }, ...globals }, { filename: file })
  return module.exports
}
const core = load('workflow')
function memory() {
  const data = new Map()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) }
}
const NOW = Date.parse('2026-09-21T01:00:00Z')
function setup(storage = memory(), clock = () => NOW) {
  const events = []
  let enabled = true
  let accepted = true
  const capture = (event, props) => { if (!accepted) return false; events.push({ event, props }); return true }
  const tracker = new core.WorkflowTracker(storage, () => enabled, capture, clock)
  return { tracker, events, storage, capture, enable: v => enabled = v, accept: v => accepted = v }
}
const task = overrides => ({ id: 'task-1', task_type: 'video_processing', status: 'completed',
  created_at: '2026-09-21T01:00:00', started_at: '2026-09-21T01:00:01Z',
  completed_at: '2026-09-21T01:00:06Z', ...overrides })


const sdk={init(){},capture(){return {}},opt_out_capturing(){},opt_in_capturing(){}};
const readableButFull={getItem(){return null},setItem(){throw Error('quota') }};
const ph=load('posthog',{'posthog-js':sdk,'./workflow':core},{localStorage:readableButFull,window:{}});
ph.initAnalytics();ph.setAnalyticsEnabled(false);
assert.equal(ph.isAnalyticsEnabled(),true);
console.log('REPRO 1: readable storage + failed write => app consent gate remains enabled after opt-out (SDK/network behavior not asserted)');
const s=setup();s.tracker.watch('studio-screen','project');
s.tracker.observeStudio(s.tracker.list()[0],{plan:{id:'plan'},analysis:{status:'failed',phase:'production',error_code:'llm_not_configured'}});
assert.equal(s.events[0].event,'studio_screen_finished');
console.log('REPRO 2: pending screening watch consumes production failure as screening failure');
const p=setup();p.tracker.watch('studio-production','plan-old','project');
p.tracker.observeStudio(p.tracker.list()[0],{plan:{id:'plan-new'},analysis:{status:'awaiting_confirmation'}});
assert.equal(p.events.length,0);assert.equal(p.tracker.list()[0].settled,undefined);
console.log('REPRO 3: overwritten plan prevents old production watch from recovering its terminal result');
