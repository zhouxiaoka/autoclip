const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadDraft() {
  const file = path.join(__dirname, '../src/analytics/feedbackDraft.ts')
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports, URLSearchParams })
  return module.exports
}

const draftInput = {
  feedbackId: '11111111-1111-4111-8111-111111111111',
  category: 'bug',
  text: '进度停住了 sk-test-abc1234567890',
  contact: 'person@example.com',
  source: 'failure',
  stage: 'ANALYZE',
  errorMessage: 'bearer: secret-token',
  version: '1.3.1',
  os: 'windows',
  arch: 'x64',
  llmProvider: 'ollama',
  llmModel: 'qwen2.5',
}

test('capture keeps the email and github links do not', () => {
  const { buildFeedbackDraft, captureProperties, githubFallbackUrl } = loadDraft()
  const draft = buildFeedbackDraft(draftInput)
  const props = captureProperties(draft)
  assert.equal(props.contact, 'person@example.com')
  assert.equal(props.llm_base_url, undefined)
  assert.ok(!props.text.includes('sk-test-abc1234567890'))
  const url = githubFallbackUrl(draft)
  assert.ok(url.startsWith('https://github.com/zhouxiaoka/autoclip/issues/new?'))
  assert.ok(!url.includes('person@example.com'))
  assert.ok(!url.includes('sk-test-abc1234567890'))
  assert.ok(url.includes('bug_report.yml'))
  assert.ok(decodeURIComponent(url).includes('11111111-1111-4111-8111-111111111111'))
})

test('ideas and other notes open discussions', () => {
  const { buildFeedbackDraft, githubFallbackUrl } = loadDraft()
  const idea = githubFallbackUrl(buildFeedbackDraft({ ...draftInput, category: 'idea', text: '希望记住导出比例' }))
  const other = githubFallbackUrl(buildFeedbackDraft({ ...draftInput, category: 'other', text: '安装包在哪里下载' }))
  assert.ok(idea.includes('/discussions/new?'))
  assert.ok(idea.includes('category=ideas'))
  assert.ok(other.includes('category=q-a'))
  assert.ok(!idea.includes('person@example.com'))
})

test('stable failure code and transcription role survive capture and fallback separately from analysis', () => {
  const { buildFeedbackDraft, captureProperties, githubFallbackUrl } = loadDraft()
  const draft = buildFeedbackDraft({ ...draftInput, errorCode: 'subtitle_setup', transcriptionProvider: 'whisper_local', transcriptionModel: 'tiny' })
  const props = captureProperties(draft)
  assert.equal(props.error_code, 'subtitle_setup')
  assert.equal(props.transcription_provider, 'whisper_local')
  assert.equal(props.transcription_model, 'tiny')
  assert.equal(props.llm_model, 'qwen2.5')
  const body = new URL(githubFallbackUrl(draft)).searchParams.get('what')
  assert.ok(body.includes('错误码：subtitle_setup'))
  assert.ok(body.includes('转写模型：whisper_local / tiny'))
  assert.ok(!body.includes('person@example.com'))
})

test('arbitrary failure codes and transcription provider payloads are not published', () => {
  const { buildFeedbackDraft, captureProperties, githubFallbackUrl } = loadDraft()
  const draft = buildFeedbackDraft({ ...draftInput, errorCode: 'private-path', transcriptionProvider: 'secret-url', transcriptionModel: 'sk-test-abc1234567890' })
  const props = captureProperties(draft)
  assert.equal(props.error_code, undefined)
  assert.equal(props.transcription_provider, undefined)
  assert.ok(!githubFallbackUrl(draft).includes('secret-url'))
  assert.ok(!JSON.stringify(props).includes('sk-test-abc1234567890'))
})
