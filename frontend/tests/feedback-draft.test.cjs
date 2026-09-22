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
