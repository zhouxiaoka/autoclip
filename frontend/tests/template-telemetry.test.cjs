const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadWorkflow() {
  const source = fs.readFileSync(path.join(__dirname, '../src/analytics/workflow.ts'), 'utf8')
  const exports = {}
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, { exports, Date, Math, JSON, Number, Array, Object, Map, Set, String, URL })
  return exports
}

const workflow = loadWorkflow()

test('template render facts stay enumerable and drop captions and paths', () => {
  const props = workflow.safeStudioProperties({
    template: 'classic', requested_template: 'editorial', encoder: 'h264_nvenc', downgraded: false, downgrade_reason: 'rank',
    os: 'darwin', cpu_count: 8, duration_ms: 90000, failure_reason: 'none', outcome: 'skipped',
    strategy_id: 'douyin', flow_id: 't-abc123def456', title: '秘密标题', caption: '原话', path: '/Users/a/v.mp4',
  })
  assert.equal(props.template, 'classic')
  assert.equal(props.requested_template, 'editorial')
  assert.equal(props.encoder, 'h264_nvenc')
  assert.equal(props.downgraded, false)
  assert.equal(props.downgrade_reason, 'rank')
  assert.equal(props.outcome, 'skipped')
  assert.equal(props.os, 'darwin')
  assert.equal(props.cpu_count, 8)
  assert.equal(props.duration_ms, 90000)
  const blob = JSON.stringify(props)
  assert.equal(blob.includes('秘密'), false)
  assert.equal(blob.includes('原话'), false)
  assert.equal(blob.includes('/Users'), false)
})

test('a rank skip is classic and is not a downgrade', () => {
  const summary = workflow.generationSummary({
    output_variants: [
      { draft_id: 'a', render_job_id: 'j1', strategy_id: 'douyin', status: 'completed' },
      { draft_id: 'b', render_job_id: 'j2', strategy_id: 'douyin', status: 'completed' },
    ],
    jobs: [
      { job_id: 'j1', status: 'completed', result: { template_render: { template: 'classic', requested_template: 'editorial', downgraded: false, downgrade_reason: 'rank', outcome: 'skipped' } } },
      { job_id: 'j2', status: 'completed', result: { template_render: { template: 'classic', requested_template: 'editorial', downgraded: true, downgrade_reason: 'over_budget', outcome: 'downgraded' } } },
    ],
    drafts: [],
  })
  assert.equal(summary.html_downgrade_count, 1)
  assert.equal(summary.classic_count, 2)
  assert.equal(summary.editorial_count, 0)
})

test('override event helper keeps enums and drops free text', () => {
  const studio = fs.readFileSync(path.join(__dirname, '../src/analytics/studio.ts'), 'utf8')
  assert.match(studio, /captureBusinessEvent\('studio_template_overridden'/)
  const events = []
  const source = fs.readFileSync(path.join(__dirname, '../src/analytics/studio.ts'), 'utf8')
  const exports = {}
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, {
    exports, console,
    require: (id) => {
      if (id === './posthog') return { captureBusinessEvent: (name, props) => { events.push({ name, props }); return false } }
      if (id === './observer') return { workflow: { context: () => ({ flow_id: 't-abc123def456' }), active: () => false } }
      if (id === './workflow') return workflow
      throw new Error(id)
    },
  }, { filename: 'studio.ts' })
  exports.trackTemplateOverride({ from_template: 'editorial', to_template: 'street', flow_id: 't-abc123def456', title: 'nope' })
  assert.equal(events.length, 1)
  assert.equal(events[0].name, 'studio_template_overridden')
  assert.equal(events[0].props.from_template, 'editorial')
  assert.equal(events[0].props.to_template, 'street')
  assert.equal(events[0].props.stage, 'pre_import')
  assert.equal(JSON.stringify(events[0].props).includes('nope'), false)
})
