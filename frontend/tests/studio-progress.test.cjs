const { test } = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const progress = loadTs(path.resolve(__dirname, '../src/features/studio/studioProgress.ts'))
const failure = loadTs(path.resolve(__dirname, '../src/features/studio/failureAction.ts'))

const NOW = Date.parse('2026-10-26T12:00:00Z')

test('transcription audio percent maps into the subtitle band and never reads as 100', () => {
  const view = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'production', message: '正在生成字幕', percent: 100, progress_stage: 'SUBTITLE' },
  }, NOW)
  assert.equal(view.label, '字幕处理')
  assert.equal(view.approximate, false)
  assert.ok(view.percent > 10 && view.percent < 30)
  assert.notEqual(view.percent, 100)
})

test('a long approximate stage eases toward the band and stops short of done', () => {
  const start = Date.parse('2026-10-26T00:00:00Z')
  const early = progress.studioRunProgress({
    analysis: {
      status: 'running', phase: 'production', message: '正在制作可发布成片',
      progress_stage: 'ANALYZE', progress_approximate: true, progress_since: start / 1000,
      created_at: new Date(start).toISOString(),
    },
  }, start + 1000)
  const later = progress.studioRunProgress({
    analysis: {
      status: 'running', phase: 'production', message: '正在制作可发布成片',
      progress_stage: 'ANALYZE', progress_approximate: true, progress_since: start / 1000,
      created_at: new Date(start).toISOString(),
    },
  }, start + 10 * 60 * 60 * 1000)
  assert.equal(early.approximate, true)
  assert.ok(later.percent >= early.percent)
  assert.ok(later.percent < 99)
  assert.ok(later.percent <= 95)
  assert.equal(progress.easePercent('ANALYZE', 25, 1e9) < progress.stageBand('ANALYZE').end, true)
  assert.equal(later.elapsedMinutes, 600)
})

test('a reported percent never moves backward and a finished run hides the bar', () => {
  const view = progress.studioRunProgress({
    analysis: {
      status: 'running', phase: 'production', message: '正在制作可发布成片',
      progress_percent: 70, progress_stage: 'HIGHLIGHT', progress_approximate: false,
    },
  }, NOW)
  assert.equal(view.percent, 70)
  assert.equal(view.approximate, false)
  assert.equal(progress.studioRunProgress({
    analysis: { status: 'completed', phase: 'production', progress_percent: 100, progress_stage: 'DONE' },
  }, NOW), null)
})

test('the 20-minute model cap applies only to analysis stages', () => {
  const download = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'screening', percent: 40, message: '正在下载' },
  }, NOW)
  assert.equal(download.modelBudget, false)
  const whisper = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'production', message: '正在生成字幕', percent: 10, progress_stage: 'SUBTITLE' },
  }, NOW)
  assert.equal(whisper.modelBudget, false)
  const rendering = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'rendering', message: '正在生成可发布成片' },
    jobs: [{ status: 'running', percent: 10 }],
  }, NOW)
  assert.equal(rendering.modelBudget, false)
  const analyze = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'production', message: '正在制作可发布成片', progress_stage: 'ANALYZE', progress_approximate: true },
  }, NOW)
  assert.equal(analyze.modelBudget, true)
  const highlight = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'production', progress_stage: 'HIGHLIGHT' },
  }, NOW)
  assert.equal(highlight.modelBudget, true)
})

test('download percent is the screening bar; rendering keeps the export band under 100', () => {
  const download = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'screening', percent: 40, message: '正在下载' },
  }, NOW)
  assert.equal(download.label, '下载中')
  assert.equal(download.percent, 40)
  assert.equal(download.approximate, false)
  const rendering = progress.studioRunProgress({
    analysis: { status: 'running', phase: 'rendering', message: '正在生成可发布成片', progress_percent: 70, progress_since: NOW / 1000 },
    jobs: [{ status: 'running', percent: 100 }],
  }, NOW + 60_000)
  assert.equal(rendering.label, '视频导出')
  assert.ok(rendering.percent >= 70 && rendering.percent < 100)
  assert.equal(rendering.approximate, false)
})

test('failure copy names the step and adds billing guidance only after a billable call', () => {
  assert.equal(failure.failureStep('subtitle', 'production', 'timeout'), '转写')
  assert.equal(failure.failureStep(undefined, 'screening', 'source_unreadable'), '下载')
  assert.equal(failure.failureStep(undefined, 'screening', 'file_locked'), '下载')
  assert.equal(failure.failureStep(undefined, 'screening', 'whisper_not_installed'), '转写')
  assert.equal(failure.failureStep(undefined, 'screening', 'llm_not_configured'), '分析')
  assert.equal(failure.failureStep('analyze', 'production', 'invalid_response'), '分析')
  assert.equal(failure.failureStep(undefined, 'rendering', 'timeout'), '制作')
  const billed = failure.presentedFailure({ error: '错误', error_code: 'invalid_response', failure_stage: 'analyze', billable_calls_before_failure: 1 })
  assert.equal(billed.step, '分析')
  assert.notEqual(billed.reason, '错误')
  assert.equal(billed.reason, '模型返回的内容无法使用，请稍后重试。')
  assert.match(billed.billing, /可能已经由服务商计费/)
  assert.equal(billed.billing.includes('元'), false)
  const quiet = failure.presentedFailure({ error: '错误', error_code: 'invalid_response', failure_stage: 'analyze', billable_calls_before_failure: 0 })
  assert.equal(quiet.billing, null)
})
