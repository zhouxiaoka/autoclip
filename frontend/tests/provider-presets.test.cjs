const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs, PRESETS } = require('./load-ts.cjs')

const catalog = JSON.parse(fs.readFileSync(PRESETS, 'utf8'))
const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
const defaults = loadTs('modelDefaults.ts', {})
const HOSTS = [
  'api.deepseek.com', 'api.moonshot.cn', 'open.bigmodel.cn', 'api.x.ai',
  'infistar.cc', 'api.88api.ai', 'localhost:11434', 'localhost:1234',
]

test('the shared JSON lists 40 providers in the four product groups', () => {
  const groups = Object.values(catalog.providers).reduce((acc, row) => {
    acc[row.group] = (acc[row.group] || 0) + 1
    return acc
  }, {})
  assert.equal(Object.keys(catalog.providers).length, 40)
  assert.deepEqual(groups, { recommended: 3, popular: 10, local: 4, more: 23 })
})

test('current settings dropdown still reads addresses and defaults from the JSON', () => {
  assert.equal(providers.PROVIDERS.api88.cloud.baseUrl, catalog.providers.api88.base_url)
  assert.equal(providers.PROVIDERS.deepseek.cloud.defaultModel, catalog.providers.deepseek.default_model)
  assert.equal(providers.PROVIDERS.ollama.local.baseUrl, catalog.providers.ollama.base_url)
  assert.equal(providers.PROVIDERS.dashscope.cloud, undefined)
  const models = [
    { id: 'qwen3.8-flash', capability: 'multimodal', analysis: true, image: false },
    { id: 'qwen-plus', capability: 'text', analysis: true, image: false },
    { id: 'wanx2.1-t2i-turbo', analysis: false, image: true },
  ]
  assert.equal(defaults.defaultModel('dashscope', models), catalog.providers.dashscope.candidates.analysis[0])
  assert.equal(defaults.defaultModel('dashscope', models, true), 'wanx2.1-t2i-turbo')
})

test('Infistar accepts both gateway domains while keeping the Chinese default', () => {
  const preset = loadTs('providerPresets.ts').getProvider('infistar')
  assert.equal(preset.base_url, 'https://infistar.cc/v1')
  for (const host of ['infistar.ai', 'www.infistar.ai', 'infistar.cc', 'www.infistar.cc']) {
    assert.ok(preset.accepted_hosts.includes(host))
  }
})

test('providers.ts and modelDefaults.ts no longer hard-code product hosts or preferred lists', () => {
  const files = ['providers.ts', 'modelDefaults.ts'].map(name =>
    fs.readFileSync(path.join(__dirname, '../src/features/settings', name), 'utf8'))
  for (const host of HOSTS) {
    assert.match(fs.readFileSync(PRESETS, 'utf8'), new RegExp(host.replace(/\./g, '\\.')))
    for (const text of files) assert.equal(text.includes(host), false, host)
  }
  const defaultsSource = files[1]
  assert.equal(defaultsSource.includes('PREFERRED'), false)
  assert.equal(defaultsSource.includes('qwen3.8-flash'), false)
})
