const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { runInSandbox } = require('./vm-sandbox.cjs')
const ts = require('typescript')

function loadWorkflow() {
  return require('./load-ts.cjs').loadTs(path.join(__dirname, '../src/analytics/workflow.ts'))
}

const workflow = loadWorkflow()

test('template render facts stay enumerable and drop captions and paths', () => {
  const props = workflow.safeStudioProperties({
    template: 'classic', requested_template: 'editorial', encoder: 'h264_nvenc', downgraded: false, downgrade_reason: 'rank',
    os: 'macos', cpu_count: 8, duration_ms: 90000, failure_reason: 'none', outcome: 'skipped',
    strategy_id: 'douyin', flow_id: 't-abc123def456', title: '秘密标题', caption: '原话', path: '/Users/a/v.mp4',
  })
  assert.equal(props.template, 'classic')
  assert.equal(props.requested_template, 'editorial')
  assert.equal(props.encoder, 'h264_nvenc')
  assert.equal(props.downgraded, false)
  assert.equal(props.downgrade_reason, 'rank')
  assert.equal(props.outcome, 'skipped')
  assert.equal(props.os, 'macos')
  assert.equal(workflow.safeStudioProperties({ os: 'darwin', outcome: 'completed' }).os, 'macos')
  assert.equal(workflow.safeStudioProperties({ os: 'win32', outcome: 'failed' }).outcome, 'error')
  assert.equal(props.cpu_count, 8)
  assert.equal(props.duration_ms, 90000)
  const blob = JSON.stringify(props)
  assert.equal(blob.includes('秘密'), false)
  assert.equal(blob.includes('原话'), false)
  assert.equal(blob.includes('/Users'), false)
})

// the rank-skip summary rule is asserted on backend attempts.generation_summary
// (backend/tests/test_studio_attempts.py); the frontend no longer derives summaries.

test('override event helper keeps enums and drops free text', () => {
  const studio = fs.readFileSync(path.join(__dirname, '../src/analytics/studio.ts'), 'utf8')
  assert.match(studio, /captureBusinessEvent\('studio_template_overridden'/)
  const events = []
  const source = fs.readFileSync(path.join(__dirname, '../src/analytics/studio.ts'), 'utf8')
  const exports = {}
  runInSandbox(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, {
    exports, console,
    require: (id) => {
      if (id === './flags') return { flagAssigned: () => false }
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
  // Dynamic hot-installed template slugs pass through while free text / paths remain blocked.
  const dyn = workflow.safeStudioProperties({
    template: 'interview_card', requested_template: 'interview_card', from_template: 'editorial', to_template: 'interview_card',
  })
  assert.equal(dyn.template, 'interview_card')
  assert.equal(dyn.to_template, 'interview_card')
  const bad = workflow.safeStudioProperties({ template: '/Users/secret/path', to_template: '包含中文的标题' })
  assert.equal(bad.template, undefined)
  assert.equal(bad.to_template, undefined)

  // Clone lifecycle helpers emit enums/counts only and strip URLs, paths, and free-text instructions.
  events.length = 0
  exports.trackTemplateCloneStarted({ source_kind: 'link', url: 'https://example.com/secret/clip.mp4', instruction: '换成霓虹紫' })
  exports.trackTemplateCloneCompleted({ outcome: 'success', duration_ms: 4200, path: '/Users/a/ref.mp4' })
  exports.trackTemplateCloneRefined({ trigger: 'manual', instruction: '字幕大一点' })
  exports.trackTemplateCloneSaved({ template: 'my_clone_style', title: '私密名称' })
  assert.deepEqual(events.map(e => e.name), [
    'studio_template_clone_started',
    'studio_template_clone_completed',
    'studio_template_clone_refined',
    'studio_template_clone_saved',
  ])
  assert.equal(events[0].props.source_kind, 'link')
  assert.equal(events[1].props.outcome, 'success')
  assert.equal(events[1].props.duration_ms, 4200)
  assert.equal(events[2].props.trigger, 'manual')
  assert.equal(events[3].props.template, 'my_clone_style')
  const cloneBlob = JSON.stringify(events)
  assert.equal(cloneBlob.includes('example.com'), false)
  assert.equal(cloneBlob.includes('霓虹紫'), false)
  assert.equal(cloneBlob.includes('/Users'), false)
  assert.equal(cloneBlob.includes('私密名称'), false)
})
