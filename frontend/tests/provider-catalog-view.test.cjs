const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('path')
const { loadTs, PRESETS } = require('./load-ts.cjs')

const catalog = JSON.parse(fs.readFileSync(PRESETS, 'utf8'))
const view = loadTs('providerCatalogView.ts', {
  '../../i18n': { t: text => text },
})

const blank = () => ({
  version: 1, saved: false, connections: [],
  analysis: null, vision: null, cover: null,
  transcription: { provider: 'whisper_local', model: 'base' },
  cover_enabled: false, allow_send_frame: true, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
})

test('catalog lists all 38 presets in the four product groups', () => {
  const rows = view.catalogProviders()
  assert.equal(rows.length, 38)
  const groups = view.groupCatalog(rows)
  assert.equal(groups.recommended.length, 2)
  assert.equal(groups.popular.length, 10)
  assert.equal(groups.local.length, 4)
  assert.equal(groups.more.length, 22)
  assert.equal(groups.recommended.map(row => row.id).join(','), 'api88,infistar')
})

test('search matches display names and capability filter hides other types', () => {
  const deepseek = view.filterCatalog('DeepSeek', 'all')
  assert.equal(deepseek.length, 1)
  assert.equal(deepseek[0].id, 'deepseek')
  const asr = view.filterCatalog('', 'asr')
  assert.equal(asr.map(row => row.id).slice().sort().join(','), 'api88,dashscope,sensevoice,siliconflow,whisper')
  const video = view.filterCatalog('', 'video')
  assert.ok(video.every(row => row.capabilities.includes('video')))
  assert.ok(video.some(row => row.id === 'seed'))
  assert.equal(view.filterCatalog('没有这家', 'all').length, 0)
})

test('more stays collapsed until search or a capability filter is on', () => {
  assert.equal(view.shouldExpandMore('', 'all', 22), false)
  assert.equal(view.shouldExpandMore('groq', 'all', 1), true)
  assert.equal(view.shouldExpandMore('', 'language', 20), true)
  assert.equal(view.shouldExpandMore('x', 'all', 0), false)
})

test('unconnected presets stay visible and point at configure / compatible / guide', () => {
  const settings = blank()
  const unconnected = view.catalogProviders().filter(row => !view.isCatalogConnected(settings, row))
  assert.ok(unconnected.length >= 30, 'most presets start unconnected')
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('deepseek')), false)
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('whisper')), false)
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('whisper'), { whisper: true }), true)
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('sensevoice')), false)
  assert.equal(view.whisperAsrReady({ status: 'installed' }, [{ name: 'base', status: 'downloaded' }], 'base'), true)
  assert.equal(view.whisperAsrReady({ status: 'installed' }, [{ name: 'base', status: 'available' }], 'base'), false)
  assert.equal(view.sensevoiceAsrReady({ status: 'ready' }), true)
  assert.equal(view.sensevoiceAsrReady({ status: 'not_installed' }), false)
  assert.equal(view.connectKind(view.catalogPreset('deepseek')), 'legacy')
  assert.equal(view.connectKind(view.catalogPreset('siliconflow')), 'compatible')
  assert.equal(view.connectKind(view.catalogPreset('anthropic')), 'guide')
  assert.equal(view.connectKind(view.catalogPreset('whisper')), 'local_asr')
})

test('empty-url presets are not live defaults and stay off the picker', () => {
  for (const id of ['azure-openai', 'amazon-bedrock', 'google-vertex', 'cloudflare-workers-ai', 'cloudflare-ai-gateway']) {
    const preset = view.catalogPreset(id)
    assert.ok(preset, id)
    assert.equal(preset.base_url, '')
    assert.equal(['guide', 'needs_endpoint'].includes(view.connectKind(preset)), true, id)
    assert.equal(view.isLiveConnectable(preset), false, id)
    const result = view.ensureCatalogConnection(blank(), preset)
    assert.equal(result.changed, false, id)
    assert.equal(result.connection, undefined, id)
    assert.equal(result.settings.connections.length, 0, id)
    assert.equal(result.settings.analysis, null, id)
    assert.equal(view.catalogDraftConnection(preset), undefined, id)
  }
  const providers = loadTs('providers.ts', { '../../i18n': { t: text => text } })
  const picker = providers.providerPickerOptions().flatMap(group => group.options.map(option => option.value))
  for (const id of ['azure-openai', 'amazon-bedrock', 'google-vertex', 'cloudflare-workers-ai', 'cloudflare-ai-gateway']) {
    assert.equal(picker.includes(id), false, id)
  }
  assert.equal(picker.includes('compatible'), true)
})

test('opening a catalog provider creates a draft without treating an empty key as connected', () => {
  const settings = blank()
  const draft = view.catalogDraftConnection(view.catalogPreset('siliconflow'))
  assert.equal(draft.provider, 'compatible')
  assert.equal(draft.base_url, catalog.providers.siliconflow.base_url)
  assert.equal(settings.connections.length, 0)
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('siliconflow')), false)
  assert.equal(view.catalogDraftConnection(view.catalogPreset('anthropic')), undefined)
  const created = view.ensureCatalogConnection(settings, view.catalogPreset('siliconflow'), undefined, () => 'conn-sf')
  assert.equal(created.changed, true)
  assert.equal(created.connection.provider, 'compatible')
  assert.equal(created.connection.base_url, catalog.providers.siliconflow.base_url)
  assert.equal(view.isCatalogConnected(created.settings, view.catalogPreset('siliconflow')), false)
  const keyed = {
    ...created.settings,
    connections: created.settings.connections.map(row => row.id === 'conn-sf' ? { ...row, has_key: true } : row),
  }
  assert.equal(view.isCatalogConnected(keyed, view.catalogPreset('siliconflow')), true)
  assert.equal(view.findCatalogConnection(keyed, view.catalogPreset('siliconflow')).id, 'conn-sf')
})

test('legacy providers reuse an existing connection and can become the analysis binding', () => {
  const settings = {
    ...blank(),
    connections: [{ id: 'ds', name: 'DeepSeek', provider: 'deepseek', base_url: '', api_key: 'sk-test', has_key: true, image_api: 'auto', image_base_url: '' }],
  }
  const reused = view.ensureCatalogConnection(settings, view.catalogPreset('deepseek'))
  assert.equal(reused.connection.id, 'ds')
  assert.equal(reused.settings.analysis.connection_id, 'ds')
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('deepseek')), true)
})

test('unmatched custom gateways stay repairable and do not attach to a catalog preset', () => {
  const settings = {
    ...blank(),
    connections: [{
      id: 'gw', name: 'Home gateway', provider: 'compatible',
      base_url: 'https://gw.home.example/v1', api_key: '', has_key: false,
      image_api: 'auto', image_base_url: '',
    }],
    analysis: { connection_id: 'gw', model: 'local-model', capability: 'auto' },
  }
  assert.equal(view.isUnmatchedCompatible(settings.connections[0]), true)
  assert.equal(view.matchedCatalogPreset(settings.connections[0]), undefined)
  assert.equal(view.unmatchedCompatibleConnections(settings).map(row => row.id).join(','), 'gw')
  assert.equal(view.customCatalogId('gw'), 'custom:gw')
  assert.equal(view.customConnectionId('custom:gw'), 'gw')
  const silicon = {
    ...settings.connections[0],
    id: 'sf',
    base_url: catalog.providers.siliconflow.base_url,
  }
  assert.equal(view.isUnmatchedCompatible(silicon), false)
  assert.equal(view.matchedCatalogPreset(silicon).id, 'siliconflow')
})

test('guide-only providers do not write a connection', () => {
  const settings = blank()
  const result = view.ensureCatalogConnection(settings, view.catalogPreset('anthropic'))
  assert.equal(result.changed, false)
  assert.equal(result.connection, undefined)
  assert.equal(result.settings.connections.length, 0)
})

test('local ASR switching does not invent cloud connections', () => {
  const sense = view.selectLocalAsr(blank(), 'sensevoice')
  assert.equal(sense.transcription.provider, 'sensevoice_local')
  assert.equal(view.isCatalogConnected(sense, view.catalogPreset('sensevoice')), false)
  assert.equal(view.isCatalogConnected(sense, view.catalogPreset('sensevoice'), { sensevoice: true }), true)
  assert.equal(view.isCatalogConnected(sense, view.catalogPreset('whisper'), { whisper: true }), false)
  const back = view.selectLocalAsr(sense, 'whisper')
  assert.equal(back.transcription.provider, 'whisper_local')
})

test('catalog host helper never returns a full URL', () => {
  const host = view.catalogHost('https://api.siliconflow.cn/v1/chat/completions')
  assert.equal(host, 'api.siliconflow.cn')
  assert.equal(host.includes('/'), false)
  assert.equal(view.catalogHost('not a url'), '')
})

test('every catalog name and hint used in the UI exists in all eight locales', () => {
  const langs = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr']
  const locales = Object.fromEntries(langs.map(lang => [
    lang,
    JSON.parse(fs.readFileSync(path.join(__dirname, '../src/i18n/locales', `${lang}.json`), 'utf8')),
  ]))
  const needed = new Set([
    'settings.providers.title', 'settings.providers.unconnected_guide', 'settings.providers.configure',
    'settings.providers.repair_custom', 'settings.providers.repair_custom_hint', 'settings.providers.custom_group',
    'settings.providers.needs_endpoint', 'settings.providers.needs_endpoint_guide',
  ])
  for (const row of Object.values(catalog.providers)) {
    for (const key of ['ui_name', 'display_name', 'short_name', 'hint']) {
      if (row[key]) needed.add(row[key])
    }
    if (row.sponsor) {
      needed.add(row.sponsor.offer)
      needed.add(row.sponsor.description)
    }
  }
  for (const lang of langs) {
    for (const key of needed) {
      assert.ok(locales[lang][key] && String(locales[lang][key]).trim(), `${lang}: ${key}`)
    }
  }
})
