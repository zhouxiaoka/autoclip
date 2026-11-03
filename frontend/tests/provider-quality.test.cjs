const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTs } = require('./load-ts.cjs')

const quality = loadTs('providerQuality.ts')
const presets = loadTs('providerPresets.ts')
const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })

const EXPECTED = {
  deepseek: ['high', 'under_5m'],
  dashscope: ['high', 'under_5m'],
  compatible: ['high', 'mid_5_20m'],
  api88: ['mid', 'mid_5_20m'],
  ollama: ['mid', 'mid_5_20m'],
  lmstudio: ['mid', 'mid_5_20m'],
  gemini: ['low', 'over_20m'],
  openai: ['low', 'mid_5_20m'],
}

test('tier mapping reads the static quality JSON and hides unmeasured providers', () => {
  for (const [id, [success, latency]] of Object.entries(EXPECTED)) {
    const row = quality.qualityFor(id)
    assert.equal(row.success_tier, success, id)
    assert.equal(row.latency_tier, latency, id)
  }
  assert.equal(quality.qualityFor('gemini').caveat_key, 'settings.providers.caveat.gemini_free_rpm')
  assert.equal(quality.qualityFor('openai').caveat_key, 'settings.providers.caveat.openai_network')
  assert.equal(quality.qualityFor('deepseek').caveat_key, undefined)
  for (const id of ['seed', 'kimi', 'glm', 'infistar', 'apimart', 'whisper']) {
    assert.equal(quality.qualityFor(id), undefined, id)
    assert.equal(presets.getProvider(id).success_tier, undefined, id)
  }
  assert.equal(presets.getProvider('deepseek').success_tier, 'high')
  assert.equal(presets.getProvider('deepseek').latency_tier, 'under_5m')
  assert.equal(presets.getProvider('openai').caveat_key, 'settings.providers.caveat.openai_network')
  assert.equal(quality.successTierOf(0.8), 'high')
  assert.equal(quality.successTierOf(0.799), 'mid')
  assert.equal(quality.successTierOf(0.6), 'mid')
  assert.equal(quality.successTierOf(0.599), 'low')
  assert.equal(quality.latencyTierOf(4.9), 'under_5m')
  assert.equal(quality.latencyTierOf(5), 'mid_5_20m')
  assert.equal(quality.latencyTierOf(20), 'mid_5_20m')
  assert.equal(quality.latencyTierOf(20.1), 'over_20m')
})

test('sponsors stay first, low tiers stay in the hot or cloud group', () => {
  assert.deepEqual([...providers.recommendedSetupProviders()], ['api88', 'infistar', 'apimart', 'deepseek', 'dashscope'])
  const cloud = providers.providerPickerOptions().find(group => group.options.some(option => option.value === 'openai'))
  const cloudIds = [...cloud.options.map(option => option.value)].filter(id => id === 'gemini' || id === 'openai' || id === 'deepseek' || id === 'dashscope').sort()
  assert.deepEqual(cloudIds, ['gemini', 'openai'])
  assert.equal(quality.displayCatalogGroup({ group: 'recommended', success_tier: 'low' }), 'popular')
  assert.equal(quality.displayCatalogGroup({ group: 'recommended', sponsor: {}, success_tier: 'low' }), 'popular')
  assert.equal(quality.pickerBucket('sponsor', 'low'), 'cloud')
  assert.equal(quality.pickerBucket('cloud', 'high'), 'sponsor')
  assert.equal(quality.pickerBucket('local', 'mid'), 'local')
  assert.equal(quality.pickerBucket('compatible', 'high'), 'compatible')
  assert.equal(providers.PROVIDERS.deepseek.cloud.success_tier, 'high')
  assert.equal(providers.PROVIDERS.deepseek.cloud.latency_tier, 'under_5m')
  assert.equal(providers.PROVIDERS.api88.success_tier, 'mid')
  assert.equal(providers.PROVIDERS.ollama.local.success_tier, 'mid')
  assert.equal(providers.PROVIDERS.compatible.success_tier, 'high')
  assert.equal(providers.PROVIDERS.seed.success_tier, undefined)
  assert.equal(providers.recommendedSetupProviders().includes('gemini'), false)
  assert.equal(providers.recommendedSetupProviders().includes('openai'), false)
  assert.equal(providers.recommendedSetupProviders().includes('compatible'), false)
})

test('quality labels and caveats exist in all eight locales', () => {
  const langs = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']
  const keys = [
    'settings.providers.quality.success.high',
    'settings.providers.quality.success.mid',
    'settings.providers.quality.success.low',
    'settings.providers.quality.latency.under_5m',
    'settings.providers.quality.latency.mid_5_20m',
    'settings.providers.quality.latency.over_20m',
    'settings.providers.caveat.gemini_free_rpm',
    'settings.providers.caveat.openai_network',
    '建议先连接 {{name}}',
    '连接 {{name}}',
    '把 API 密钥粘贴到下方即可。',
  ]
  for (const lang of langs) {
    const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/i18n/locales', `${lang}.json`), 'utf8'))
    for (const key of keys) assert.ok(catalog[key] && String(catalog[key]).trim(), `${lang}: ${key}`)
  }
})
