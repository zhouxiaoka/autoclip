const { test } = require('node:test')
const assert = require('node:assert/strict')
const { loadTs } = require('./load-ts.cjs')

function settingsHook(initial, transport) {
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
    '../../analytics/experience': { beginExperience: () => () => {}, trackProviderValidation() {} },
    './modelSettingsApi': {
      modelSettingsApi: {
        get: async () => structuredClone(initial),
        discover: async () => ({ models: [], source: 'catalog', preview: true }),
        ...transport,
      },
      bindingCapability: () => 'text',
    },
  })
  return () => { cursor = 0; return hook.useModelSettings('settings_model') }
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
