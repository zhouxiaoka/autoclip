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

test('B2: catalog analysis switching preserves explicit bindings and follows only a null vision', () => {
  const logic = loadTs('modelSettingsLogic.ts', { '../../i18n': { t: text => text } })
  const defaults = loadTs('modelDefaults.ts')
  const connections = ['old', 'new', 'independent'].map(id => ({ id, name: id, provider: 'ollama', base_url: '', image_api: 'auto', image_base_url: '' }))
  for (const bindingId of ['old', 'independent']) {
    for (const cover_enabled of [true, false]) {
      const state = { ...blank(), connections, analysis: { connection_id: 'old', model: 'old-analysis', capability: 'auto' },
        vision: { connection_id: bindingId, model: 'my-vision', capability: 'multimodal', model_source: 'user' },
        cover: { connection_id: bindingId, model: 'my-cover', capability: 'auto', model_source: 'user' }, cover_enabled, cover_follows_analysis: false }
      const switched = view.assignAnalysis(state, connections[1])
      const filled = defaults.applyModelDefaults(switched, connections[1], [{ id: 'new-analysis', analysis: true, capability: 'multimodal' }, { id: 'new-image', image: true }], false)
      assert.equal(filled.analysis.connection_id, 'new')
      assert.equal(filled.analysis.model, 'new-analysis')
      for (const value of [switched, filled, logic.forSave(logic.setVisual(logic.setVisual(filled, false), true))]) {
        assert.deepEqual(value.vision, state.vision)
        assert.deepEqual(value.cover, state.cover)
      }
      const followed = view.assignAnalysis({ ...state, vision: null }, connections[1])
      assert.equal(followed.vision, null)
      assert.equal(logic.followedVisionBinding(followed).connection_id, 'new')
      assert.equal(view.assignAnalysis(state, connections[0]), state)
    }
  }
})

test('catalog lists all 40 presets in the four product groups', () => {
  const rows = view.catalogProviders()
  assert.equal(rows.length, 40)
  const groups = view.groupCatalog(rows)
  assert.equal(groups.recommended.length, 3)
  assert.equal(groups.popular.length, 10)
  assert.equal(groups.local.length, 4)
  assert.equal(groups.more.length, 23)
  assert.equal(groups.recommended.map(row => row.id).join(','), 'apimart,api88,infistar')
})

test('search matches display names and capability filter hides other types', () => {
  const deepseek = view.filterCatalog('DeepSeek', 'all')
  assert.equal(deepseek.length, 1)
  assert.equal(deepseek[0].id, 'deepseek')
  const asr = view.filterCatalog('', 'asr')
  assert.equal(asr.map(row => row.id).slice().sort().join(','), 'dashscope,sensevoice,siliconflow,whisper')
  const video = view.filterCatalog('', 'video')
  assert.ok(video.every(row => row.capabilities.includes('video')))
  assert.ok(video.some(row => row.id === 'seed'))
  assert.ok(video.some(row => row.id === 'apimart'))
  const image = view.filterCatalog('', 'image')
  assert.ok(image.some(row => row.id === 'apimart'))
  assert.deepEqual(view.catalogPreset('apimart').capabilities, ['language', 'image', 'video'])
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
  assert.equal(view.connectKind(view.catalogPreset('apimart')), 'legacy')
  assert.equal(view.catalogPreset('apimart').base_url, 'https://api.apimart.ai/v1')
  assert.equal(view.catalogPreset('apimart').docs_url, 'https://go.apimart.ai/tw-autoclip')
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
    assert.equal(result.changed, true, id)
    assert.equal(result.connection.catalog_provider_id, id)
    assert.equal(result.settings.connections.length, 1, id)
    assert.equal(result.settings.analysis, null, id)
    assert.equal(view.catalogDraftConnection(preset).catalog_provider_id, id)
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
  assert.equal(view.isCatalogConnected(keyed, view.catalogPreset('siliconflow')), false)
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
  assert.equal(view.isCatalogConnected(settings, view.catalogPreset('deepseek')), false)
})

test('catalog requires successful verification for keyed and keyless connections', () => {
  for (const provider of ['deepseek', 'siliconflow', 'ollama', 'lmstudio']) {
    const preset = view.catalogPreset(provider)
    for (const validation_status of [undefined, 'unchecked', 'failed', 'ok']) {
      const connection = {
        ...view.catalogDraftConnection(preset), id: 'conn', has_key: true, validation_status,
      }
      const settings = { ...blank(), connections: [connection] }
      assert.equal(view.isCatalogConnected(settings, preset), validation_status === 'ok', `${provider}: ${validation_status}`)
    }
  }
})

test('validation is invalidated by credential and endpoint edits before the catalog renders', () => {
  const logic = loadTs('modelSettingsLogic.ts', { '../../i18n': { t: text => text } })
  const preset = view.catalogPreset('deepseek')
  const settings = { ...blank(), connections: [{ ...view.catalogDraftConnection(preset), id: 'ds', has_key: true }] }
  const verified = logic.applyValidation(settings, 'ds', { success: true, ok: true, result: 'success' })
  assert.equal(view.isCatalogConnected(verified, preset), true)
  for (const patch of [{ api_key: 'test-replacement' }, { base_url: 'https://example.test/v1' }]) {
    assert.equal(view.isCatalogConnected(logic.editConnection(verified, 'ds', patch), preset), false)
  }
  const failed = logic.applyValidation(verified, 'ds', { success: false, ok: false, result: 'failed' })
  assert.equal(view.isCatalogConnected(failed, preset), false)
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
  assert.equal(view.isCatalogConnected(sense, view.catalogPreset('whisper'), { whisper: true }), true)
  const back = view.selectLocalAsr(sense, 'whisper')
  assert.equal(back.transcription.provider, 'whisper_local')
})

test('ready local ASR stays available independently of the selected transcription provider', () => {
  for (const provider of ['whisper_local', 'sensevoice_local', 'cloud']) {
    const settings = { ...blank(), transcription: { provider, model: 'base' } }
    for (const id of ['whisper', 'sensevoice']) {
      assert.equal(view.isCatalogConnected(settings, view.catalogPreset(id)), false)
      assert.equal(view.isCatalogConnected(settings, view.catalogPreset(id), { [id]: false }), false)
      assert.equal(view.isCatalogConnected(settings, view.catalogPreset(id), { [id]: true }), true)
    }
  }
  assert.equal(view.whisperAsrReady({ status: 'not_installed' }, [{ name: 'base', status: 'downloaded' }], 'base'), false)
  assert.equal(view.whisperAsrReady({ status: 'installed' }, [{ name: 'base', status: 'downloaded' }], 'small'), false)
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
    'settings.providers.title', 'settings.providers.configure',
    'settings.providers.repair_custom', 'settings.providers.repair_custom_hint', 'settings.providers.custom_group',
    'settings.providers.needs_endpoint',
  ])
  const translatedShort = new Set(['dashscope', 'openai', 'infistar', 'api88', 'gemini', 'deepseek', 'seed', 'kimi', 'glm', 'grok', 'ollama', 'lmstudio'])
  for (const [id, row] of Object.entries(catalog.providers)) {
    const shown = row.ui_name || row.display_name
    if (shown) needed.add(shown)
    if (row.hint) needed.add(row.hint)
    if (translatedShort.has(id) && row.short_name) needed.add(row.short_name)
    if (translatedShort.has(id) && row.context_hint) needed.add(row.context_hint)
    if (row.sponsor) {
      needed.add(row.sponsor.offer)
      if (translatedShort.has(id) && row.sponsor.description) needed.add(row.sponsor.description)
    }
  }
  for (const lang of langs) {
    for (const key of needed) {
      assert.ok(locales[lang][key] && String(locales[lang][key]).trim(), `${lang}: ${key}`)
    }
  }
})

test('endpoint drafts stay out of every purpose and default until address and validation pass', () => {
  const slots = loadTs('defaultModelSlots.ts', { '../../i18n': { t: text => text } })
  const logic = loadTs('modelSettingsLogic.ts', { '../../i18n': { t: text => text } })
  const defaults = loadTs('modelDefaults.ts', { '../../i18n': { t: text => text } })
  for (const preset of view.catalogProviders().filter(row => !row.base_url && row.protocol !== 'local')) {
    assert.ok(view.filterCatalog(preset.id, 'all').some(row => row.id === preset.id))
    for (const [base_url, validation_status, ready] of [['', 'ok', false], ['https://endpoint.example.test/v1', 'unchecked', false], ['https://endpoint.example.test/v1', 'failed', false], ['https://endpoint.example.test/v1', 'ok', true]]) {
      const connection = { id: 'endpoint', name: preset.display_name, provider: 'compatible', catalog_provider_id: preset.id, base_url, has_key: true, validation_status }
      assert.equal(logic.connectionReady(connection), ready, preset.id)
      const model = { id: 'test-model', analysis: true, capability: 'multimodal', image: true, asr: true, asr_supported: true }
      const lists = { endpoint: { models: [model], source: 'live', preview: false } }
      const settings = { ...blank(), connections: [connection] }
      for (const purpose of slots.PURPOSE_IDS) {
        const groups = slots.collectModelGroups(settings, lists, purpose)
        assert.equal(groups.some(group => group.offers.some(offer => offer.connectionId === connection.id)), ready, `${preset.id}: ${purpose}`)
        const selected = slots.applySmartSelection(settings, purpose, model.id, connection.id)
        assert.equal(!!selected[purpose]?.connection_id, ready, `${preset.id}: smart ${purpose}`)
        const fixed = slots.applyFixedSelection(settings, purpose, model.id, connection.id)
        assert.equal(!!fixed[purpose]?.connection_id, ready, `${preset.id}: fixed ${purpose}`)
      }
      assert.equal(!!view.assignAnalysis(settings, connection).analysis, ready)
      assert.equal(view.isCatalogConnected(settings, preset), ready)
      const stale = { ...settings, analysis: { connection_id: connection.id, model: '', capability: 'auto' } }
      assert.equal(!!defaults.applyModelDefaults(stale, connection, [model], false).analysis.model, ready)
      const bound = { ...stale, analysis: { ...stale.analysis, model: model.id } }
      assert.equal(!!logic.setCoverEnabled(bound, true, lists).cover, ready)
      if (ready) {
        assert.equal(logic.connectionReady(logic.editConnection(settings, connection.id, { base_url: 'https://changed.example.test/v1' }).connections[0]), false)
        assert.equal(logic.connectionReady(logic.editConnection(settings, connection.id, { api_key: 'test-only' }).connections[0]), false)
      }
    }
  }
})
