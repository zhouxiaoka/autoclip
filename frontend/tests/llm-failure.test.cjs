const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

function loadClassifier() {
  return loadTs(path.join(__dirname, '../src/utils/llmFailure.ts'))
}

const { classifyLlmKeyFailure } = loadClassifier()

const LEGACY = '没有可用的 LLM 提供商（当前选择：阿里通义千问 · qwen-plus），缺少 API Key 或本地服务地址。 请到「设置 → 服务商与模型」检查提供商、API Key 与模型名，点「测试连接」确认后重试。'

test('invalid credentials use distinct localized copy even with a stale missing-key message', () => {
  const { llmFailureText } = loadClassifier()
  assert.equal(classifyLlmKeyFailure(LEGACY, 'llm_auth_invalid'), false)
  const key = llmFailureText(LEGACY, 'llm_auth_invalid')
  assert.equal(key, 'API Key 无效或已过期，请到设置里更新后再试')
  for (const locale of ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']) {
    const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, `../src/i18n/locales/${locale}.json`), 'utf8'))
    assert.ok(catalog[key], locale)
    if (locale !== 'zh') assert.notEqual(catalog[key], key)
  }
  assert.equal(llmFailureText(LEGACY, 'llm_not_configured'), LEGACY)
})

test('503 coarse provider_error shows the upstream_unavailable sentence', () => {
  const { llmFailureText } = loadClassifier()
  const { USER_MESSAGES } = loadTs(path.join(__dirname, '../src/analytics/failureCodes.ts'))
  const generic = USER_MESSAGES.provider_error
  assert.match(generic, /无法识别/)
  assert.equal(llmFailureText(generic, 'provider_error', 'upstream_unavailable'), USER_MESSAGES.upstream_unavailable)
  assert.equal(llmFailureText('', 'provider_error', 'upstream_unavailable'), USER_MESSAGES.upstream_unavailable)
  assert.equal(llmFailureText('模型服务暂时不可用，请稍后重试。', 'provider_error', 'upstream_unavailable'), '模型服务暂时不可用，请稍后重试。')
  assert.equal(llmFailureText(generic, 'provider_error', 'unknown'), generic)
  assert.equal(llmFailureText('Error code: 401 sk-secret', 'unexpected'), 'Error code: 401 sk-secret')
})

test('classifies a missing key, a failed provider test, and the stable code', () => {
  assert.equal(classifyLlmKeyFailure('anything', 'llm_not_configured'), true)
  assert.equal(classifyLlmKeyFailure(LEGACY), true)
  assert.equal(classifyLlmKeyFailure('未配置LLM提供商，请自备 API Key 并到「设置 → 服务商与模型」填写'), true)
  assert.equal(classifyLlmKeyFailure('连接测试失败。请到「设置 → 服务商与模型」核对自备的密钥和模型名后再试。'), true)
  assert.equal(classifyLlmKeyFailure('API连接测试失败。请检查API Key是否正确'), true)
})

test('does not treat scoring, subtitle, or empty-timeline failures as a missing model key', () => {
  assert.equal(classifyLlmKeyFailure('没有片段通过评分筛选。到「设置 → 服务商与模型 → 最低评分阈值」调低后重试。'), false)
  assert.equal(classifyLlmKeyFailure('没有字幕可分析：视频不带字幕，且本地 Whisper 还没安装。到「设置 → 默认模型 → 语音转字幕」安装。'), false)
  const timeline = '时间线提取为空：4 个话题在对齐并按时长筛选后没有留下可用片段。 短视频里的片段常被最短时长滤掉（短片约 20 秒起），或模型给出的时间戳对不上字幕。换一条更长、口播更完整的素材后再试。'
  assert.equal(classifyLlmKeyFailure(timeline), false)
  assert.equal(classifyLlmKeyFailure(timeline, 'timeline_empty'), false)
  assert.equal(classifyLlmKeyFailure('处理失败：' + timeline), false)
  assert.equal(classifyLlmKeyFailure(''), false)
  assert.equal(classifyLlmKeyFailure(null, 'whisper_not_installed'), false)
  assert.equal(classifyLlmKeyFailure(null, 'timeline_empty'), false)
})

test('failure screens deep-link to Settings → Model', () => {
  const detail = fs.readFileSync(path.join(__dirname, '../src/pages/ProjectDetailPage.tsx'), 'utf8')
  const card = fs.readFileSync(path.join(__dirname, '../src/components/ProjectCard.tsx'), 'utf8')
  const empty = fs.readFileSync(path.join(__dirname, '../src/components/LlmKeyFailureEmpty.tsx'), 'utf8')
  const en = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/i18n/locales/en.json'), 'utf8'))
  assert.match(detail, /\/settings\?section=model/)
  assert.match(card, /\/settings\?section=model/)
  assert.match(empty, /打开模型设置/)
  assert.match(en['切片分析需要你自己的 API Key。打开「设置 → 服务商与模型」，填上提供商、密钥和模型名，再点「测试连接」。密钥在该提供商的控制台申请，只保存在这台机器上。'], /Settings → Providers and models/)
  assert.match(en['切片分析需要你自己的 API Key。打开「设置 → 服务商与模型」，填上提供商、密钥和模型名，再点「测试连接」。密钥在该提供商的控制台申请，只保存在这台机器上。'], /Bring your own API key/)
})
