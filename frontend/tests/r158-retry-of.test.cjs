const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

test('1.5.8 one-click retry: new attempt_id, linked to the failed one via retry_of', () => {
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  const events = []
  const tracker = new workflow.WorkflowTracker({ getItem: () => null, setItem() {}, removeItem() {} },
    () => true, (event, props) => { events.push({ event, props }); return true })
  const failed = { material_origin: 'user', generation: { status: 'failed', error_code: 'service_restarted' }, analysis: { status: 'failed', phase: 'production', error_code: 'service_restarted' } }
  tracker.watch('studio-generation', 'p1')
  tracker.observeStudio(tracker.list()[0], failed)
  tracker.watch('studio-generation', 'p1', undefined, undefined, {}, true)
  tracker.observeStudio(tracker.list().find(w => w.kind === 'studio-generation'), { ...failed, generation: { status: 'completed' }, analysis: { status: 'completed' } })
  const finished = events.filter(e => e.event === 'studio_generation_finished')
  assert.equal(finished.length, 2)
  const [first, second] = finished.map(e => e.props)
  assert.ok(first.attempt_id && second.attempt_id && first.attempt_id !== second.attempt_id)
  assert.equal(first.retry_of, undefined)
  assert.equal(second.retry_of, first.attempt_id)
})

test('1.5.8 failed-state Retry button reuses the rerun API, which restarts the watch (new attempt + retry_of)', () => {
  const fs = require('node:fs')
  const ui = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/StudioResults.tsx'), 'utf8')
  const failed = ui.slice(ui.indexOf("workspace.analysis?.status==='failed'"))
  assert.match(failed.slice(0, 900), /!workspace\.output_variants\?\.length && <Btn[^>]*onClick=\{\(\)=>act\('retry-analysis', async\(\)=>\{await studioApi\.analyze\(project\.id, !!automatic\)\}\)\}>\{t\("重试"\)\}/)
  const api = fs.readFileSync(path.resolve(__dirname, '../src/features/studio/api.ts'), 'utf8')
  assert.match(api, /analyze: \(pid: string, automatic = false\)[\s\S]{0,300}workflow\.watch\('studio-screen', pid, undefined, undefined, props, true/)
  // retry_of survives the property allow-list and is never accepted when not a telemetry id
  const workflow = loadTs(path.resolve(__dirname, '../src/analytics/workflow.ts'))
  assert.equal(workflow.safeStudioProperties({ retry_of: 't-0123456789abc' }).retry_of, 't-0123456789abc')
  assert.equal(workflow.safeStudioProperties({ retry_of: 'https://x/sk-abc' }).retry_of, undefined)
})
