const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

const slots = loadTs('defaultModelSlots.ts', { '../../i18n': { t: text => text } })
const plain = value => JSON.parse(JSON.stringify(value))

const conn = (id, provider, extra = {}) => ({
  id, name: provider, provider, base_url: '', api_key: 'k', has_key: true,
  image_api: 'auto', image_base_url: '', validation_status: 'ok', ...extra,
})
const settings = (extra = {}) => ({
  version: 1, saved: true,
  connections: [conn('infi', 'infistar'), conn('ds', 'dashscope'), conn('or', 'openrouter')],
  analysis: { connection_id: 'ds', model: 'qwen-plus', capability: 'text', model_source: 'user' },
  vision: null, cover: null,
  transcription: { provider: 'whisper_local', model: 'base', model_source: 'user' },
  cover_enabled: false, allow_send_frame: false, analysis_mode: 'auto', allow_visual_screening: true,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
  ...extra,
})
const lists = {
  infi: { source: 'live', models: [
    { id: 'gpt-4o-mini', capability: 'multimodal', analysis: true, image: false },
    { id: 'qwen-plus', capability: 'text', analysis: true, image: false },
  ] },
  ds: { source: 'live', models: [
    { id: 'qwen-plus', capability: 'text', analysis: true, image: false },
    { id: 'qwen-vl-plus', capability: 'multimodal', analysis: true, image: false },
    { id: 'wanx2.1-t2i-turbo', analysis: false, image: true },
  ] },
  or: { source: 'live', models: [
    { id: 'gpt-4o-mini', capability: 'multimodal', analysis: true, image: false },
  ] },
}

test('four purpose slots and no video purpose', () => {
  assert.deepEqual(plain(slots.PURPOSE_IDS), ['analysis', 'vision', 'transcription', 'cover'])
  assert.equal(slots.PURPOSE_IDS.includes('video'), false)
  assert.deepEqual(plain(slots.COMING_SOON), ['配音 · 语音合成', '配乐 · 音乐'])
})

test('old files without model_source count as user; empty slots are preset', () => {
  assert.equal(slots.resolvedModelSource({ model: 'qwen-plus' }), 'user')
  assert.equal(slots.resolvedModelSource({ model: '' }), 'preset')
  assert.equal(slots.resolvedModelSource({ model: 'qwen-flash', model_source: 'preset' }), 'preset')
  assert.equal(slots.resolvedModelSource({ model: 'mine', model_source: 'user' }), 'user')
})

test('provider rank is recommended then popular then other', () => {
  assert.ok(slots.providerRank('api88') < slots.providerRank('dashscope'))
  assert.ok(slots.providerRank('infistar') < slots.providerRank('openai'))
  assert.ok(slots.providerRank('dashscope') < slots.providerRank('openrouter'))
})

test('a live list without a suitable model does not invent catalog candidates', () => {
  const groups = slots.collectModelGroups(settings(), lists, 'transcription')
  assert.equal(groups.length, 0)
  const cover = slots.collectModelGroups(settings(), lists, 'cover')
  assert.equal(cover.some(group => group.modelId === 'wanx2.1-t2i-turbo'), true, 'image models that are on a live list stay')
  const emptyCover = slots.collectModelGroups(settings({
    connections: [conn('ds', 'dashscope')],
  }), { ds: { source: 'live', models: [{ id: 'qwen-plus', capability: 'text', analysis: true, image: false }] } }, 'cover')
  assert.equal(emptyCover.length, 0)
})

test('cloud transcription only lists models with a supported, non-preview ASR route', () => {
  const asrLists = {
    ds: { source: 'live', models: [
      { id: 'qwen-audio-3.0-asr-flash', asr: true, asr_supported: true, analysis: false, image: false },
      { id: 'paraformer-v2', asr: true, asr_supported: false, analysis: false, image: false },
      { id: 'qwen-audio-preview', asr: true, asr_supported: true, asr_preview: true, analysis: false, image: false },
      { id: 'qwen-plus', capability: 'text', analysis: true, image: false },
    ] },
  }
  const groups = slots.collectModelGroups(settings({ connections: [conn('ds', 'dashscope')] }), asrLists, 'transcription')
  assert.equal(groups.length, 1)
  assert.equal(groups[0].modelId, 'qwen-audio-3.0-asr-flash')
})

test('a key without a passed access check is not shown as connected', () => {
  const state = settings({
    connections: [
      conn('ds', 'dashscope', { validation_status: 'unchecked' }),
      conn('infi', 'infistar', { validation_status: 'failed' }),
    ],
  })
  const groups = slots.collectModelGroups(state, lists, 'analysis')
  const qwen = groups.find(group => group.modelId === 'qwen-plus')
  assert.ok(qwen)
  assert.equal(qwen.offers.every(offer => offer.connected === false), true)
  assert.equal(slots.preferredOffer(qwen.offers), undefined)
})

test('the same model id is listed once and smart pick prefers the sponsor connection', () => {
  const groups = slots.collectModelGroups(settings(), lists, 'analysis')
  const gpt = groups.find(group => group.modelId === 'gpt-4o-mini')
  assert.ok(gpt)
  assert.equal(gpt.offers.length >= 2, true)
  const preferred = slots.preferredOffer(gpt.offers)
  assert.equal(preferred.provider, 'infistar')
  assert.equal(gpt.offers.some(offer => !offer.connected), true, 'unconnected catalog providers stay visible')
  const next = slots.applySmartSelection(settings(), 'analysis', 'gpt-4o-mini', preferred.connectionId)
  assert.equal(next.analysis.model, 'gpt-4o-mini')
  assert.equal(next.analysis.connection_id, 'infi')
  assert.equal(next.analysis.model_source, 'preset')
})

test('fixed selection pins the chosen connection and marks user', () => {
  const next = slots.applyFixedSelection(settings(), 'analysis', 'qwen-plus', 'ds')
  assert.equal(next.analysis.model_source, 'user')
  assert.equal(next.analysis.connection_id, 'ds')
  assert.equal(slots.isFixedSelected(next, 'analysis', 'qwen-plus', { modelId: 'qwen-plus', provider: 'dashscope', connectionId: 'ds', connected: true, displayName: '阿里云百炼' }), true)
})

test('vision follow warns only when the followed model is known to lack vision', () => {
  const state = settings()
  assert.equal(slots.visionWarning(state, lists), 'follow')
  const withVision = slots.applySmartSelection(state, 'analysis', 'qwen-vl-plus', 'ds')
  assert.equal(slots.visionWarning({ ...withVision, vision: null }, lists), null)
  const independent = slots.applyFixedSelection(state, 'vision', 'gpt-4o-mini', 'infi')
  assert.equal(slots.visionWarning(independent, lists), null)
  const badPick = slots.applyFixedSelection(state, 'vision', 'qwen-plus', 'ds')
  assert.equal(slots.visionWarning(badPick, lists), 'selected')
  assert.equal(slots.visionWarning(settings({ analysis: { connection_id: 'ds', model: 'qwen-plus', capability: 'auto', model_source: 'user' } }), {}), null, 'unknown capability is not a red warning')
  assert.equal(slots.visionWarning(settings({ analysis_mode: 'subtitle' }), lists), null, 'subtitle mode does not need vision')
})

test('cover off keeps the cover assignment and cover_enabled', () => {
  const on = slots.applySmartSelection(settings(), 'cover', 'wanx2.1-t2i-turbo', 'ds')
  assert.equal(on.cover_enabled, true)
  assert.equal(on.cover.model, 'wanx2.1-t2i-turbo')
  assert.equal(on.cover.model_source, 'preset')
  const off = slots.applyCoverOff(on)
  assert.equal(off.cover_enabled, false)
  assert.equal(off.cover.model, 'wanx2.1-t2i-turbo')
  assert.deepEqual(plain(slots.slotSummary(off, lists, 'cover')), { kind: 'off' })
})

test('vision follow and local transcription summaries', () => {
  assert.deepEqual(plain(slots.slotSummary(settings(), lists, 'vision')), { kind: 'follow', model: 'qwen-plus' })
  assert.deepEqual(plain(slots.slotSummary(settings(), lists, 'transcription')), { kind: 'local', model: 'base', provider: 'whisper_local' })
  const cloud = slots.applySmartSelection(settings(), 'transcription', 'qwen-audio', 'ds')
  assert.equal(cloud.transcription.model_source, 'preset')
  assert.equal(cloud.transcription.provider, 'cloud')
})

test('hidden non-vision count and vision-only groups', () => {
  assert.equal(slots.hiddenNonVisionCount(lists), 1)
  const vision = slots.collectModelGroups(settings(), lists, 'vision')
  assert.equal(vision.some(group => group.modelId === 'qwen-plus'), false)
  assert.equal(vision.some(group => group.modelId === 'qwen-vl-plus'), true)
  assert.equal(vision.some(group => group.modelId === 'gpt-4o-mini'), true)
})

test('slot telemetry is enums and a boolean — never a model id', () => {
  const payload = plain(slots.slotTelemetry(settings(), lists))
  assert.equal(payload.analysis_source, 'user')
  assert.equal(payload.vision_source, 'follow')
  assert.equal(payload.cover_source, 'frame')
  assert.equal(payload.transcription_source, 'whisper_local')
  assert.equal(payload.vision_follow_lacks_vision, true)
  assert.equal(JSON.stringify(payload).includes('qwen'), false)
  assert.equal(JSON.stringify(payload).includes('gpt'), false)
})


test('U2 reuses U1 compatible catalog connections without duplicate provider offers', () => {
  const gateway = conn('or', 'compatible', { name: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1' })
  const state = settings({ connections: [gateway], analysis: { connection_id: 'or', model: 'gpt-4o-mini', capability: 'auto', model_source: 'user' } })
  const groups = slots.collectModelGroups(state, { or: lists.or }, 'analysis')
  const group = groups.find(item => item.modelId === 'gpt-4o-mini')
  const offer = group.offers.find(item => item.provider === 'openrouter')
  assert.equal(offer.connected, true)
  assert.equal(offer.connectionId, 'or')
  assert.equal(group.offers.some(item => item.provider === 'compatible'), false)
  assert.equal(slots.slotSummary(state, lists, 'analysis').provider, 'OpenRouter')
  const next = slots.applySmartSelection(state, 'analysis', group.modelId, offer.connectionId)
  assert.equal(next.connections[0].provider, 'compatible', 'routing retains the U1 connection API')
  assert.equal(next.analysis.model_source, 'preset')
})

test('compatible catalog offers require validation for live and enriched models', () => {
  const infi = { ...lists.infi, models: [{ id: 'deepseek-flash', capability: 'text', analysis: true, image: false }] }
  for (const validation_status of [undefined, 'unchecked', 'failed', 'ok']) {
    const gateway = conn('ds', 'compatible', {
      name: 'DeepSeek', base_url: 'https://api.deepseek.com', validation_status,
    })
    const state = settings({ connections: [conn('infi', 'infistar'), gateway] })
    for (const gatewayList of [undefined, { source: 'live', models: infi.models }]) {
      const groups = slots.collectModelGroups(state, { infi, ...(gatewayList ? { ds: gatewayList } : {}) }, 'analysis')
      const group = groups.find(item => item.modelId === 'deepseek-flash')
      const offers = group.offers.filter(item => item.provider === 'deepseek')
      assert.equal(offers.length, 1)
      assert.equal(group.offers.some(item => item.provider === 'compatible'), false)
      assert.equal(offers[0].connectionId, 'ds')
      assert.equal(offers[0].connected, validation_status === 'ok' && !!gatewayList)
      assert.equal(!!slots.preferredOffer(offers), validation_status === 'ok' && !!gatewayList)
    }
  }
})

test('catalog enrichment respects authoritative lists on compatible connections', () => {
  const gateway = conn('ds', 'compatible', { name: 'DeepSeek', base_url: 'https://api.deepseek.com' })
  const state = settings({ connections: [conn('infi', 'infistar'), gateway] })
  const infi = { ...lists.infi, models: [{ id: 'deepseek-flash', capability: 'text', analysis: true, image: false }] }
  for (const source of ['live', 'cache']) {
    for (const models of [[], [{ id: 'deepseek-flash', capability: 'text', analysis: false, image: true }]]) {
      const groups = slots.collectModelGroups(state, { infi, ds: { source, models } }, 'analysis')
      const group = groups.find(item => item.modelId === 'deepseek-flash')
      assert.ok(group)
      assert.equal(group.offers.some(offer => offer.provider === 'deepseek'), false)
      assert.equal(group.offers.some(offer => offer.provider === 'compatible'), false)
    }
  }
})

test('missing lists create no models and do not make matched catalog offers connected', () => {
  const gateway = conn('ds', 'compatible', { name: 'DeepSeek', base_url: 'https://api.deepseek.com' })
  const state = settings({ connections: [conn('infi', 'infistar'), gateway] })
  assert.deepEqual(plain(slots.collectModelGroups(state, {}, 'analysis')), [])
  const infi = { ...lists.infi, models: [{ id: 'deepseek-flash', capability: 'text', analysis: true, image: false }] }
  const groups = slots.collectModelGroups(state, { infi }, 'analysis')
  const group = groups.find(item => item.modelId === 'deepseek-flash')
  const offer = group.offers.find(item => item.provider === 'deepseek')
  assert.ok(offer)
  assert.equal(offer.connectionId, 'ds')
  assert.equal(offer.connected, false)
  assert.equal(slots.preferredOffer([offer]), undefined)
})

test('catalog and preview lists never make a validated connection selectable', () => {
  for (const flags of [
    { source: 'catalog' }, { source: 'catalog', preview: false },
    { source: 'live', preview: true }, { source: 'cache', preview: true },
  ]) {
    const groups = slots.collectModelGroups(settings(), {
      ...lists, infi: { ...lists.infi, ...flags },
    }, 'analysis')
    const gpt = groups.find(group => group.modelId === 'gpt-4o-mini')
    assert.equal(gpt.offers.find(offer => offer.connectionId === 'infi').connected, false)
    assert.equal(slots.preferredOffer(gpt.offers).connectionId, 'or')
  }
  const cached = slots.collectModelGroups(settings(), {
    infi: { ...lists.infi, source: 'cache', preview: false },
  }, 'analysis')
  assert.equal(slots.preferredOffer(cached.find(group => group.modelId === 'gpt-4o-mini').offers).connectionId, 'infi')
})
