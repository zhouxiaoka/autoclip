const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

function settingsHook(initial, transport, requireCloudTranscription = false) {
  let cursor = 0
  const slots = []
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
    useEffect() {},
  }
  const hook = loadTs('useModelSettings.ts', {
    react,
    antd: { message: { success() {}, error() {} } },
    '../../i18n': { t: text => text },
    '../studio/api': { errorText: () => 'redacted' },
    '../studio/settingsReturn': { notifySettingsSaved() {} },
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
      bindingCapability: () => 'text',
    },
  })
  return () => { cursor = 0; return hook.useModelSettings('settings_model', requireCloudTranscription) }
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
  assert.equal(saved.cover_enabled, false)
  assert.equal(saved.transcription.provider, 'cloud')
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
