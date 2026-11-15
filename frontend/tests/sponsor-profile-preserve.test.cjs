const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const i18n = { t: (text, values) => (values && values.name ? text.replace('{{name}}', values.name) : text) }
const providers = loadTs('providers.ts', { '../../i18n': i18n })
const defaults = loadTs('modelDefaults.ts')
const access = loadTs('providerAccess.ts', { '../../i18n': i18n, './providers': providers })
const urls = loadTs('providerUrl.ts')
const logic = loadTs('modelSettingsLogic.ts', {
  './providers': providers,
  './modelDefaults': defaults,
  './providerAccess': access,
  './providerUrl': urls,
})
const quick = loadTs('quickConnect.ts', { './modelSettingsLogic': logic })

function profile(provider, baseUrl, model) {
  return {
    version: 1,
    saved: true,
    connections: [{
      id: 'kept',
      name: provider,
      provider,
      base_url: baseUrl,
      api_key: 'fixture-key',
      has_key: true,
      image_api: 'auto',
      image_base_url: '',
      base_url_source: provider === 'compatible' ? 'user' : 'preset',
    }],
    analysis: { connection_id: 'kept', model, capability: 'auto', model_source: 'user' },
    vision: null,
    cover: null,
    cover_enabled: false,
    analysis_mode: 'auto',
  }
}

test('saved 88API, Infistar, APIMart and custom profiles are not rewritten', () => {
  const samples = [
    profile('api88', 'https://api.88api.ai/v1', 'qwen3.8-flash'),
    profile('infistar', 'https://infistar.cc/v1', 'doubao-seed-2-1-turbo-260628'),
    profile('apimart', 'https://api.apimart.ai/v1', 'qwen3.8-flash'),
    profile('compatible', 'https://gw.example.com/v1', 'my-model'),
  ]
  for (const sample of samples) {
    const before = JSON.stringify(sample)
    const loaded = logic.prepareLoaded(sample)
    assert.equal(JSON.stringify(loaded), before)
    assert.equal(quick.quickConnectPatch(loaded), undefined)
    const again = logic.chooseProvider(loaded, 'analysis', loaded.connections[0].provider, {}, false)
    assert.equal(again.changed, false)
    assert.equal(again.settings.connections[0].api_key, 'fixture-key')
    assert.equal(again.settings.connections[0].base_url, sample.connections[0].base_url)
    assert.equal(again.settings.analysis.model, sample.analysis.model)
  }
})

test('a blank unsaved profile is not assigned APIMart until the user chooses it', () => {
  const blank = {
    version: 1,
    saved: false,
    connections: [],
    analysis: null,
    vision: null,
    cover: null,
    cover_enabled: false,
    analysis_mode: 'auto',
  }
  const loaded = logic.prepareLoaded(blank)
  assert.equal(loaded.analysis, null)
  assert.equal(loaded.connections.length, 0)
  const chosen = logic.chooseProvider(loaded, 'analysis', 'apimart', {}, false)
  assert.equal(chosen.connection.provider, 'apimart')
  assert.equal(chosen.connection.base_url, 'https://api.apimart.ai/v1')
  assert.equal(chosen.connection.api_key, '')
  assert.equal(chosen.settings.analysis.model, '')
  const probed = quick.quickConnectPatch(chosen.settings)
  assert.equal(probed.analysis.model, 'deepseek-v4-flash')
  assert.equal(probed.analysis.model_source, 'preset')
  assert.equal(chosen.settings.connections[0].provider, 'apimart')
})

test('explicit visual mode never selects a text-only model, and a missing live id is not invented', () => {
  const defaults = loadTs('modelDefaults.ts')
  const connection = { id: 'main', provider: 'apimart' }
  const blank = () => ({
    analysis: { connection_id: 'main', model: '', capability: 'auto' },
    vision: null, cover: null, cover_enabled: false, analysis_mode: 'visual',
  })
  const textOnly = [{ id: 'deepseek-v4-flash', analysis: true, capability: 'text' }]
  const mixed = [...textOnly, { id: 'gemini-3.8-flash', analysis: true, capability: 'multimodal' }]
  assert.equal(defaults.applyModelDefaults(blank(), connection, textOnly, false).analysis.model, '')
  assert.equal(defaults.applyModelDefaults(blank(), connection, mixed, false).analysis.model, 'gemini-3.8-flash')
  const subtitle = { ...blank(), analysis_mode: 'subtitle' }
  assert.equal(defaults.defaultModel('apimart', textOnly), 'deepseek-v4-flash')
  assert.equal(defaults.defaultModel('apimart', [{ id: 'account-only', analysis: true, capability: 'text' }]), 'account-only')
  assert.equal(defaults.applyModelDefaults(subtitle, connection, textOnly, false).analysis.model, 'deepseek-v4-flash')
})
