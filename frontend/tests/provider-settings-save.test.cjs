const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

function settingsHook(initial, transport, requireCloudTranscription = false, guideBus, notifySettingsSaved = () => {}) {
  let cursor = 0
  const slots = []
  const mountEffects = []
  let mounted = false
  const react = {
    useState(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = typeof value === 'function' ? value() : value
      return [slots[i], next => { slots[i] = typeof next === 'function' ? next(slots[i]) : next }]
    },
    useRef(value) {
      const i = cursor++
      if (!(i in slots)) slots[i] = { current: value }
      return slots[i]
    },
    useEffect(fn, deps) { if (guideBus && !mounted && deps?.length === 0) mountEffects.push(fn) },
  }
  const hook = loadTs('useModelSettings.ts', {
    react,
    ...(guideBus && { './keyGuideBus': guideBus }),
    antd: { message: { success() {}, error() {} } },
    '../../i18n': { t: text => text },
    '../studio/api': { errorText: () => 'redacted' },
    '../studio/settingsReturn': { notifySettingsSaved },
    '../../analytics/experience': {
      beginExperience: () => () => {},
      beginDebouncedEditDiscovery: () => () => {},
      claimModelSettingsLoad: () => true,
      trackProviderValidation() {},
      connectionSignature: value => JSON.stringify((value?.connections || []).map(c => [c.id, c.provider, c.base_url, c.api_key ?? '', c.image_base_url])),
      shouldReportModelDiscovery: (trigger, current, loaded) => trigger !== 'edit' || current !== loaded,
    },
    './modelSettingsApi': {
      modelSettingsApi: {
        get: async () => structuredClone(initial),
        discover: async () => ({ models: [], source: 'catalog', preview: true }),
        ...transport,
      },
      bindingCapability: loadTs('modelSettingsApi.ts', { '../../services/api': {}, '../../utils/apiConfig': {} }).bindingCapability,
    },
  })
  return () => {
    cursor = 0
    const store = hook.useModelSettings('settings_model', requireCloudTranscription)
    mounted = true
    for (const effect of mountEffects.splice(0)) effect()
    return store
  }
}

const whisperSettings = () => ({
  version: 1, saved: true,
  connections: [{
    id: 'ds', name: '百炼', provider: 'dashscope',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key: 'sk-test', has_key: true, image_api: 'auto', image_base_url: '', validation_status: 'unchecked',
  }],
  analysis: { connection_id: 'ds', model: 'qwen-plus', capability: 'text', model_source: 'user' },
  vision: null, cover: null, cover_enabled: false,
  transcription: { provider: 'whisper_local', model: 'base', model_source: 'user' },
  allow_send_frame: false, analysis_mode: 'subtitle', allow_visual_screening: false,
  chunk_size: 5000, min_score_threshold: .7, max_clips_per_collection: 5,
})

test('only a usable saved analysis selection returns the user to production', async () => {
  const base = whisperSettings()
  for (const [settings, expected] of [
    [{ ...base, analysis: null }, 0],
    [{ ...base, connections: [{ ...base.connections[0], validation_status: 'failed', validation_error_type: 'invalid_key' }] }, 0],
    [{ ...base, analysis_mode: 'visual' }, 0],
    [base, 1],
  ]) {
    let writes = 0, notifications = 0
    const render = settingsHook(settings, { save: async value => { writes++; return value } },
      false, undefined, () => { notifications++ })
    await render().load()
    assert.equal((await render().save()).ok, true)
    assert.equal(writes, 1)
    assert.equal(notifications, expected)
  }
})

test('the save that follows a pending cloud choice persists Bailian transcription', async () => {
  const slots = loadTs('defaultModelSlots.ts', { '../../i18n': { t: text => text } })
  let persisted
  const render = settingsHook(whisperSettings(), {
    test: async () => ({ success: true, ok: true, result: 'ok' }),
    save: async value => { persisted = value; return { ...value, saved: true } },
  })
  await render().load()
  await Promise.resolve()
  const pending = slots.cloudTranscriptionSavePatch(true, render().settings)
  assert.equal(render().settings.transcription.provider, 'whisper_local')
  const result = await render().save(pending)
  assert.equal(result.ok, true)
  assert.equal(persisted.transcription.provider, 'cloud')
  assert.equal(persisted.transcription.model, 'qwen-audio-3.1-asr-flash')
  assert.equal(persisted.transcription.connection_id, 'ds')
  assert.equal(persisted.transcription.model_source, 'preset')
  const plain = await render().save()
  assert.equal(plain.ok, true)
  assert.equal(persisted.transcription.provider, 'cloud')
})

test('one-key setup validates the account and commits four assignments in one write', async () => {
  const writes = []
  const initial = whisperSettings()
  initial.transcription.model_source = 'preset'
  const render = settingsHook(initial, {
    discover: async () => ({ source: 'live', models: [
      { id: 'qwen-plus', analysis: true, capability: 'text' },
      { id: 'qwen-vl-plus', analysis: true, capability: 'multimodal' },
      { id: 'qwen-audio-3.1-asr-flash', asr: true, asr_supported: true },
      { id: 'qwen-image-plus', image: true },
    ] }),
    test: async () => ({ success: true, ok: true, result: 'ok' }),
    save: async value => { writes.push(value); return { ...value, saved: true } },
  })
  await render().load()
  const first = render().configureProvider(initial.connections[0])
  const repeat = await render().configureProvider(initial.connections[0])
  assert.equal(repeat.ok, false)
  assert.equal((await first).ok, true)
  assert.equal(writes.length, 1)
  const [saved] = writes
  for (const role of ['analysis', 'vision', 'transcription', 'cover']) assert.equal(saved[role].connection_id, 'ds')
  assert.equal(saved.cover_enabled, true)
  assert.equal(saved.allow_send_frame, false)
  assert.equal(saved.transcription.provider, 'cloud')
})

test('catalog-only setup releases a following cover on the previous account', async () => {
  const initial = whisperSettings()
  initial.analysis.model_source = 'preset'
  initial.cover = { ...initial.analysis, model: 'qwen-image-2.1-pro' }
  initial.cover_enabled = true
  initial.cover_follows_analysis = true
  const other = { ...initial.connections[0], id: 'other', provider: 'openai', base_url: 'https://api.openai.com/v1' }
  initial.connections.push(other)
  let written
  const render = settingsHook(initial, {
    test: async () => ({ ok: true }),
    save: async value => { written = value; return { ...value, saved: true } },
  })
  await render().load()
  assert.equal((await render().configureProvider(other)).ok, true)
  assert.equal(written.analysis.connection_id, 'other')
  assert.equal(written.cover, null)
  assert.equal(written.cover_enabled, false)
  assert.equal(written.connections.length, 2)
})

for (const cause of ['invalid key', 'missing cloud ASR']) {
  test('one-key setup preserves the prior document on ' + cause, async () => {
    let writes = 0
    let probes = 0
    const initial = whisperSettings()
    const render = settingsHook(initial, {
      discover: async () => ({ source: 'live', models: [{ id: 'qwen-plus', analysis: true }] }),
      test: async () => {
        probes++
        return cause === 'invalid key' ? { ok: false, result: 'failed', error_type: 'invalid_key' } : { ok: true, success: true }
      },
      save: async value => { writes++; return value },
    }, cause === 'missing cloud ASR')
    await render().load()
    const result = await render().configureProvider(initial.connections[0])
    assert.equal(result.ok, false)
    assert.equal(writes, 0)
    assert.equal(probes, cause === 'missing cloud ASR' ? 0 : 1)
    assert.equal(render().settings.transcription.provider, 'whisper_local')
  })
}

test('retesting a masked NVIDIA connection and saving preserves its stored key (#622)', async () => {
  const state = whisperSettings()
  const connection = {
    id: 'nvidia', provider: 'compatible', name: 'NVIDIA', has_key: true,
    base_url: 'https://integrate.api.nvidia.com/v1', image_base_url: '', image_api: 'auto',
  }
  state.connections = [connection]
  state.analysis = { connection_id: connection.id, model: 'nvidia/nemotron-3-ultra-550b-a55b', capability: 'text' }
  const tests = [], writes = []
  const render = settingsHook(state, {
    discover: async () => ({ source: 'live', models: [{ id: state.analysis.model, analysis: true }] }),
    test: async (c, model, vision, role, kind) => { tests.push({ c, kind }); return { ok: true, probe_kind: kind } },
    save: async value => { writes.push(value); return value },
  })
  await render().load()
  for (const kind of ['quick', 'trial']) {
    await render().testCatalogProvider('nvidia', {
      base_url: connection.base_url, api_key: undefined, has_key: true,
    }, kind)
  }
  assert.deepEqual(tests.map(row => row.kind), ['quick', 'trial'])
  assert.ok(tests.every(row => row.c.has_key && row.c.api_key === undefined))
  assert.equal((await render().save()).ok, true)
  const [saved] = writes[0].connections
  assert.equal(saved.has_key, true)
  assert.equal(saved.api_key, undefined, 'omit the hidden key on PUT so the backend preserves it')
})

test('catalog tests and first save use the chosen model, and saving never starts a trial (#619)', async () => {
  const state = { ...whisperSettings(), saved: false, connections: [], analysis: null }
  const models = ['gpt-4o-mini', 'gpt-5-mini'].map(id => ({ id, analysis: true, capability: 'text' }))
  const calls = [], writes = []
  const render = settingsHook(state, {
    discover: async () => ({ source: 'live', models }),
    test: async (c, model, vision, role, kind) => {
      calls.push([model, kind])
      if (model === 'changed-model') return { ok: false, result: 'transient', error_type: 'rate_limited' }
      return { ok: true, probe_kind: kind, trial_passed: kind === 'trial' }
    },
    save: async value => { writes.push(value); return { ...value, saved: true } },
  })
  await render().load()
  render().ensureCatalogProvider('openai', { api_key: 'fixture' })
  await new Promise(resolve => setImmediate(resolve))
  const { main } = render()
  assert.equal(render().settings.analysis.model, 'gpt-5-mini')
  for (const kind of ['quick', 'trial']) {
    await render().testCatalogProvider('openai', { base_url: main.base_url, api_key: main.api_key }, kind)
  }
  assert.equal((await render().save()).ok, true)
  assert.deepEqual(calls, [['gpt-5-mini', 'quick'], ['gpt-5-mini', 'trial']])
  render().update({ analysis: { ...render().settings.analysis, model: 'changed-model' } })
  assert.equal((await render().save()).ok, true)
  assert.equal(calls.length, 2, 'saving a selection makes no model request')
  assert.equal(writes[1].analysis.model, 'changed-model')
  assert.equal(writes[1].connections[0].api_key, 'fixture')
  await render().testCatalogProvider('openai')
  assert.deepEqual(calls.slice(2), [['changed-model', 'quick']])
  assert.equal(render().settings.connections[0].validation_status, 'transient')
})

test('OpenRouter key guide discovers an analysis model before the first save (#621)', async () => {
  const initial = { ...whisperSettings(), saved: false, analysis: null, connections: [] }
  const bus = loadTs('keyGuideBus.ts')
  const model = 'nvidia/nemotron-3-ultra-550b-a55b'
  const probes = [], writes = []
  const render = settingsHook(initial, {
    discover: async () => ({ source: 'live', models: [{ id: model, analysis: true, capability: 'text' }] }),
    test: async (connection, id) => { probes.push([connection.base_url, id]); return { ok: true } },
    save: async value => { writes.push(value); return { ...value, saved: true } },
  }, false, bus)
  render()
  await new Promise(resolve => setImmediate(resolve))
  render()
  const url = 'https://openrouter.ai/api/v1'
  const result = await bus.commitKeyGuide({ providerId: 'openrouter', apiKey: 'fixture', baseUrl: url, overwrite: false })
  assert.equal(result.ok, true)
  assert.deepEqual(probes, [[url, model]])
  assert.equal(writes[0].analysis.model, model)
  assert.equal(writes[0].connections[0].api_key, 'fixture')
})

test('OpenRouter guide keeps a missing model editable, then saves a manual ID on retry', async () => {
  const bus = loadTs('keyGuideBus.ts')
  const writes = [], probes = []
  const render = settingsHook({ ...whisperSettings(), saved: false, connections: [], analysis: null }, {
    discover: async () => ({ source: 'catalog', preview: true, models: [] }),
    test: async (connection, model) => { probes.push(model); return { ok: true } },
    save: async value => { writes.push(value); return { ...value, saved: true } },
  }, false, bus)
  render()
  await new Promise(resolve => setImmediate(resolve))
  render()
  const request = { providerId: 'openrouter', baseUrl: 'https://openrouter.ai/api/v1', apiKey: 'fixture', overwrite: false }
  assert.equal((await bus.commitKeyGuide(request)).ok, false)
  assert.equal(writes.length, 0)
  assert.deepEqual(probes, [])
  render()
  assert.equal((await bus.commitKeyGuide({ ...request, model: 'vendor/manual' })).ok, true)
  assert.deepEqual(probes, ['vendor/manual'])
  assert.equal(writes[0].analysis.model_source, 'user')
  assert.equal(writes[0].connections.length, 1)
})

test('saving during a provider list refresh reuses the validated vision capability (#619)', async () => {
  const state = whisperSettings()
  const model = 'gpt-5-mini'
  state.analysis = { connection_id: 'selected', model, capability: 'auto' }
  state.analysis_mode = 'auto'
  state.connections = [{ ...state.connections[0], id: 'selected', provider: 'openai', base_url: 'https://api.openai.com/v1' }]
  const calls = []
  let refresh = false
  const render = settingsHook(state, {
    discover: async () => refresh ? new Promise(() => {}) : { source: 'live', models: [{ id: model, analysis: true, capability: 'multimodal' }] },
    test: async (c, id, vision, role, kind) => { calls.push([id, vision, kind]); return { ok: true, models: [model] } },
    save: async value => value,
  })
  await render().load()
  await new Promise(resolve => setImmediate(resolve))
  refresh = true
  await render().testCatalogProvider('openai')
  await render().save()
  assert.deepEqual(calls, [[model, true, 'quick']])
  render().editConnection(render().main, { api_key: 'rotated-fixture' })
  await render().save()
  assert.equal(calls.length, 1)
  assert.equal(render().main.validation_status, 'unchecked', 'new credentials were saved without a check')
  await render().testCatalogProvider('openai')
  assert.equal(calls.length, 2)
})

test('testing a catalog connection after editing its base_url reuses the same connection id (#636)', async () => {
  const state = { ...whisperSettings(), saved: true, analysis: null, connections: [] }
  const model = 'gpt-4o-mini'
  const tested = []
  const render = settingsHook(state, {
    discover: async () => ({ source: 'live', models: [{ id: model, analysis: true, capability: 'text' }] }),
    test: async (c, id, vision, role, kind) => { tested.push([c.id, c.base_url, kind]); return { ok: true, probe_kind: kind } },
    save: async value => value,
  })
  await render().load()
  const id = render().ensureCatalogProvider('openai', { base_url: 'https://gateway.example/final/v1', api_key: 'fixture' })
  assert.ok(id)
  const edited = render().settings.connections.find(row => row.id === id)
  assert.equal(edited.base_url, 'https://gateway.example/final/v1')
  for (const kind of ['quick', 'trial']) {
    await render().testCatalogProvider('openai', edited, kind)
  }
  assert.equal(render().settings.connections.length, 1)
  assert.deepEqual(tested, [
    [id, 'https://gateway.example/final/v1', 'quick'],
    [id, 'https://gateway.example/final/v1', 'trial'],
  ])
})
