const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadClassifier() {
  const file = path.join(__dirname, '../src/utils/llmFailure.ts')
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports })
  return module.exports
}

const { classifyLlmKeyFailure } = loadClassifier()

const LEGACY = '没有可用的 LLM 提供商（当前选择：阿里通义千问 · qwen-plus），缺少 API Key 或本地服务地址。 请到「设置 → 模型」检查提供商、API Key 与模型名，点「测试连接」确认后重试。'

test('classifies a missing key, a failed provider test, and the stable code', () => {
  assert.equal(classifyLlmKeyFailure('anything', 'llm_not_configured'), true)
  assert.equal(classifyLlmKeyFailure(LEGACY), true)
  assert.equal(classifyLlmKeyFailure('未配置LLM提供商，请自备 API Key 并到「设置 → 模型」填写'), true)
  assert.equal(classifyLlmKeyFailure('连接测试失败。请到「设置 → 模型」核对自备的密钥和模型名后再试。'), true)
  assert.equal(classifyLlmKeyFailure('API连接测试失败。请检查API Key是否正确'), true)
})

test('does not treat scoring or subtitle failures as a missing model key', () => {
  assert.equal(classifyLlmKeyFailure('没有片段通过评分筛选。到「设置 → 模型 → 最低评分阈值」调低后重试。'), false)
  assert.equal(classifyLlmKeyFailure('没有字幕可分析：视频不带字幕，且本地 Whisper 还没安装。到「设置 → 转写」安装。'), false)
  assert.equal(classifyLlmKeyFailure(''), false)
  assert.equal(classifyLlmKeyFailure(null, 'whisper_not_installed'), false)
})

test('failure screens deep-link to Settings → Model', () => {
  const detail = fs.readFileSync(path.join(__dirname, '../src/pages/ProjectDetailPage.tsx'), 'utf8')
  const card = fs.readFileSync(path.join(__dirname, '../src/components/ProjectCard.tsx'), 'utf8')
  const empty = fs.readFileSync(path.join(__dirname, '../src/components/LlmKeyFailureEmpty.tsx'), 'utf8')
  const en = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/i18n/locales/en.json'), 'utf8'))
  assert.match(detail, /\/settings\?section=model/)
  assert.match(card, /\/settings\?section=model/)
  assert.match(empty, /打开模型设置/)
  assert.match(en['切片分析需要你自己的 API Key。打开「设置 → 模型」，填上提供商、密钥和模型名，再点「测试连接」。密钥在该提供商的控制台申请，只保存在这台机器上。'], /Settings → Model/)
  assert.match(en['切片分析需要你自己的 API Key。打开「设置 → 模型」，填上提供商、密钥和模型名，再点「测试连接」。密钥在该提供商的控制台申请，只保存在这台机器上。'], /Bring your own API key/)
})
