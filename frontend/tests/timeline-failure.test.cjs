const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function load(relativePath) {
  const file = path.join(__dirname, relativePath)
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports })
  return module.exports
}

const { classifyTimelineEmpty } = load('../src/utils/timelineFailure.ts')
const { classifyLlmKeyFailure } = load('../src/utils/llmFailure.ts')
const { classifySubtitleFailure } = load('../src/utils/subtitleFailure.ts')

// 与 backend empty_timeline_failure().user_message() 一致；CLI 会把它写进 last_error。
const LAST_ERROR = '时间线提取为空：4 个话题在对齐并按时长筛选后没有留下可用片段。 短视频里的片段常被最短时长滤掉（短片约 20 秒起），或模型给出的时间戳对不上字幕。换一条更长、口播更完整的素材后再试。'
const PROGRESS = `处理失败：${LAST_ERROR}`

test('classifies the stable code and a last_error that has no code', () => {
  assert.equal(classifyTimelineEmpty('anything', 'timeline_empty'), true)
  assert.equal(classifyTimelineEmpty(LAST_ERROR), true)
  assert.equal(classifyTimelineEmpty(PROGRESS), true)
  assert.equal(classifyTimelineEmpty('时间线为空：没有可用片段。'), true)
})

test('does not treat model, scoring, or subtitle failures as an empty timeline', () => {
  assert.equal(classifyTimelineEmpty('没有可用的 LLM 提供商，缺少 API Key。请到「设置 → 模型」点「测试连接」。'), false)
  assert.equal(classifyTimelineEmpty('没有片段通过评分筛选。到「设置 → 模型 → 最低评分阈值」调低后重试。'), false)
  assert.equal(classifyTimelineEmpty('没有字幕可分析：视频不带字幕。到「设置 → 转写」安装。'), false)
  assert.equal(classifyTimelineEmpty(''), false)
  assert.equal(classifyTimelineEmpty(null, 'llm_not_configured'), false)
  assert.equal(classifyTimelineEmpty(null, 'whisper_not_installed'), false)
})

test('an empty timeline last_error does not open model or transcription settings', () => {
  assert.equal(classifyLlmKeyFailure(LAST_ERROR), false)
  assert.equal(classifyLlmKeyFailure(LAST_ERROR, 'timeline_empty'), false)
  assert.equal(classifyLlmKeyFailure(PROGRESS), false)
  assert.equal(classifySubtitleFailure(LAST_ERROR), null)
  assert.equal(classifySubtitleFailure(LAST_ERROR, 'timeline_empty'), null)
  assert.equal(classifySubtitleFailure(PROGRESS), null)
  assert.equal(LAST_ERROR.includes('设置 → 模型'), false)
  assert.equal(LAST_ERROR.includes('API Key'), false)
  assert.equal(LAST_ERROR.includes('测试连接'), false)
})

test('failure screens do not route an empty timeline to Settings → Model', () => {
  const detail = fs.readFileSync(path.join(__dirname, '../src/pages/ProjectDetailPage.tsx'), 'utf8')
  const card = fs.readFileSync(path.join(__dirname, '../src/components/ProjectCard.tsx'), 'utf8')
  assert.match(detail, /classifyTimelineEmpty/)
  assert.match(detail, /!timelineEmpty && classifyLlmKeyFailure/)
  assert.match(card, /classifyTimelineEmpty/)
  assert.match(card, /!timelineEmpty && classifyLlmKeyFailure/)
})
