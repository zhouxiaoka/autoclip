const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const file = path.join(__dirname, '../src/features/settings/providerUrl.ts')
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const urls = {}
vm.runInNewContext(code, { exports: urls, URL }, { filename: file })

test('cleanup collapses spaces, trailing slashes, and missing scheme', () => {
  assert.equal(urls.cleanupBaseUrl('  https://gw.example /v1/  \n'), 'https://gw.example/v1')
  assert.equal(urls.cleanupBaseUrl('HTTP://gw.example/v1'), 'http://gw.example/v1')
  assert.equal(urls.cleanupBaseUrl('gw.example/v1'), 'https://gw.example/v1')
  assert.equal(urls.cleanupBaseUrl('localhost:11434/v1'), 'http://localhost:11434/v1')
  assert.equal(urls.cleanupBaseUrl('not-an-endpoint'), 'not-an-endpoint')
  assert.equal(urls.cleanupBaseUrl(''), '')
})

test('normalize adds or dedupes /v1 per provider and never rejects', () => {
  assert.equal(urls.normalizeProviderBaseUrl('https://gw.example', 'compatible'), 'https://gw.example/v1')
  assert.equal(urls.normalizeProviderBaseUrl('https://gw.example/v1/v1', 'compatible'), 'https://gw.example/v1')
  assert.equal(urls.normalizeProviderBaseUrl('https://openrouter.ai/api/v1', 'compatible'), 'https://openrouter.ai/api/v1')
  assert.equal(urls.normalizeProviderBaseUrl('https://api.deepseek.com', 'deepseek'), 'https://api.deepseek.com/v1')
  assert.equal(urls.normalizeProviderBaseUrl('http://localhost:11434', 'ollama'), 'http://localhost:11434/v1')
  assert.equal(
    urls.normalizeProviderBaseUrl('https://generativelanguage.googleapis.com', 'gemini'),
    'https://generativelanguage.googleapis.com/v1beta/openai',
  )
  assert.equal(
    urls.normalizeProviderBaseUrl('https://llm-x.cn-beijing.maas.aliyuncs.com', 'dashscope'),
    'https://llm-x.cn-beijing.maas.aliyuncs.com',
  )
  assert.equal(urls.normalizeProviderBaseUrl('https://fal.run', 'compatible'), 'https://fal.run')
  assert.equal(urls.normalizeProviderBaseUrl('https://88api.ai/v1', 'api88'), 'https://88api.ai/v1')
  assert.equal(urls.normalizeProviderBaseUrl('https://api.88api.ai/v1', 'api88'), 'https://api.88api.ai/v1')
  assert.equal(urls.normalizeProviderBaseUrl('not-an-endpoint', 'compatible'), 'not-an-endpoint')
})
